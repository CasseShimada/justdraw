using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace JustDraw.Wpf;

public sealed record ReleaseInfo(
    string TagName,
    string Name,
    string HtmlUrl,
    string ExeUrl,
    string Sha256Url,
    string Body)
{
    public string Version => UpdateService.NormalizeVersion(TagName);
}

public sealed record UpdateCheckResult(
    ReleaseInfo Release,
    string LocalSha256,
    string RemoteSha256,
    bool UpdateAvailable);

public sealed class UpdateNetworkException(string message, Exception? innerException = null) : Exception(message, innerException);

public sealed class UpdateService
{
    private const string Owner = "CasseShimada";
    private const string Repo = "justdraw";
    private const string ApiLatestRelease = $"https://api.github.com/repos/{Owner}/{Repo}/releases/latest";
    public const string RepositoryUrl = $"https://github.com/{Owner}/{Repo}";
    public const string ReleasesUrl = $"https://github.com/{Owner}/{Repo}/releases/latest";
    private const string WindowsExeAssetName = "JustDraw.exe";
    private const string WindowsSha256AssetName = "JustDraw.exe.sha256";

    public static string AppVersion
    {
        get
        {
            var version = typeof(UpdateService).Assembly.GetName().Version;
            return version is null ? "0.0.0-dev" : $"{version.Major}.{version.Minor}.{version.Build}";
        }
    }

    public static string NormalizeVersion(string value)
    {
        var text = (value ?? "").Trim();
        return text.StartsWith("v", StringComparison.OrdinalIgnoreCase) ? text[1..] : text;
    }

    public static bool IsNewerVersion(string remoteVersion, string currentVersion)
    {
        var remote = NormalizeVersion(remoteVersion);
        var current = NormalizeVersion(currentVersion);
        if (remote.Length == 0 || current.Length == 0)
        {
            return false;
        }

        return CompareVersionKeys(remote, current) > 0;
    }

    private static int CompareVersionKeys(string left, string right)
    {
        var leftParts = VersionParts(left).ToArray();
        var rightParts = VersionParts(right).ToArray();
        var length = Math.Max(leftParts.Length, rightParts.Length);
        for (var i = 0; i < length; i++)
        {
            var l = i < leftParts.Length ? leftParts[i] : "";
            var r = i < rightParts.Length ? rightParts[i] : "";
            var ln = int.TryParse(l, out var li);
            var rn = int.TryParse(r, out var ri);
            var cmp = ln && rn
                ? li.CompareTo(ri)
                : string.Compare(l, r, StringComparison.OrdinalIgnoreCase);
            if (cmp != 0)
            {
                return cmp;
            }
        }

        return 0;
    }

    private static IEnumerable<string> VersionParts(string value)
    {
        foreach (Match match in Regex.Matches(value, "[0-9]+|[A-Za-z]+"))
        {
            yield return match.Value;
        }
    }

    public async Task<UpdateCheckResult> CheckLatestReleaseAsync(string currentExePath, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(currentExePath) || !File.Exists(currentExePath))
        {
            throw new FileNotFoundException("Current executable does not exist", currentExePath);
        }

