@echo off
setlocal

cd /d "%~dp0"

where dotnet >nul 2>nul
if errorlevel 1 (
  echo .NET SDK not found. Please install the .NET SDK first.
  pause
  exit /b 1
)

echo Building JustDraw C# WPF edition...
dotnet publish src\JustDraw.Wpf\JustDraw.Wpf.csproj ^
  -c Release ^
  -r win-x64 ^
  --self-contained false ^
  -p:PublishSingleFile=true ^
  -p:IncludeNativeLibrariesForSelfExtract=true ^
  -p:PublishReadyToRun=false ^
  -o artifacts\csharp-win-x64

if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

echo.
echo Build succeeded: artifacts\csharp-win-x64\JustDraw.exe
pause
