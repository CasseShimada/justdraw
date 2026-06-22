using System.Collections.Concurrent;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text.Json;

namespace JustDraw.Wpf;

public sealed record VideoFrameInfo(string Path, double Duration, double Fps, int FrameCount, int Width, int Height);

public sealed class VideoFrameCache : IDisposable
{
    private const int PreloadRadius = 50;
    private const int MaxCachedFrames = 320;

    private readonly SemaphoreSlim _extractGate = new(2);
    private readonly ConcurrentDictionary<int, Task<string>> _frameTasks = [];
    private readonly object _sync = new();
    private readonly object _preloadSync = new();
    private readonly List<int> _cacheOrder = [];

    private VideoToolsInfo _tools = new("", "", false, "");
    private VideoFrameInfo? _video;
    private string _cacheDirectory = "";
    private int _preloadVersion;
    private int _sessionId;
    private CancellationTokenSource? _preloadCts;

    public VideoFrameInfo? CurrentVideo => _video;

    public async Task<VideoFrameInfo> OpenAsync(VideoToolsInfo tools, string path, CancellationToken cancellationToken = default)
    {
        if (!tools.Available)
        {
            throw new InvalidOperationException(tools.MissingReason);
        }

        if (!File.Exists(path))
        {
            throw new FileNotFoundException("Video does not exist", path);
        }

        Clear();
        _tools = tools;
        var info = await ProbeAsync(tools.FfprobePath, path, cancellationToken).ConfigureAwait(false);
        _video = info;
        _cacheDirectory = Path.Combine(Path.GetTempPath(), "JustDrawVideoFrames_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_cacheDirectory);
        return info;
    }

    public async Task<string> GetFrameAsync(int frameIndex, CancellationToken cancellationToken = default)
    {
        var video = _video ?? throw new InvalidOperationException("No video is open");
        var index = Math.Clamp(frameIndex, 0, video.FrameCount - 1);
        cancellationToken.ThrowIfCancellationRequested();
        var cacheDirectory = _cacheDirectory;
        var sessionId = _sessionId;
        var task = _frameTasks.GetOrAdd(index, _ => ExtractFrameAsync(video, index, cacheDirectory, sessionId, cancellationToken));
        try
        {
            var path = await task.WaitAsync(cancellationToken).ConfigureAwait(false);
            Touch(index);
            return path;
        }
        catch
        {
            if (task.IsFaulted || task.IsCanceled)
            {
                _frameTasks.TryRemove(index, out _);
            }

            throw;
        }
    }

    public async Task<string> GetFrameForDisplayAsync(int frameIndex, CancellationToken cancellationToken = default)
    {
        CancelPreload();
        var video = _video ?? throw new InvalidOperationException("No video is open");
        var index = Math.Clamp(frameIndex, 0, video.FrameCount - 1);
        cancellationToken.ThrowIfCancellationRequested();

        if (_frameTasks.TryGetValue(index, out var existingTask))
        {
            try
            {
                var cachedPath = await existingTask.WaitAsync(cancellationToken).ConfigureAwait(false);
                if (File.Exists(cachedPath))
                {
                    Touch(index);
                    return cachedPath;
                }

                _frameTasks.TryRemove(index, out _);
            }
            catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
            {
                _frameTasks.TryRemove(index, out _);
            }
            catch
            {
                if (existingTask.IsFaulted || existingTask.IsCanceled)
                {
                    _frameTasks.TryRemove(index, out _);
                }

                throw;
            }
        }

        var cacheDirectory = _cacheDirectory;
        var sessionId = _sessionId;
        var path = await ExtractFrameAsync(video, index, cacheDirectory, sessionId, cancellationToken).ConfigureAwait(false);
        _frameTasks[index] = Task.FromResult(path);
        Touch(index);
        return path;
    }

    public void PreloadAround(int frameIndex)
    {
        var video = _video;
        if (video is null)
        {
            return;
        }

        var version = Interlocked.Increment(ref _preloadVersion);
        var cts = BeginPreload();
        var token = cts.Token;
        _ = Task.Run(async () =>
        {
            try
            {
                var start = Math.Max(0, frameIndex - PreloadRadius);
                var end = Math.Min(video.FrameCount - 1, frameIndex + PreloadRadius);
                var indexes = Enumerable.Range(start, end - start + 1)
                    .OrderBy(index => Math.Abs(index - frameIndex))
                    .ToList();

                foreach (var index in indexes)
                {
                    if (version != Volatile.Read(ref _preloadVersion) || token.IsCancellationRequested)
                    {
                        return;
                    }

                    try
                    {
                        await GetFrameAsync(index, token).ConfigureAwait(false);
                    }
                    catch (OperationCanceledException)
                    {
                        return;
                    }
                    catch
                    {
                        // Bad individual frames should not stop navigation.
                    }
                }
            }
            finally
            {
                FinishPreload(cts);
            }
        });
    }

    public void CancelPreload()
    {
        Interlocked.Increment(ref _preloadVersion);
        lock (_preloadSync)
        {
            _preloadCts?.Cancel();
        }
    }

    public void Clear()
    {
        CancelPreload();
        Interlocked.Increment(ref _sessionId);
        foreach (var path in _frameTasks.Values.Where(task => task.IsCompletedSuccessfully).Select(task => task.Result))
        {
            TryDelete(path);
        }

        _frameTasks.Clear();
        lock (_sync)
        {
            _cacheOrder.Clear();
        }

        if (!string.IsNullOrWhiteSpace(_cacheDirectory) && Directory.Exists(_cacheDirectory))
        {
            TryDeleteDirectory(_cacheDirectory);
        }

        _video = null;
        _cacheDirectory = "";
    }

    private CancellationTokenSource BeginPreload()
    {
        lock (_preloadSync)
        {
            _preloadCts?.Cancel();
            _preloadCts = new CancellationTokenSource();
            return _preloadCts;
        }
    }

    private void FinishPreload(CancellationTokenSource cts)
    {
        lock (_preloadSync)
        {
            if (ReferenceEquals(_preloadCts, cts))
            {
                _preloadCts = null;
            }
        }

        cts.Dispose();
    }

    private async Task<string> ExtractFrameAsync(VideoFrameInfo video, int frameIndex, string cacheDirectory, int sessionId, CancellationToken cancellationToken)
    {
        await _extractGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            Directory.CreateDirectory(cacheDirectory);
            var path = FramePath(cacheDirectory, frameIndex);
            if (File.Exists(path))
            {
                return path;
            }

            var seconds = frameIndex / video.Fps;
            await RunProcessAsync(_tools.FfmpegPath, [
                "-y",
                "-hide_banner",
                "-loglevel", "error",
                "-ss", seconds.ToString("0.########", CultureInfo.InvariantCulture),
                "-i", video.Path,
                "-frames:v", "1",
                "-q:v", "2",
                path
            ], cancellationToken).ConfigureAwait(false);
            cancellationToken.ThrowIfCancellationRequested();
            if (sessionId == Volatile.Read(ref _sessionId))
            {
                TrimCache(frameIndex);
            }
            else
            {
                TryDelete(path);
                TryDeleteDirectory(cacheDirectory);
                throw new OperationCanceledException();
            }

            return path;
        }
        catch (OperationCanceledException)
        {
            TryDelete(FramePath(cacheDirectory, frameIndex));
            throw;
        }
        finally
        {
            _extractGate.Release();
        }
    }

