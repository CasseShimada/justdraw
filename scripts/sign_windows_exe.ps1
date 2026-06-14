param(
  [string]$ExePath = "dist\JustDraw.exe"
)

$ErrorActionPreference = "Stop"

function Find-SignTool {
  $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
  if ($command) {
    return $command.Source
  }

  $kitRoot = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
  if (Test-Path -LiteralPath $kitRoot) {
    $matches = Get-ChildItem -LiteralPath $kitRoot -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
      Where-Object { $_.FullName -match "\\x64\\signtool\.exe$" } |
      Sort-Object FullName
    if ($matches) {
      return $matches[-1].FullName
    }
  }

  return ""
}

if (!(Test-Path -LiteralPath $ExePath)) {
  throw "Executable not found: $ExePath"
}

$requireSigning = $env:JUSTDRAW_REQUIRE_CODESIGN -eq "1"
$certPath = $env:JUSTDRAW_CODESIGN_CERT_PATH
$certBase64 = $env:JUSTDRAW_CODESIGN_CERT_BASE64
$certPassword = $env:JUSTDRAW_CODESIGN_CERT_PASSWORD
$timestampUrl = $env:JUSTDRAW_CODESIGN_TIMESTAMP_URL
if ([string]::IsNullOrWhiteSpace($timestampUrl)) {
  $timestampUrl = "http://timestamp.digicert.com"
}

$tempCertPath = ""
if (![string]::IsNullOrWhiteSpace($certBase64)) {
  $tempCertPath = Join-Path $env:TEMP "justdraw-codesign.pfx"
  [System.IO.File]::WriteAllBytes($tempCertPath, [Convert]::FromBase64String($certBase64))
  $certPath = $tempCertPath
}

try {
  if ([string]::IsNullOrWhiteSpace($certPath)) {
    if ($requireSigning) {
      throw "Code signing is required, but no certificate was provided."
    }
    Write-Host "Code signing skipped: no certificate configured."
    exit 0
  }

  if (!(Test-Path -LiteralPath $certPath)) {
    throw "Code signing certificate not found: $certPath"
  }

  $signTool = Find-SignTool
  if ([string]::IsNullOrWhiteSpace($signTool)) {
    throw "signtool.exe was not found. Install the Windows SDK or add signtool.exe to PATH."
  }

  $signArgs = @("sign", "/fd", "SHA256", "/tr", $timestampUrl, "/td", "SHA256", "/f", $certPath)
  if (![string]::IsNullOrEmpty($certPassword)) {
    $signArgs += @("/p", $certPassword)
  }
  $signArgs += @($ExePath)

  Write-Host "Signing $ExePath"
  & $signTool @signArgs
  if ($LASTEXITCODE -ne 0) {
    throw "signtool sign failed with exit code $LASTEXITCODE"
  }

  & $signTool verify /pa /v $ExePath
  if ($LASTEXITCODE -ne 0) {
    throw "signtool verify failed with exit code $LASTEXITCODE"
  }
} finally {
  if ($tempCertPath -and (Test-Path -LiteralPath $tempCertPath)) {
    Remove-Item -LiteralPath $tempCertPath -Force -ErrorAction SilentlyContinue
  }
}
