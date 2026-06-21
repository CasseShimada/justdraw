using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace JustDraw.Wpf;

public sealed record VideoToolsInfo(string FfmpegPath, string FfprobePath, bool Available, string MissingReason);

public sealed record VideoExportOptions(
    string InputPath,
    string OutputPath,
    int TargetDurationSeconds,
    string OutputFormat,
    string WatermarkPath,
    string WatermarkText,
    string OverlayMode,
    bool DeleteOriginalAfterExport);

public sealed record VideoExportResult(string OutputPath, double FinalDuration, double SourceDuration);

public sealed class VideoExportService
{
    public static readonly string[] VideoExtensions =
    [
        ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".flv", ".ts", ".mts", ".m2ts"
    ];

    public static VideoToolsInfo FindTools()
    {
        var ffmpeg = FindBinary("ffmpeg");
        var ffprobe = FindBinary("ffprobe");
        if (!string.IsNullOrWhiteSpace(ffmpeg) && string.IsNullOrWhiteSpace(ffprobe))
        {
            var sibling = Path.Combine(Path.GetDirectoryName(ffmpeg) ?? "", OperatingSystem.IsWindows() ? "ffprobe.exe" : "ffprobe");
            if (File.Exists(sibling))
            {
                ffprobe = sibling;
            }
        }

        var missing = new List<string>();
        if (string.IsNullOrWhiteSpace(ffmpeg))
        {
            missing.Add("ffmpeg was not found");
        }

        if (string.IsNullOrWhiteSpace(ffprobe))
        {
            missing.Add("ffprobe was not found");
        }

        return new VideoToolsInfo(ffmpeg ?? "", ffprobe ?? "", missing.Count == 0, string.Join("; ", missing));
    }