    private static string FramePath(string cacheDirectory, int frameIndex) => Path.Combine(cacheDirectory, $"frame_{frameIndex:000000000}.jpg");

    private void Touch(int frameIndex)
    {
        lock (_sync)
        {
            _cacheOrder.Remove(frameIndex);
            _cacheOrder.Add(frameIndex);
        }
    }

    private void TrimCache(int currentFrame)
    {
        List<int> toRemove = [];
        lock (_sync)
        {
            _cacheOrder.Remove(currentFrame);
            _cacheOrder.Add(currentFrame);
            while (_cacheOrder.Count > MaxCachedFrames)
            {
                toRemove.Add(_cacheOrder[0]);
                _cacheOrder.RemoveAt(0);
            }
        }

        foreach (var index in toRemove)
        {
            if (_frameTasks.TryRemove(index, out _))
            {
                TryDelete(FramePath(_cacheDirectory, index));
            }
        }
    }

    private static async Task<VideoFrameInfo> ProbeAsync(string ffprobe, string path, CancellationToken cancellationToken)
    {
        var output = await RunProcessAsync(ffprobe, [
            "-v", "error",
            "-show_entries", "format=duration:stream=codec_type,width,height,avg_frame_rate,nb_frames",
            "-of", "json",
            path
        ], cancellationToken).ConfigureAwait(false);

        using var document = JsonDocument.Parse(output);
        var root = document.RootElement;
        var stream = root.GetProperty("streams").EnumerateArray()
            .FirstOrDefault(item => item.TryGetProperty("codec_type", out var codec) && codec.GetString() == "video");
        if (stream.ValueKind == JsonValueKind.Undefined)
        {
            throw new InvalidOperationException("No video stream found");
        }

        var width = stream.TryGetProperty("width", out var widthElement) ? widthElement.GetInt32() : 0;
        var height = stream.TryGetProperty("height", out var heightElement) ? heightElement.GetInt32() : 0;
        var fpsText = stream.TryGetProperty("avg_frame_rate", out var fpsElement) ? fpsElement.GetString() ?? "" : "";
        var fps = Math.Max(1.0, ParseFps(fpsText));
        var durationText = root.GetProperty("format").TryGetProperty("duration", out var durationElement) ? durationElement.GetString() : "0";
        var duration = double.TryParse(durationText, NumberStyles.Float, CultureInfo.InvariantCulture, out var parsedDuration) ? parsedDuration : 0;
        var frameCount = 0;
        if (stream.TryGetProperty("nb_frames", out var framesElement) &&
            int.TryParse(framesElement.GetString(), NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsedFrames))
        {
            frameCount = parsedFrames;
        }

        if (frameCount <= 0)
        {
            frameCount = Math.Max(1, (int)Math.Ceiling(duration * fps));
        }

        return new VideoFrameInfo(path, Math.Max(0.1, duration), fps, frameCount, width, height);
    }

