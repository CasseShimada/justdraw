using System.IO;
using System.Globalization;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace JustDraw.Wpf;

public enum AppMode
{
    PhotoSwitching,
    ColorBlocks,
    ColorPhoto,
    VideoFrames
}

public enum TimerEndMode
{
    AutoNext,
    Hold,
    Overtime
}

public sealed class ImageViewState
{
    public double Scale { get; set; } = 1.0;
    public double OffsetX { get; set; }
    public double OffsetY { get; set; }
    public int Rotation { get; set; }
}

public sealed class ModeState
{
    public string ImageRootPath { get; set; } = "";
    public string LastImagePath { get; set; } = "";
    public int VideoFrameIndex { get; set; }
    public bool RandomPlayMode { get; set; }
    public int TimerSeconds { get; set; } = 90;
    public TimerEndMode TimerEndMode { get; set; } = TimerEndMode.AutoNext;
    public bool PrestartCountdownEnabled { get; set; }
    public bool MosaicEnabled { get; set; }
    public List<string> ImageOrder { get; set; } = [];
    public Dictionary<string, ImageViewState> ImageViewStates { get; set; } = new(StringComparer.OrdinalIgnoreCase);
    public List<string> RecentPaths { get; set; } = [];
}

public sealed class JustDrawState
{
    public int WindowWidth { get; set; } = 640;
    public int WindowHeight { get; set; } = 760;
    public AppMode AppMode { get; set; } = AppMode.PhotoSwitching;
    public bool StayOnTop { get; set; }
    public bool LockImageViewportAspectRatio { get; set; }
    public bool FlipHorizontal { get; set; }
    public bool FlipVertical { get; set; }
    public string UiLanguage { get; set; } = CultureInfo.CurrentUICulture.TwoLetterISOLanguageName.Equals("zh", StringComparison.OrdinalIgnoreCase) ? "zh" : "en";
    public bool TimerFinishNotificationEnabled { get; set; }
    public bool SampleImageColorsEnabled { get; set; }
    public bool GrayscaleDisplayEnabled { get; set; }
    public string ThemeAccentColor { get; set; } = "#0EA5A8";
    public int MosaicDownsampleFactor { get; set; } = 16;
    public int ColorBlocksStripeCount { get; set; } = 1;
    public double ColorBlocksMinLuma { get; set; } = 0.22;
    public double ColorBlocksMaxLuma { get; set; } = 0.82;
    public double ColorBlocksMinSaturation { get; set; } = 0.35;
    public bool ColorBlocksShapeModeEnabled { get; set; }
    public ProtectedVideoExportState ProtectedVideoExport { get; set; } = new();
    public Dictionary<AppMode, ModeState> Modes { get; set; } = new()
    {
        [AppMode.PhotoSwitching] = new ModeState(),
        [AppMode.ColorPhoto] = new ModeState(),
        [AppMode.VideoFrames] = new ModeState()
    };

    [JsonIgnore]
    public ModeState PhotoSwitching => GetModeState(AppMode.PhotoSwitching);

    [JsonIgnore]
    public ModeState ColorPhoto => GetModeState(AppMode.ColorPhoto);

    [JsonIgnore]
    public ModeState VideoFrames => GetModeState(AppMode.VideoFrames);

    public ModeState GetModeState(AppMode mode)
    {
        if (mode is not (AppMode.PhotoSwitching or AppMode.ColorPhoto or AppMode.VideoFrames))
        {
            return PhotoSwitching;
        }

        if (!Modes.TryGetValue(mode, out var state))
        {
            state = new ModeState();
            Modes[mode] = state;
        }

        return state;
    }
}

public sealed class ProtectedVideoExportState
{
    public List<string> InputPaths { get; set; } = [];
    public string WatermarkPath { get; set; } = "";
    public string WatermarkText { get; set; } = "JustDraw";
    public int DurationSeconds { get; set; } = 15;
    public string OutputFormat { get; set; } = "mp4";
    public string OverlayMode { get; set; } = "noise";
    public bool DeleteOriginalAfterExport { get; set; }
}

public static class StateStore
{
    private static readonly JsonSerializerOptions Options = new()
    {
        WriteIndented = true,
        Converters = { new JsonStringEnumConverter() }
    };

    public static string AppDataDirectory
    {
        get
        {
            var appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            var target = Path.Combine(appData, "JustDraw");
            Directory.CreateDirectory(target);
            return target;
        }
    }

    public static string StatePath => Path.Combine(AppDataDirectory, "justdraw_csharp_state.json");

    public static JustDrawState Load()
    {
        try
        {
            if (!File.Exists(StatePath))
            {
                return new JustDrawState();
            }

            var text = File.ReadAllText(StatePath);
            var state = JsonSerializer.Deserialize<JustDrawState>(text, Options) ?? new JustDrawState();
            _ = state.PhotoSwitching;
            _ = state.ColorPhoto;
            _ = state.VideoFrames;
            state.MosaicDownsampleFactor = Math.Clamp(state.MosaicDownsampleFactor, 4, 64);
            state.ColorBlocksStripeCount = Math.Clamp(state.ColorBlocksStripeCount, 1, 20);
            return state;
        }
        catch
        {
            return new JustDrawState();
        }
    }

    public static void Save(JustDrawState state)
    {
        try
        {
            Directory.CreateDirectory(AppDataDirectory);
            File.WriteAllText(StatePath, JsonSerializer.Serialize(state, Options));
        }
        catch
        {
            // Best effort; drawing should not be interrupted by state persistence.
        }
    }
}