    public async Task<VideoExportResult> ExportProtectedShortVideoAsync(
        VideoToolsInfo tools,
        VideoExportOptions options,
        IProgress<(int Percent, string Stage, string Detail)>? progress = null,
        CancellationToken cancellationToken = default)
    {
        if (!tools.Available)
        {
            throw new InvalidOperationException(tools.MissingReason);
        }

        if (!File.Exists(options.InputPath))
        {
            throw new FileNotFoundException("Input video does not exist", options.InputPath);
        }

        var format = NormalizeFormat(options.OutputFormat);
        var overlay = NormalizeOverlay(options.OverlayMode);
        if (string.IsNullOrWhiteSpace(options.WatermarkPath) && string.IsNullOrWhiteSpace(options.WatermarkText))
        {
            throw new InvalidOperationException("Provide a watermark image or watermark text");
        }

        if (!string.IsNullOrWhiteSpace(options.WatermarkPath) && !File.Exists(options.WatermarkPath))
        {
            throw new FileNotFoundException("Watermark image does not exist", options.WatermarkPath);
        }

        var meta = await ProbeVideoAsync(tools.FfprobePath, options.InputPath, cancellationToken).ConfigureAwait(false);
        var tempDir = Path.Combine(Path.GetTempPath(), "justdraw-video-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempDir);
        var tempDedupe = Path.Combine(tempDir, "dedupe.mp4");
        var tempRender = Path.Combine(tempDir, "render.mp4");
        var noiseImage = Path.Combine(tempDir, "noise.png");
        var watermarkImage = Path.Combine(tempDir, "watermark.png");
        try
        {
            progress?.Report((5, "Removing duplicate frames", Path.GetFileName(options.InputPath)));
            await RunProcessAsync(tools.FfmpegPath, [
                "-y",
                "-i", options.InputPath,
                "-vf", $"mpdecimate=hi=64*8:lo=64*3:frac=0.10:keep=6,setpts=N/({Math.Max(meta.Fps, 1.0).ToString("0.##########", CultureInfo.InvariantCulture)}*TB)",
                "-an",
                "-c:v", "libx264",
                "-crf", "18",
                "-preset", "veryfast",
                tempDedupe
            ], cancellationToken).ConfigureAwait(false);

            var processed = await ProbeVideoAsync(tools.FfprobePath, tempDedupe, cancellationToken).ConfigureAwait(false);
            var outputPath = ResolveOutputPath(options, processed.Duration, format);

            progress?.Report((45, "Preparing watermark and overlays", Path.GetFileName(outputPath)));
            var watermarkAsset = options.WatermarkPath;
            if (string.IsNullOrWhiteSpace(watermarkAsset))
            {
                await GenerateTextWatermarkAsync(tools.FfmpegPath, watermarkImage, options.WatermarkText, meta.Width, meta.Height, cancellationToken).ConfigureAwait(false);
                watermarkAsset = watermarkImage;
            }

            if (overlay == "noise")
            {
                await GenerateNoiseAsync(tools.FfmpegPath, noiseImage, meta.Width, meta.Height, cancellationToken).ConfigureAwait(false);
            }

            progress?.Report((65, "Rendering protected clip", Path.GetFileName(outputPath)));
            var renderArgs = BuildRenderArguments(
                inputPath: tempDedupe,
                sourcePath: options.InputPath,
                outputPath: tempRender,
                noisePath: overlay == "noise" ? noiseImage : "",
                watermarkPath: watermarkAsset,
                width: meta.Width,
                height: meta.Height,
                processedDuration: Math.Max(0.1, processed.Duration),
                targetDuration: Math.Max(1, options.TargetDurationSeconds));
            await RunProcessAsync(tools.FfmpegPath, renderArgs, cancellationToken).ConfigureAwait(false);

            if (format == "gif")
            {
                progress?.Report((88, "Writing GIF", Path.GetFileName(outputPath)));
                await RunProcessAsync(tools.FfmpegPath, [
                    "-y",
                    "-i", tempRender,
                    "-filter_complex", "split[v_palette_src][v_gif_src];[v_palette_src]palettegen=reserve_transparent=0:stats_mode=full[palette];[v_gif_src][palette]paletteuse=dither=sierra2_4a[vout]",
                    "-map", "[vout]",
                    "-loop", "0",
                    outputPath
                ], cancellationToken).ConfigureAwait(false);
            }
            else
            {
                File.Copy(tempRender, outputPath, overwrite: true);
            }

            var finalMeta = await ProbeVideoAsync(tools.FfprobePath, outputPath, cancellationToken).ConfigureAwait(false);
            if (options.DeleteOriginalAfterExport)
            {
                File.Delete(options.InputPath);
            }

            progress?.Report((100, "Protected video export complete", Path.GetFileName(outputPath)));
            return new VideoExportResult(outputPath, finalMeta.Duration, meta.Duration);
        }
        finally
        {
            try
            {
                Directory.Delete(tempDir, recursive: true);
            }
            catch
            {
                // Temporary cleanup is best effort.
            }
        }
    }

    private static List<string> BuildRenderArguments(
        string inputPath,
        string sourcePath,
        string outputPath,
        string noisePath,
        string watermarkPath,
        int width,
        int height,
        double processedDuration,
        int targetDuration)
    {
        var intro = targetDuration >= 2 ? 1.0 : 0.0;
        var outro = targetDuration >= 2 ? 1.0 : 0.0;
        var mainDuration = Math.Max(0.2, targetDuration - intro - outro);
        var speedFactor = processedDuration / mainDuration;
        var inputs = new List<string> { "-y", "-i", inputPath, "-sseof", "-1", "-i", sourcePath };
        var nextInputIndex = 2;
        var noiseInputIndex = -1;
        var watermarkInputIndex = -1;
        if (!string.IsNullOrWhiteSpace(noisePath))
        {
            noiseInputIndex = nextInputIndex++;
            inputs.AddRange(["-loop", "1", "-i", noisePath]);
        }

        if (!string.IsNullOrWhiteSpace(watermarkPath))
        {
            watermarkInputIndex = nextInputIndex;
            inputs.AddRange(["-loop", "1", "-i", watermarkPath]);
        }

        var filter = new StringBuilder();
        filter.Append(CultureInfo.InvariantCulture, $"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,setpts=PTS/{Math.Max(0.001, speedFactor):0.##########},trim=duration={mainDuration:0.###}[main];");
        filter.Append(CultureInfo.InvariantCulture, $"[0:v]select=eq(n\\,0),scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,trim=duration={Math.Max(0.01, intro):0.###},setpts=N/30/TB[intro];");
        filter.Append(CultureInfo.InvariantCulture, $"[1:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,trim=duration={Math.Max(0.01, outro):0.###},setpts=N/30/TB[outro];");
        filter.Append("[intro][main][outro]concat=n=3:v=1:a=0,fps=30,format=rgba[base];");
        var current = "base";
        if (noiseInputIndex >= 0)
        {
            filter.Append(CultureInfo.InvariantCulture, $"[{noiseInputIndex}:v]scale={width}:{height}:flags=lanczos,format=rgba,colorchannelmixer=aa=0.120[noise];");
            filter.Append($"[{current}][noise]overlay=0:0:format=auto[noised];");
            current = "noised";
        }

        if (watermarkInputIndex >= 0)
        {
            filter.Append(CultureInfo.InvariantCulture, $"[{watermarkInputIndex}:v]scale={width}:{height}:flags=lanczos,format=rgba,colorchannelmixer=aa=0.360[wm];");
            filter.Append($"[{current}][wm]overlay=0:0:format=auto[vout]");
        }
        else
        {
            filter.Append($"[{current}]format=yuv420p[vout]");
        }

        var args = inputs;
        args.AddRange([
            "-filter_complex", filter.ToString(),
            "-map", "[vout]",
            "-an",
            "-t", targetDuration.ToString(CultureInfo.InvariantCulture),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "22",
            "-preset", "medium",
            "-movflags", "+faststart",
            outputPath
        ]);
        return args;
    }

    private static async Task GenerateTextWatermarkAsync(string ffmpeg, string path, string text, int width, int height, CancellationToken cancellationToken)
    {
        var escaped = (text ?? "JustDraw").Replace("\\", "\\\\").Replace(":", "\\:").Replace("'", "\\'");
        var fontSize = Math.Max(24, Math.Min(width, height) / 12);
        var filter = $"color=c=black@0.0:s={width}x{height},format=rgba,drawtext=text='{escaped}':fontcolor=white@0.75:fontsize={fontSize}:x=(w-text_w)/2:y=(h-text_h)/2";
        await RunProcessAsync(ffmpeg, [
            "-y",
            "-f", "lavfi",
            "-i", filter,
            "-frames:v", "1",
            "-pix_fmt", "rgba",
            path
        ], cancellationToken).ConfigureAwait(false);
    }

    private static async Task GenerateNoiseAsync(string ffmpeg, string path, int width, int height, CancellationToken cancellationToken)
    {
        await RunProcessAsync(ffmpeg, [
            "-y",
            "-f", "lavfi",
            "-i", $"nullsrc=s={Math.Max(640, width)}x{Math.Max(640, height)}",
            "-frames:v", "1",
            "-vf", $"noise=alls=100:allf=u,boxblur=1:1,scale={width}:{height},format=rgb24",
            path
        ], cancellationToken).ConfigureAwait(false);
    }

    private static string ResolveOutputPath(VideoExportOptions options, double processedDuration, string format)
    {
        if (!string.IsNullOrWhiteSpace(options.OutputPath))
        {
            return options.OutputPath;
        }

        var directory = Path.GetDirectoryName(options.InputPath) ?? Environment.CurrentDirectory;
        var stem = Path.GetFileNameWithoutExtension(options.InputPath);
        var duration = Math.Max(0, (int)Math.Round(processedDuration));
        return Path.Combine(directory, $"{stem}_{duration:000000}_{Math.Max(1, options.TargetDurationSeconds)}s.{format}");
    }

    private static async Task<VideoMeta> ProbeVideoAsync(string ffprobe, string inputPath, CancellationToken cancellationToken)
    {
        var output = await RunProcessAsync(ffprobe, [
            "-v", "error",
            "-show_entries", "format=duration:stream=codec_type,width,height,avg_frame_rate",
            "-of", "json",
            inputPath
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
        if (width <= 0 || height <= 0)
        {
            throw new InvalidOperationException("Video dimensions could not be read");
        }

        if (width % 2 == 1)
        {
            width--;
        }

        if (height % 2 == 1)
        {
            height--;
        }

        var durationText = root.GetProperty("format").TryGetProperty("duration", out var durationElement) ? durationElement.GetString() : "0";
        var duration = double.TryParse(durationText, NumberStyles.Float, CultureInfo.InvariantCulture, out var parsedDuration) ? parsedDuration : 0;
        var fpsText = stream.TryGetProperty("avg_frame_rate", out var fpsElement) ? fpsElement.GetString() ?? "" : "";
        var fps = ParseFps(fpsText);
        return new VideoMeta(width, height, Math.Max(0.1, duration), Math.Max(1.0, fps));
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

    private static string NormalizeFormat(string value)
    {
        var format = (value ?? "mp4").Trim().ToLowerInvariant();
        return format == "gif" ? "gif" : "mp4";
    }

    private static string NormalizeOverlay(string value)
    {
        var overlay = (value ?? "noise").Trim().ToLowerInvariant();
        return overlay is "off" or "none" or "no overlay" ? "off" : "noise";
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
        await process.WaitForExitAsync(cancellationToken).ConfigureAwait(false);
        var stdout = await stdoutTask.ConfigureAwait(false);
        var stderr = await stderrTask.ConfigureAwait(false);
        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException(stderr.Trim().Length > 0 ? stderr.Trim() : $"{Path.GetFileName(fileName)} failed with exit code {process.ExitCode}");
        }

        return stdout;
    }

    private static string? FindBinary(string name)
    {
        var executable = OperatingSystem.IsWindows() ? name + ".exe" : name;
        foreach (var folder in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(Path.PathSeparator))
        {
            if (string.IsNullOrWhiteSpace(folder))
            {
                continue;
            }

            var candidate = Path.Combine(folder.Trim(), executable);
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        var candidates = new List<string>();
        if (OperatingSystem.IsWindows())
        {
            var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            var programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
            candidates.Add(Path.Combine(local, "Programs", "ffmpeg", "bin", executable));
            candidates.Add(Path.Combine(programFiles, "ffmpeg", "bin", executable));
            candidates.Add(Path.Combine("C:\\", "ffmpeg", "bin", executable));
        }

        return candidates.FirstOrDefault(File.Exists);
    }

    private sealed record VideoMeta(int Width, int Height, double Duration, double Fps);
}