    private static double ParseFps(string value)
    {
        var parts = value.Split('/');
        if (parts.Length == 2
            && double.TryParse(parts[0], NumberStyles.Float, CultureInfo.InvariantCulture, out var numerator)
            && double.TryParse(parts[1], NumberStyles.Float, CultureInfo.InvariantCulture, out var denominator)
            && denominator > 0)
        {
            return numerator / denominator;
        }

        return double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var fps) ? fps : 30.0;
    }

    private static async Task<string> RunProcessAsync(string fileName, IReadOnlyList<string> arguments, CancellationToken cancellationToken)
    {
        var start = new ProcessStartInfo
        {
            FileName = fileName,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        foreach (var argument in arguments)
        {
            start.ArgumentList.Add(argument);
        }

        using var process = Process.Start(start) ?? throw new InvalidOperationException($"Could not start {fileName}");
        var stdoutTask = process.StandardOutput.ReadToEndAsync(cancellationToken);
        var stderrTask = process.StandardError.ReadToEndAsync(cancellationToken);
        try
        {
            await process.WaitForExitAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            TryKill(process);
            throw;
        }

        var stdout = await stdoutTask.ConfigureAwait(false);
        var stderr = await stderrTask.ConfigureAwait(false);
        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException(stderr.Trim().Length > 0 ? stderr.Trim() : $"{Path.GetFileName(fileName)} failed with exit code {process.ExitCode}");
        }

        return stdout;
    }

    private static void TryKill(Process process)
    {
        try
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
            }
        }
        catch
        {
            // Process cancellation is best effort.
        }
    }

    private static void TryDelete(string path)
    {
        try
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }
        catch
        {
            // Cache cleanup is best effort.
        }
    }

    private static void TryDeleteDirectory(string path)
    {
        try
        {
            Directory.Delete(path, recursive: true);
        }
        catch
        {
            // Cache cleanup is best effort.
        }
    }

    public void Dispose()
    {
        CancelPreload();
        Clear();
    }
}