        var release = await FetchLatestReleaseAsync(cancellationToken).ConfigureAwait(false);
        var remoteSha = await FetchReleaseSha256Async(release, cancellationToken).ConfigureAwait(false);
        var localSha = ComputeSha256(currentExePath);
        return new UpdateCheckResult(release, localSha, remoteSha, !localSha.Equals(remoteSha, StringComparison.OrdinalIgnoreCase));
    }

    public async Task<ReleaseInfo> FetchLatestReleaseAsync(CancellationToken cancellationToken = default)
    {
        return await UseBestConnectionAsync(async (client, token) =>
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, ApiLatestRelease);
            request.Headers.UserAgent.ParseAdd($"JustDraw/{AppVersion}");
            request.Headers.Accept.ParseAdd("application/vnd.github+json");
            using var response = await client.SendAsync(request, token).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            await using var stream = await response.Content.ReadAsStreamAsync(token).ConfigureAwait(false);
            using var document = await JsonDocument.ParseAsync(stream, cancellationToken: token).ConfigureAwait(false);
            var root = document.RootElement;
            var exeUrl = "";
            var shaUrl = "";
            if (root.TryGetProperty("assets", out var assets) && assets.ValueKind == JsonValueKind.Array)
            {
                foreach (var asset in assets.EnumerateArray())
                {
                    var name = asset.TryGetProperty("name", out var nameElement) ? nameElement.GetString() ?? "" : "";
                    var url = asset.TryGetProperty("browser_download_url", out var urlElement) ? urlElement.GetString() ?? "" : "";
                    if (name.Equals(WindowsExeAssetName, StringComparison.OrdinalIgnoreCase))
                    {
                        exeUrl = url;
                    }
                    else if (name.Equals(WindowsSha256AssetName, StringComparison.OrdinalIgnoreCase))
                    {
                        shaUrl = url;
                    }
                }
            }

            return new ReleaseInfo(
                root.TryGetProperty("tag_name", out var tag) ? tag.GetString() ?? "" : "",
                root.TryGetProperty("name", out var nameValue) ? nameValue.GetString() ?? "" : "",
                root.TryGetProperty("html_url", out var html) ? html.GetString() ?? ReleasesUrl : ReleasesUrl,
                exeUrl,
                shaUrl,
                root.TryGetProperty("body", out var body) ? body.GetString() ?? "" : "");
        }, cancellationToken).ConfigureAwait(false);
    }

    public async Task<string> DownloadReleaseExeAsync(ReleaseInfo releaseInfo, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(releaseInfo.ExeUrl))
        {
            throw new InvalidOperationException($"The latest release does not include {WindowsExeAssetName}");
        }

        var tempDir = Path.Combine(Path.GetTempPath(), "justdraw-update-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempDir);
        var exePath = Path.Combine(tempDir, WindowsExeAssetName);
        await UseBestConnectionAsync(async (client, token) =>
        {
            await DownloadFileAsync(client, releaseInfo.ExeUrl, exePath, token).ConfigureAwait(false);
            if (new FileInfo(exePath).Length <= 0)
            {
                throw new InvalidOperationException("Downloaded update file is empty");
            }

            if (!string.IsNullOrWhiteSpace(releaseInfo.Sha256Url))
            {
                var shaPath = Path.Combine(tempDir, WindowsSha256AssetName);
                await DownloadFileAsync(client, releaseInfo.Sha256Url, shaPath, token).ConfigureAwait(false);
                VerifySha256(exePath, shaPath);
            }

            return true;
        }, cancellationToken).ConfigureAwait(false);

        return exePath;
    }

    public string CreateUpdateScript(string downloadedExePath, string? targetExePath = null, bool restart = true)
    {
        if (!OperatingSystem.IsWindows())
        {
            throw new InvalidOperationException("Automatic replacement is only supported on Windows");
        }

        var target = Path.GetFullPath(targetExePath ?? Environment.ProcessPath ?? "");
        if (target.Length == 0)
        {
            throw new InvalidOperationException("Could not resolve current executable path");
        }

        var source = Path.GetFullPath(downloadedExePath);
        var backup = target + ".old";
        var scriptPath = Path.Combine(Path.GetTempPath(), "justdraw_apply_update_" + DateTimeOffset.UtcNow.ToUnixTimeSeconds() + ".ps1");
        var lines = new List<string>
        {
            "$ErrorActionPreference = \"Stop\"",
            "$source = " + QuotePowerShell(source),
            "$target = " + QuotePowerShell(target),
            "$backup = " + QuotePowerShell(backup),
            "Start-Sleep -Milliseconds 800",
            "for ($i = 0; $i -lt 60; $i++) {",
            "    try {",
            "        if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue }",
            "        if (Test-Path -LiteralPath $target) { Rename-Item -LiteralPath $target -NewName ([System.IO.Path]::GetFileName($backup)) -Force }",
            "        Move-Item -LiteralPath $source -Destination $target -Force",
            "        if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue }",
            "        break",
            "    } catch {",
            "        Start-Sleep -Milliseconds 500",
            "        if ($i -eq 59) { throw }",
            "    }",
            "}"
        };
        if (restart)
        {
            lines.Add("Start-Process -FilePath $target");
        }

        File.WriteAllLines(scriptPath, lines);
        return scriptPath;
    }

    public static void LaunchUpdateScript(string scriptPath)
    {
        var powershell = FindOnPath("powershell.exe") ?? FindOnPath("pwsh.exe") ?? "powershell.exe";
        Process.Start(new ProcessStartInfo
        {
            FileName = powershell,
            Arguments = $"-NoProfile -ExecutionPolicy Bypass -File \"{scriptPath}\"",
            UseShellExecute = false,
            CreateNoWindow = true
        });
    }

    private static async Task<string> FetchReleaseSha256Async(ReleaseInfo releaseInfo, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(releaseInfo.Sha256Url))
        {
            throw new InvalidOperationException($"The latest release does not include {WindowsSha256AssetName}");
        }

        return await UseBestConnectionAsync(async (client, token) =>
        {
            using var response = await client.GetAsync(releaseInfo.Sha256Url, token).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            var text = await response.Content.ReadAsStringAsync(token).ConfigureAwait(false);
            return ParseSha256(text);
        }, cancellationToken).ConfigureAwait(false);
    }

    private static async Task<T> UseBestConnectionAsync<T>(Func<HttpClient, CancellationToken, Task<T>> action, CancellationToken cancellationToken)
    {
        try
        {
            using var directClient = CreateHttpClient(useSystemProxy: false);
            return await action(directClient, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception ex) when (IsConnectionFailure(ex))
        {
            // Direct connection failed. Try the system proxy next.
        }

        try
        {
            using var proxyClient = CreateHttpClient(useSystemProxy: true);
            return await action(proxyClient, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception ex) when (IsConnectionFailure(ex))
        {
            throw new UpdateNetworkException("Network error. Please check your internet connection or system proxy.", ex);
        }
    }

    private static bool IsConnectionFailure(Exception ex) =>
        ex is TaskCanceledException or WebException ||
        ex is HttpRequestException { StatusCode: null };

    private static HttpClient CreateHttpClient(bool useSystemProxy)
    {
        var handler = new HttpClientHandler
        {
            UseProxy = useSystemProxy,
            Proxy = useSystemProxy ? WebRequest.DefaultWebProxy : null
        };

        if (handler.Proxy is not null)
        {
            handler.Proxy.Credentials = CredentialCache.DefaultCredentials;
        }

        return new HttpClient(handler)
        {
            Timeout = TimeSpan.FromSeconds(30)
        };
    }

    private static async Task DownloadFileAsync(HttpClient client, string url, string path, CancellationToken cancellationToken)
    {
        using var response = await client.GetAsync(url, cancellationToken).ConfigureAwait(false);
        response.EnsureSuccessStatusCode();
        await using var source = await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false);
        await using var target = File.Create(path);
        await source.CopyToAsync(target, cancellationToken).ConfigureAwait(false);
    }

    private static void VerifySha256(string exePath, string shaPath)
    {
        var expected = ParseSha256(File.ReadAllText(shaPath));
        var actual = ComputeSha256(exePath);
        if (!actual.Equals(expected, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("Downloaded update checksum did not match the release checksum");
        }
    }

    private static string ParseSha256(string text)
    {
        var expected = text.Trim().Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries).FirstOrDefault()?.ToLowerInvariant();
        if (expected is null || !Regex.IsMatch(expected, "^[0-9a-f]{64}$"))
        {
            throw new InvalidOperationException("Release checksum is invalid");
        }

        return expected;
    }

    private static string ComputeSha256(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    private static string QuotePowerShell(string value) => "'" + value.Replace("'", "''") + "'";

    private static string? FindOnPath(string name)
    {
        var path = Environment.GetEnvironmentVariable("PATH") ?? "";
        foreach (var folder in path.Split(Path.PathSeparator))
        {
            var candidate = Path.Combine(folder.Trim(), name);
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        return null;
    }
}
