using Microsoft.Win32;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Media;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Effects;
using System.Windows.Media.Imaging;
using System.Windows.Shapes;
using System.Windows.Threading;
using Forms = System.Windows.Forms;
using MediaColor = System.Windows.Media.Color;
using MediaBrushes = System.Windows.Media.Brushes;
using IoPath = System.IO.Path;
using WpfImage = System.Windows.Controls.Image;
using WpfPoint = System.Windows.Point;
using WpfRectangle = System.Windows.Shapes.Rectangle;

namespace JustDraw.Wpf;

public partial class MainWindow : Window, IViewportController
{
    private const double MosaicMinFactor = 2.0;
    private const double MosaicMaxFactor = 128.0;

    private static readonly (double Ratio, string Label)[] CommonViewportAspectRatios =
    [
        (9.0 / 16.0, "9:16"),
        (2.0 / 3.0, "2:3"),
        (3.0 / 4.0, "3:4"),
        (1.0, "1:1"),
        (4.0 / 3.0, "4:3"),
        (3.0 / 2.0, "3:2"),
        (16.0 / 10.0, "16:10"),
        (16.0 / 9.0, "16:9"),
        (21.0 / 9.0, "21:9"),
        (32.0 / 9.0, "32:9")
    ];

    private readonly JustDrawState _state;
    private readonly ImageLibrary _imageLibrary = new();
    private readonly DispatcherTimer _timer = new() { Interval = TimeSpan.FromSeconds(1) };
    private readonly DispatcherTimer _toastTimer = new() { Interval = TimeSpan.FromSeconds(1.8) };
    private readonly DispatcherTimer _countdownTimer = new() { Interval = TimeSpan.FromSeconds(1) };
    private readonly DispatcherTimer _startupUpdateTimer = new() { Interval = TimeSpan.FromSeconds(2) };
    private readonly UpdateService _updateService = new();
    private readonly VideoExportService _videoExportService = new();
    private readonly VideoFrameCache _videoFrameCache = new();
    private readonly VideoToolsInfo _videoTools = VideoExportService.FindTools();
    private readonly Dictionary<AppMode, List<ImageEntry>> _entriesByMode = [];
    private readonly Dictionary<AppMode, int> _currentIndexByMode = [];
    private readonly Dictionary<AppMode, BitmapImage?> _sourceBitmapByMode = [];
    private readonly Dictionary<AppMode, BitmapSource?> _displayBitmapByMode = [];
    private readonly HashSet<AppMode> _loadedSources = [];
    private readonly HashSet<AppMode> _autoPromptedSourceModes = [];
    private readonly List<MediaColor> _palette = [];
    private readonly List<MediaColor> _sampledImageColors = [];
    private readonly Dictionary<MenuItem, bool> _menuCheckedStates = [];

    private bool _grayscaleDisplayEnabled;
    private bool _sampleImageColorsEnabled;
    private bool _timerPaused = true;
    private bool _timerExpiredHold;
    private bool _updateBusy;
    private bool _updateAvailable;
    private bool _videoExportBusy;
    private bool _isClosing;
    private int _videoFrameLoadVersion;
    private int _displayedVideoFrameIndex = -1;
    private int _loadingVideoFrameIndex = -1;
    private bool _videoFrameRequestActive;
    private CancellationTokenSource _videoFrameLoadCts = new();
    private int _timerRemaining;
    private int _overtimeSeconds;
    private int _countdownRemaining;
    private bool _isDraggingImage;
    private bool _viewportRefreshQueued;
    private bool _sourceSelectionPromptQueued;
    private bool _sourceSelectionPromptOpen;
    private WpfPoint _dragStart;
    private double _dragStartOffsetX;
    private double _dragStartOffsetY;

    public MainWindow()
    {
        _state = StateStore.Load();
        InitializeComponent();
        if (_state.AppMode == AppMode.VideoFrames && !_videoTools.Available)
        {
            _state.AppMode = AppMode.PhotoSwitching;
        }

        ApplyIcon();
        ApplyTheme();
        ApplySafeStartupSize();
        Topmost = _state.StayOnTop;
        _timer.Tick += Timer_Tick;
        _toastTimer.Tick += (_, _) => Toast.Visibility = Visibility.Collapsed;
        _countdownTimer.Tick += CountdownTimer_Tick;
        _startupUpdateTimer.Tick += StartupUpdateTimer_Tick;
        _timerRemaining = ActiveModeState().TimerSeconds;
        _grayscaleDisplayEnabled = _state.GrayscaleDisplayEnabled;
        _sampleImageColorsEnabled = _state.SampleImageColorsEnabled;
        _videoFrameCache.BufferSeconds = _state.VideoFrameBufferSeconds;
        GeneratePalette();
        LoadSavedSources();
        ApplyMode(_state.AppMode);
        UpdateAllUi();
        _startupUpdateTimer.Start();
    }

    public bool IsViewportAspectRatioLocked => _state.LockImageViewportAspectRatio;

    public double ViewportAspectRatio => _state.ImageViewportAspectRatio;

    public IViewportController ViewportController => this;

    public void SetViewportAspectRatio(double width, double height, bool lockAspectRatio = true)
    {
        var aspectRatio = ViewportAspectRatioLayout.CalculateAspectRatio(width, height);
        if (!Dispatcher.CheckAccess())
        {
            Dispatcher.Invoke(() => SetViewportAspectRatio(width, height, lockAspectRatio));
            return;
        }

        _state.ImageViewportAspectRatio = aspectRatio;
        _state.LockImageViewportAspectRatio = lockAspectRatio;
        UpdateAllUi();
    }

    public void SetViewportAspectRatioLock(bool enabled)
    {
        if (!Dispatcher.CheckAccess())
        {
            Dispatcher.Invoke(() => SetViewportAspectRatioLock(enabled));
            return;
        }

        _state.LockImageViewportAspectRatio = enabled;
        UpdateAllUi();
    }

    private ModeState ActiveModeState() => _state.GetModeState(_state.AppMode);

    private bool IsImageMode => _state.AppMode is AppMode.PhotoSwitching or AppMode.ColorPhoto or AppMode.VideoFrames;

    private bool IsImageLibraryMode => _state.AppMode is AppMode.PhotoSwitching or AppMode.ColorPhoto;

    private bool IsVideoFrameMode => _state.AppMode == AppMode.VideoFrames;

    private WpfImage ActiveImage => _state.AppMode switch
    {
        AppMode.ColorPhoto => ColorPhotoImage,
        AppMode.VideoFrames => VideoFrameImage,
        _ => PhotoImage
    };

    private Grid ActiveViewport => _state.AppMode switch
    {
        AppMode.ColorPhoto => ColorPhotoViewport,
        AppMode.VideoFrames => VideoFramesViewport,
        _ => PhotoViewport
    };

    private Canvas ActiveSampleColorsCanvas => _state.AppMode switch
    {
        AppMode.ColorPhoto => ColorPhotoSampleColorsCanvas,
        AppMode.VideoFrames => VideoFrameSampleColorsCanvas,
        _ => PhotoSampleColorsCanvas
    };

    private List<ImageEntry> ActiveEntries => _entriesByMode.TryGetValue(_state.AppMode, out var entries) ? entries : [];

    private ImageEntry? ActiveEntry
    {
        get
        {
            var entries = ActiveEntries;
            if (entries.Count == 0)
            {
                return null;
            }

            var index = Math.Clamp(CurrentIndex, 0, entries.Count - 1);
            return entries[index];
        }
    }

    private int CurrentIndex
    {
        get => _currentIndexByMode.TryGetValue(_state.AppMode, out var index) ? index : 0;
        set => _currentIndexByMode[_state.AppMode] = value;
    }

    private bool IsChinese => _state.UiLanguage.Equals("zh", StringComparison.OrdinalIgnoreCase);

    private string T(string en, string zh) => IsChinese ? zh : en;

    private static string FormatMosaicSize(double value) => value.ToString("0.#", CultureInfo.InvariantCulture);

    private static string FormatViewportAspectRatio(double aspectRatio)
    {
        aspectRatio = ViewportAspectRatioLayout.Normalize(aspectRatio);
        foreach (var common in CommonViewportAspectRatios)
        {
            if (Math.Abs(aspectRatio - common.Ratio) < 0.000001)
            {
                return common.Label;
            }
        }

        return $"{aspectRatio.ToString("0.###", CultureInfo.InvariantCulture)}:1";
    }

    private bool IsViewportAspectRatio(double width, double height)
    {
        var expected = ViewportAspectRatioLayout.CalculateAspectRatio(width, height);
        return Math.Abs(_state.ImageViewportAspectRatio - expected) < 0.000001;
    }

    private static bool TryParseViewportAspectRatio(string value, out double width, out double height)
    {
        width = 0;
        height = 0;
        var normalized = value.Trim()
            .Replace('：', ':')
            .Replace('x', ':')
            .Replace('X', ':')
            .Replace('/', ':');
        var parts = normalized.Split(':', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length == 1)
        {
            if (!TryParsePositiveNumber(parts[0], out width))
            {
                return false;
            }

            height = 1;
        }
        else if (parts.Length == 2)
        {
            if (!TryParsePositiveNumber(parts[0], out width) || !TryParsePositiveNumber(parts[1], out height))
            {
                return false;
            }
        }
        else
        {
            return false;
        }

        try
        {
            _ = ViewportAspectRatioLayout.CalculateAspectRatio(width, height);
            return true;
        }
        catch (ArgumentOutOfRangeException)
        {
            return false;
        }
    }

    private static bool TryParsePositiveNumber(string value, out double number)
    {
        var parsed = double.TryParse(value, NumberStyles.Float, CultureInfo.CurrentCulture, out number)
            || double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out number);
        return parsed && double.IsFinite(number) && number > 0;
    }

    private static double ClampUnit(double value) => Math.Clamp(value, 0.0, 1.0);

    private void ApplyTheme()
    {
        var accent = ParseThemeColor(_state.ThemeAccentColor);
        var background = MediaColor.FromRgb(5, 7, 9);
        var surface = MediaColor.FromRgb(18, 22, 25);
        var panel = MediaColor.FromRgb(28, 33, 37);
        var hoverAccent = AdjustThemeColor(accent, saturationFactor: 0.62, lightnessFactor: 0.74, alpha: 130);
        var separatorAccent = AdjustThemeColor(accent, saturationFactor: 0.48, lightnessFactor: 0.88, alpha: 112);
        var arrowAccent = AdjustThemeColor(accent, saturationFactor: 1.15, lightnessFactor: 1.18, alpha: 230);
        Resources["AccentBrush"] = FrozenBrush(accent);
        Resources["AccentSoftBrush"] = FrozenBrush(MediaColor.FromArgb(58, accent.R, accent.G, accent.B));
        Resources["AccentHoverBrush"] = FrozenBrush(hoverAccent);
        Resources["AccentSeparatorBrush"] = FrozenBrush(separatorAccent);
        Resources["AccentArrowBrush"] = FrozenBrush(arrowAccent);
        Resources["AppBackgroundBrush"] = FrozenBrush(background);
        Resources["SurfaceBrush"] = FrozenBrush(surface);
        Resources["PanelBrush"] = FrozenBrush(panel);
        Resources["TextBrush"] = FrozenBrush(MediaColor.FromRgb(242, 246, 247));
        Resources["MutedTextBrush"] = FrozenBrush(MediaColor.FromRgb(160, 170, 175));
        Resources["TimerBadgeBrush"] = FrozenBrush(MediaColor.FromArgb(226, 10, 12, 14));
        Resources["ToastBrush"] = FrozenBrush(MediaColor.FromArgb(238, 22, 27, 31));
        Resources[System.Windows.SystemColors.HighlightBrushKey] = Resources["AccentHoverBrush"];
        Resources[System.Windows.SystemColors.HighlightTextBrushKey] = FrozenBrush(MediaColor.FromRgb(255, 255, 255));
        Resources[System.Windows.SystemColors.ControlBrushKey] = FrozenBrush(panel);
        Resources[System.Windows.SystemColors.ControlTextBrushKey] = FrozenBrush(MediaColor.FromRgb(242, 246, 247));
        Resources[System.Windows.SystemColors.MenuBrushKey] = FrozenBrush(panel);
        Resources[System.Windows.SystemColors.MenuTextBrushKey] = FrozenBrush(MediaColor.FromRgb(242, 246, 247));
        Resources[System.Windows.SystemColors.WindowBrushKey] = FrozenBrush(panel);
        Resources[System.Windows.SystemColors.WindowTextBrushKey] = FrozenBrush(MediaColor.FromRgb(242, 246, 247));
        Resources[System.Windows.SystemColors.ActiveBorderBrushKey] = FrozenBrush(accent);
        Resources[System.Windows.SystemColors.InactiveBorderBrushKey] = FrozenBrush(accent);
        Background = (System.Windows.Media.Brush)Resources["AppBackgroundBrush"];
        RootSurface?.SetValue(BackgroundProperty, Resources["AppBackgroundBrush"]);
        PhotoSwitchingPage?.SetValue(BackgroundProperty, Resources["AppBackgroundBrush"]);
        PhotoViewport?.SetValue(BackgroundProperty, Resources["AppBackgroundBrush"]);
        ColorBlocksPage?.SetValue(BackgroundProperty, Resources["AppBackgroundBrush"]);
        ColorBlocksCanvas?.SetValue(BackgroundProperty, Resources["AppBackgroundBrush"]);
        ColorPhotoPage?.SetValue(BackgroundProperty, Resources["AppBackgroundBrush"]);
        ColorPhotoViewport?.SetValue(BackgroundProperty, Resources["AppBackgroundBrush"]);
        VideoFramesPage?.SetValue(BackgroundProperty, Resources["AppBackgroundBrush"]);
        VideoFramesViewport?.SetValue(BackgroundProperty, Resources["AppBackgroundBrush"]);
        ApplyMenuTheme();
    }

    private static SolidColorBrush FrozenBrush(MediaColor color)
    {
        var brush = new SolidColorBrush(color);
        brush.Freeze();
        return brush;
    }

    private static MediaColor AdjustThemeColor(MediaColor color, double saturationFactor, double lightnessFactor, byte alpha)
    {
        RgbToHsl(color, out var hue, out var saturation, out var lightness);
        saturation = ClampUnit(saturation * saturationFactor);
        lightness = ClampUnit(lightness * lightnessFactor);
        var adjusted = HslToRgb(hue, saturation, lightness);
        return MediaColor.FromArgb(alpha, adjusted.R, adjusted.G, adjusted.B);
    }

    private static void RgbToHsl(MediaColor color, out double hue, out double saturation, out double lightness)
    {
        var r = color.R / 255.0;
        var g = color.G / 255.0;
        var b = color.B / 255.0;
        var max = Math.Max(r, Math.Max(g, b));
        var min = Math.Min(r, Math.Min(g, b));
        var delta = max - min;

        lightness = (max + min) / 2.0;
        if (delta == 0)
        {
            hue = 0;
            saturation = 0;
            return;
        }

        saturation = lightness > 0.5
            ? delta / (2.0 - max - min)
            : delta / (max + min);

        if (max == r)
        {
            hue = (g - b) / delta + (g < b ? 6 : 0);
        }
        else if (max == g)
        {
            hue = (b - r) / delta + 2;
        }
        else
        {
            hue = (r - g) / delta + 4;
        }

        hue /= 6.0;
    }

    private static MediaColor HslToRgb(double hue, double saturation, double lightness)
    {
        if (saturation == 0)
        {
            var gray = ToByte(lightness);
            return MediaColor.FromRgb(gray, gray, gray);
        }

        var q = lightness < 0.5
            ? lightness * (1 + saturation)
            : lightness + saturation - lightness * saturation;
        var p = 2 * lightness - q;

        return MediaColor.FromRgb(
            ToByte(HueToRgb(p, q, hue + 1.0 / 3.0)),
            ToByte(HueToRgb(p, q, hue)),
            ToByte(HueToRgb(p, q, hue - 1.0 / 3.0)));
    }

    private static double HueToRgb(double p, double q, double t)
    {
        if (t < 0)
        {
            t += 1;
        }
        else if (t > 1)
        {
            t -= 1;
        }

        if (t < 1.0 / 6.0)
        {
            return p + (q - p) * 6 * t;
        }

        if (t < 1.0 / 2.0)
        {
            return q;
        }

        if (t < 2.0 / 3.0)
        {
            return p + (q - p) * (2.0 / 3.0 - t) * 6;
        }

        return p;
    }

    private static byte ToByte(double value) => (byte)Math.Round(ClampUnit(value) * 255);

    private static MediaColor ParseThemeColor(string value)
    {
        try
        {
            if (TryParseThemeColor(value, out var color))
            {
                return color;
            }
        }
        catch
        {
            // Fall back to default accent.
        }

        return MediaColor.FromRgb(14, 165, 168);
    }

    private static bool TryParseThemeColor(string value, out MediaColor color)
    {
        color = default;
        try
        {
            var converted = System.Windows.Media.ColorConverter.ConvertFromString(string.IsNullOrWhiteSpace(value) ? "#0EA5A8" : value.Trim());
            if (converted is not MediaColor parsed)
            {
                return false;
            }

            color = MediaColor.FromRgb(parsed.R, parsed.G, parsed.B);
            return true;
        }
        catch
        {
            return false;
        }
    }

    private static string ColorToHex(MediaColor color) => $"#{color.R:X2}{color.G:X2}{color.B:X2}";

    private void ApplyMenuTheme()
    {
        if (TopMenu is null)
        {
            return;
        }

        TopMenu.Background = (System.Windows.Media.Brush)Resources["SurfaceBrush"];
        TopMenu.Foreground = (System.Windows.Media.Brush)Resources["TextBrush"];
        foreach (var item in EnumerateMenuItems(TopMenu.Items))
        {
            StyleMenuItem(item);
        }
    }

    private IEnumerable<MenuItem> EnumerateMenuItems(ItemCollection items)
    {
        foreach (var rawItem in items)
        {
            if (rawItem is not MenuItem item)
            {
                continue;
            }

            yield return item;
            foreach (var child in EnumerateMenuItems(item.Items))
            {
                yield return child;
            }
        }
    }

    private void StyleMenuItem(MenuItem item)
    {
        var isChecked = _menuCheckedStates.TryGetValue(item, out var checkedState) && checkedState;
        var isUpdatePrompt = IsUpdatePromptItem(item);
        var isTopLevel = item.Parent is Menu;
        item.Background = isUpdatePrompt
            ? (System.Windows.Media.Brush)Resources["AccentSoftBrush"]
            : DefaultMenuItemBackground(item);
        item.Foreground = isUpdatePrompt
            ? (System.Windows.Media.Brush)Resources["AccentArrowBrush"]
            : (System.Windows.Media.Brush)Resources["TextBrush"];
        item.IsCheckable = false;
        item.IsChecked = false;
        item.BorderBrush = isUpdatePrompt
            ? (System.Windows.Media.Brush)Resources["AccentBrush"]
            : System.Windows.Media.Brushes.Transparent;
        item.BorderThickness = isUpdatePrompt ? new Thickness(1) : new Thickness(0);
        item.Icon = isTopLevel ? null : CreateMenuCheckIcon(isChecked);
        item.Padding = isTopLevel ? new Thickness(10, 4, 10, 4) : new Thickness(10, 6, 10, 6);
        item.Resources[System.Windows.SystemColors.HighlightBrushKey] = Resources["AccentHoverBrush"];
        item.Resources[System.Windows.SystemColors.HighlightTextBrushKey] = Resources["TextBrush"];
        item.Resources[System.Windows.SystemColors.MenuBrushKey] = Resources["PanelBrush"];
        item.Resources[System.Windows.SystemColors.MenuTextBrushKey] = Resources["TextBrush"];
        foreach (var separator in item.Items.OfType<Separator>())
        {
            StyleMenuSeparator(separator);
        }
        item.SubmenuOpened -= MenuItem_SubmenuOpened;
        item.SubmenuOpened += MenuItem_SubmenuOpened;
        item.MouseEnter -= MenuItem_MouseEnter;
        item.MouseEnter += MenuItem_MouseEnter;
        item.MouseLeave -= MenuItem_MouseLeave;
        item.MouseLeave += MenuItem_MouseLeave;
    }

    private void MenuItem_MouseEnter(object sender, System.Windows.Input.MouseEventArgs e)
    {
        if (sender is not MenuItem item || !item.IsEnabled)
        {
            return;
        }

        item.Background = (System.Windows.Media.Brush)Resources["AccentHoverBrush"];
        item.Foreground = (System.Windows.Media.Brush)Resources["TextBrush"];
    }

    private void MenuItem_MouseLeave(object sender, System.Windows.Input.MouseEventArgs e)
    {
        if (sender is not MenuItem item)
        {
            return;
        }

        if (IsUpdatePromptItem(item))
        {
            item.Background = (System.Windows.Media.Brush)Resources["AccentSoftBrush"];
            item.Foreground = (System.Windows.Media.Brush)Resources["AccentArrowBrush"];
            return;
        }

        item.Background = DefaultMenuItemBackground(item);
        item.Foreground = (System.Windows.Media.Brush)Resources["TextBrush"];
    }

    private void StyleMenuSeparator(Separator separator)
    {
        separator.Background = (System.Windows.Media.Brush)Resources["AccentSeparatorBrush"];
        separator.BorderBrush = (System.Windows.Media.Brush)Resources["AccentSeparatorBrush"];
        separator.Margin = new Thickness(28, 5, 8, 5);
        separator.Height = 1;
    }

    private bool IsUpdatePromptItem(MenuItem item) => _updateAvailable && (item == SettingsMenu || item == CheckForUpdatesItem);

    private System.Windows.Media.Brush DefaultMenuItemBackground(MenuItem item) =>
        item.Parent is Menu
            ? (System.Windows.Media.Brush)Resources["SurfaceBrush"]
            : (System.Windows.Media.Brush)Resources["PanelBrush"];

    private FrameworkElement CreateMenuCheckIcon(bool isChecked)
    {
        var container = new Grid
        {
            Width = 18,
            Height = 16,
            Margin = new Thickness(0, 0, 6, 0),
            HorizontalAlignment = System.Windows.HorizontalAlignment.Center,
            VerticalAlignment = System.Windows.VerticalAlignment.Center,
            SnapsToDevicePixels = true
        };

        if (!isChecked)
        {
            return container;
        }

        var check = new System.Windows.Shapes.Path
        {
            Data = Geometry.Parse("M 2 6 L 5 9 L 11 2"),
            Stroke = (System.Windows.Media.Brush)Resources["AccentBrush"],
            StrokeThickness = 2,
            StrokeStartLineCap = PenLineCap.Round,
            StrokeEndLineCap = PenLineCap.Round,
            StrokeLineJoin = PenLineJoin.Round,
            Width = 13,
            Height = 11,
            Stretch = Stretch.Uniform,
            HorizontalAlignment = System.Windows.HorizontalAlignment.Center,
            VerticalAlignment = System.Windows.VerticalAlignment.Center,
            Margin = new Thickness(0, 1, 0, 0),
            SnapsToDevicePixels = true
        };
        container.Children.Add(check);
        return container;
    }

    private void MenuItem_SubmenuOpened(object sender, RoutedEventArgs e)
    {
        if (sender is not MenuItem item)
        {
            return;
        }

        Dispatcher.BeginInvoke(() => ApplySubmenuPopupTheme(item), DispatcherPriority.Loaded);
        foreach (var child in EnumerateMenuItems(item.Items))
        {
            StyleMenuItem(child);
        }
    }

    private void ApplySubmenuPopupTheme(MenuItem item)
    {
        if (item.Template?.FindName("PART_Popup", item) is not Popup popup ||
            popup.Child is not DependencyObject popupChild)
        {
            return;
        }

        var border = popupChild as Border ?? FindVisualChildren<Border>(popupChild).FirstOrDefault();
        if (border is null)
        {
            return;
        }

        border.BorderBrush = (System.Windows.Media.Brush)Resources["AccentBrush"];
        border.BorderThickness = new Thickness(1);
        border.Background = (System.Windows.Media.Brush)Resources["PanelBrush"];
        border.SnapsToDevicePixels = true;
        foreach (var separator in FindVisualChildren<Separator>(border))
        {
            StyleMenuSeparator(separator);
        }
    }

    private static IEnumerable<T> FindVisualChildren<T>(DependencyObject parent) where T : DependencyObject
    {
        var childCount = VisualTreeHelper.GetChildrenCount(parent);
        for (var i = 0; i < childCount; i++)
        {
            var child = VisualTreeHelper.GetChild(parent, i);
            if (child is T typedChild)
            {
                yield return typedChild;
            }

            foreach (var nestedChild in FindVisualChildren<T>(child))
            {
                yield return nestedChild;
            }
        }
    }

    private void SetMenuChecked(MenuItem item, bool isChecked)
    {
        _menuCheckedStates[item] = isChecked;
    }

    private void ApplySafeStartupSize()
    {
        var workArea = SystemParameters.WorkArea;
        var maxWidth = Math.Max(320, workArea.Width - 40);
        var maxHeight = Math.Max(320, workArea.Height - 40);
        Width = Math.Clamp(_state.WindowWidth, 320, maxWidth);
        Height = Math.Clamp(_state.WindowHeight, 320, maxHeight);
    }

    private void ApplyViewportLayout()
    {
        var activeViewport = IsImageMode ? ActiveViewport : null;
        foreach (var viewport in new[] { PhotoViewport, ColorPhotoViewport, VideoFramesViewport })
        {
            if (!ReferenceEquals(viewport, activeViewport) || !_state.LockImageViewportAspectRatio)
            {
                ResetViewportLayout(viewport);
            }
        }

        if (activeViewport is not null && _state.LockImageViewportAspectRatio)
        {
            var (width, height) = ViewportAspectRatioLayout.Fit(
                RootSurface.ActualWidth,
                RootSurface.ActualHeight,
                _state.ImageViewportAspectRatio);
            if (width > 0 && height > 0)
            {
                activeViewport.HorizontalAlignment = System.Windows.HorizontalAlignment.Center;
                activeViewport.VerticalAlignment = System.Windows.VerticalAlignment.Center;
                activeViewport.Width = width;
                activeViewport.Height = height;
            }
        }

        QueueViewportRefresh();
    }

    private static void ResetViewportLayout(FrameworkElement viewport)
    {
        viewport.ClearValue(WidthProperty);
        viewport.ClearValue(HeightProperty);
        viewport.HorizontalAlignment = System.Windows.HorizontalAlignment.Stretch;
        viewport.VerticalAlignment = System.Windows.VerticalAlignment.Stretch;
    }

    private void QueueViewportRefresh()
    {
        if (_viewportRefreshQueued || _isClosing)
        {
            return;
        }

        _viewportRefreshQueued = true;
        Dispatcher.BeginInvoke(new Action(() =>
        {
            _viewportRefreshQueued = false;
            RenderSampledImageColors();
            if (IsImageMode && ActiveImage.Source is not null)
            {
                ApplyImageViewState();
            }
        }), DispatcherPriority.Loaded);
    }

    private void Window_Loaded(object sender, RoutedEventArgs e)
    {
        if (WindowState == WindowState.Normal)
        {
            Left = Math.Max(SystemParameters.WorkArea.Left, Math.Min(Left, SystemParameters.WorkArea.Right - ActualWidth));
            Top = Math.Max(SystemParameters.WorkArea.Top, Math.Min(Top, SystemParameters.WorkArea.Bottom - ActualHeight));
        }

        ApplyViewportLayout();
        QueueSourceSelectionIfNeeded();
    }

    private void RootSurface_SizeChanged(object sender, SizeChangedEventArgs e)
    {
        ApplyViewportLayout();
    }

    private void QueueSourceSelectionIfNeeded()
    {
        if (!IsLoaded || _sourceSelectionPromptQueued || _sourceSelectionPromptOpen || _autoPromptedSourceModes.Contains(_state.AppMode) || !NeedsSourceSelection())
        {
            return;
        }

        _sourceSelectionPromptQueued = true;
        Dispatcher.BeginInvoke(new Action(PromptForSourceSelectionIfNeeded), DispatcherPriority.ApplicationIdle);
    }

    private void PromptForSourceSelectionIfNeeded()
    {
        _sourceSelectionPromptQueued = false;
        if (_sourceSelectionPromptOpen || !NeedsSourceSelection())
        {
            return;
        }

        _sourceSelectionPromptOpen = true;
        _autoPromptedSourceModes.Add(_state.AppMode);
        try
        {
            SetImageFolder_Click(this, new RoutedEventArgs());
        }
        finally
        {
            _sourceSelectionPromptOpen = false;
        }
    }

    private bool NeedsSourceSelection()
    {
        if (!IsImageMode)
        {
            return false;
        }

        var source = ActiveModeState().ImageRootPath;
        if (IsVideoFrameMode)
        {
            return _videoTools.Available && (string.IsNullOrWhiteSpace(source) || !File.Exists(source));
        }

        return IsImageLibraryMode && (string.IsNullOrWhiteSpace(source) || (!Directory.Exists(source) && !File.Exists(source)));
    }

    private void ApplyIcon()
    {
        var iconPath = System.IO.Path.Combine(AppContext.BaseDirectory, "images", "icon.png");
        if (!File.Exists(iconPath))
        {
            return;
        }

        try
        {
            Icon = new BitmapImage(new Uri(iconPath));
        }
        catch
        {
            // Icon is cosmetic.
        }
    }

    private void LoadSavedSources()
    {
        LoadSourceForMode(AppMode.PhotoSwitching, showToast: false);
        LoadSourceForMode(AppMode.ColorPhoto, showToast: false);
        if (_videoTools.Available)
        {
            LoadSourceForMode(AppMode.VideoFrames, showToast: false);
        }
    }

    private void LoadSourceForMode(AppMode mode, bool showToast)
    {
        var modeState = _state.GetModeState(mode);
        var source = modeState.ImageRootPath;
        if (string.IsNullOrWhiteSpace(source))
        {
            return;
        }

        if (mode == AppMode.VideoFrames)
        {
            if (_videoTools.Available && File.Exists(source))
            {
                _loadedSources.Add(mode);
            }

            return;
        }

        var pathState = modeState.GetPathPlaybackState(source);
        var entries = _imageLibrary.Load(source);
        RestoreOrder(pathState, entries);
        _entriesByMode[mode] = entries;
        _loadedSources.Add(mode);
        RememberRecentPath(modeState, source);

        var index = 0;
        if (!string.IsNullOrWhiteSpace(pathState.LastImagePath))
        {
            var found = entries.FindIndex(e => string.Equals(e.Path, pathState.LastImagePath, StringComparison.OrdinalIgnoreCase));
            if (found >= 0)
            {
                index = found;
            }
        }

        _currentIndexByMode[mode] = index;
        if (showToast)
        {
            ShowToast(entries.Count == 0 ? T("No images found", "没有找到图片") : T("Loaded ", "已载入 ") + entries.Count + T(" images", " 张图片"));
        }
    }

    private static void RememberRecentPath(ModeState modeState, string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return;
        }

        modeState.RecentPaths.RemoveAll(item => item.Equals(path, StringComparison.OrdinalIgnoreCase));
        modeState.RecentPaths.Insert(0, path);
        if (modeState.RecentPaths.Count > 10)
        {
            modeState.RecentPaths.RemoveRange(10, modeState.RecentPaths.Count - 10);
        }
    }

    private void RebuildRecentPathsMenu()
    {
        RecentPathsMenu.Items.Clear();
        var recent = ActiveModeState().RecentPaths.Where(path => Directory.Exists(path) || File.Exists(path)).Take(10).ToList();
        if (recent.Count == 0)
        {
            RecentPathsMenu.Items.Add(new MenuItem { Header = T("No Recent Paths", "暂无最近路径"), IsEnabled = false });
            return;
        }

        foreach (var path in recent)
        {
            var item = new MenuItem { Header = path };
            item.Click += (_, _) =>
            {
                if (IsVideoFrameMode)
                {
                    _ = OpenVideoFrameSourceAsync(path, showToast: true);
                    return;
                }

                OpenImageSource(path);
            };
            RecentPathsMenu.Items.Add(item);
        }
    }

    private static void RestoreOrder(PathPlaybackState pathState, List<ImageEntry> entries)
    {
        if (entries.Count == 0)
        {
            return;
        }

        if (!pathState.UseCustomImageOrder || pathState.ImageOrder.Count == 0)
        {
            ImageLibrary.SortNatural(entries);
            return;
        }

        var lookup = entries.ToDictionary(e => e.Path, StringComparer.OrdinalIgnoreCase);
        var ordered = new List<ImageEntry>();
        foreach (var savedPath in pathState.ImageOrder)
        {
            if (lookup.Remove(savedPath, out var entry))
            {
                ordered.Add(entry);
            }
        }

        var newEntries = lookup.Values.ToList();
        ImageLibrary.SortNatural(newEntries);
        ordered.AddRange(newEntries);
        entries.Clear();
        entries.AddRange(ordered);
    }

    private void ApplyMode(AppMode mode)
    {
        SaveCurrentImageViewState();
        var previousMode = _state.AppMode;
        _state.AppMode = mode;
        if (previousMode != mode)
        {
            _autoPromptedSourceModes.Remove(mode);
        }

        PhotoSwitchingPage.Visibility = mode == AppMode.PhotoSwitching ? Visibility.Visible : Visibility.Collapsed;
        ColorBlocksPage.Visibility = mode == AppMode.ColorBlocks ? Visibility.Visible : Visibility.Collapsed;
        ColorPhotoPage.Visibility = mode == AppMode.ColorPhoto ? Visibility.Visible : Visibility.Collapsed;
        VideoFramesPage.Visibility = mode == AppMode.VideoFrames ? Visibility.Visible : Visibility.Collapsed;
        FileMenu.Visibility = IsImageMode ? Visibility.Visible : Visibility.Collapsed;
        TimerMenu.Visibility = mode == AppMode.PhotoSwitching ? Visibility.Visible : Visibility.Collapsed;
        ColorToolsMenu.Visibility = mode == AppMode.ColorBlocks ? Visibility.Visible : Visibility.Collapsed;
        MosaicMenu.Visibility = IsImageMode ? Visibility.Visible : Visibility.Collapsed;
        _timerRemaining = ActiveModeState().TimerSeconds;
        _timerExpiredHold = false;
        _overtimeSeconds = 0;
        _timerPaused = mode != AppMode.PhotoSwitching || _timerPaused;

        if (IsImageLibraryMode && !_loadedSources.Contains(mode))
        {
            LoadSourceForMode(mode, showToast: false);
        }

        var activeVideoSource = ActiveModeState().ImageRootPath;
        var pendingVideoOpen = mode == AppMode.VideoFrames
            && !string.IsNullOrWhiteSpace(activeVideoSource)
            && File.Exists(activeVideoSource)
            && _videoFrameCache.CurrentVideo?.Path != activeVideoSource;
        if (pendingVideoOpen)
        {
            _ = OpenSavedVideoFrameSourceAsync();
        }

        if (!pendingVideoOpen)
        {
            RefreshActiveView();
        }
        else
        {
            VideoFrameEmptyText.Visibility = Visibility.Collapsed;
            VideoFrameBadge.Visibility = Visibility.Visible;
            VideoFrameText.Text = T("Loading video...", "正在载入视频...");
        }

        UpdateAllUi();
        QueueSourceSelectionIfNeeded();
    }

    private void RefreshActiveView()
    {
        if (_state.AppMode == AppMode.ColorBlocks)
        {
            ClearSampledImageColors();
            RenderColorBlocks();
            return;
        }

        if (IsVideoFrameMode)
        {
            RequestVideoFrameDisplay();
            return;
        }

        LoadCurrentImage();
    }

    private void OpenImageSource(string sourcePath)
    {
        var modeState = ActiveModeState();
        modeState.ImageRootPath = sourcePath;
        _autoPromptedSourceModes.Remove(_state.AppMode);
        _loadedSources.Remove(_state.AppMode);
        LoadSourceForMode(_state.AppMode, showToast: true);
        RefreshActiveView();
        UpdateAllUi();
    }

    private async Task OpenSavedVideoFrameSourceAsync()
    {
        var source = ActiveModeState().ImageRootPath;
        if (!_videoTools.Available || string.IsNullOrWhiteSpace(source) || !File.Exists(source))
        {
            return;
        }

        await OpenVideoFrameSourceAsync(source, showToast: false);
    }

    private async Task OpenVideoFrameSourceAsync(string sourcePath, bool showToast)
    {
        if (!_videoTools.Available)
        {
            return;
        }

        try
        {
            CancelVideoFrameLoad();
            var info = await _videoFrameCache.OpenAsync(_videoTools, sourcePath);
            var modeState = _state.GetModeState(AppMode.VideoFrames);
            modeState.ImageRootPath = sourcePath;
            _autoPromptedSourceModes.Remove(AppMode.VideoFrames);
            modeState.LastImagePath = sourcePath;
            var pathState = modeState.GetPathPlaybackState(sourcePath);
            pathState.LastImagePath = sourcePath;
            modeState.VideoFrameIndex = Math.Clamp(pathState.VideoFrameIndex, 0, info.FrameCount - 1);
            pathState.VideoFrameIndex = modeState.VideoFrameIndex;
            _currentIndexByMode[AppMode.VideoFrames] = modeState.VideoFrameIndex;
            _entriesByMode.Remove(AppMode.VideoFrames);
            _sourceBitmapByMode.Remove(AppMode.VideoFrames);
            _displayBitmapByMode.Remove(AppMode.VideoFrames);
            _displayedVideoFrameIndex = -1;
            _loadedSources.Add(AppMode.VideoFrames);
            RememberRecentPath(modeState, sourcePath);
            if (showToast)
            {
                ShowToast(T("Video loaded: ", "视频已载入：") + IoPath.GetFileName(sourcePath));
            }

            if (IsVideoFrameMode)
            {
                RequestVideoFrameDisplay();
            }
        }
        catch (Exception ex)
        {
            ShowToast(T("Cannot open video: ", "无法打开视频：") + ex.Message);
        }
        finally
        {
            UpdateAllUi();
        }
    }

    private void RequestVideoFrameDisplay()
    {
        if (_isClosing || !IsVideoFrameMode)
        {
            return;
        }

        var targetIndex = NormalizeTargetVideoFrameIndex();
        if (targetIndex < 0)
        {
            return;
        }

        if (targetIndex != _displayedVideoFrameIndex && targetIndex != _loadingVideoFrameIndex)
        {
            _videoFrameLoadCts.Cancel();
        }

        if (_videoFrameRequestActive)
        {
            return;
        }

        _videoFrameRequestActive = true;
        _ = ProcessVideoFrameRequestsAsync();
    }

    private async Task ProcessVideoFrameRequestsAsync()
    {
        var canRestart = true;
        try
        {
            while (!_isClosing && IsVideoFrameMode)
            {
                var targetIndex = NormalizeTargetVideoFrameIndex();
                if (targetIndex < 0 || targetIndex == _displayedVideoFrameIndex)
                {
                    break;
                }

                var loaded = await LoadTargetVideoFrameAsync(targetIndex);
                if (!loaded)
                {
                    canRestart = NormalizeTargetVideoFrameIndex() != targetIndex;
                    break;
                }

                if (NormalizeTargetVideoFrameIndex() == _displayedVideoFrameIndex)
                {
                    break;
                }
            }
        }
        finally
        {
            _videoFrameRequestActive = false;
            if (canRestart &&
                !_isClosing &&
                IsVideoFrameMode &&
                NormalizeTargetVideoFrameIndex() >= 0 &&
                NormalizeTargetVideoFrameIndex() != _displayedVideoFrameIndex)
            {
                RequestVideoFrameDisplay();
            }
        }
    }

    private int NormalizeTargetVideoFrameIndex()
    {
        if (_isClosing || !IsVideoFrameMode)
        {
            return -1;
        }

        var video = _videoFrameCache.CurrentVideo;
        if (video is null)
        {
            ActiveImage.Source = null;
            VideoFrameEmptyText.Visibility = Visibility.Visible;
            VideoFrameBadge.Visibility = Visibility.Collapsed;
            ClearSampledImageColors();
            _displayedVideoFrameIndex = -1;
            _loadingVideoFrameIndex = -1;
            return -1;
        }

        var modeState = ActiveModeState();
        var frameIndex = Math.Clamp(modeState.VideoFrameIndex, 0, video.FrameCount - 1);
        modeState.VideoFrameIndex = frameIndex;
        modeState.GetPathPlaybackState(modeState.ImageRootPath).VideoFrameIndex = frameIndex;
        CurrentIndex = frameIndex;
        return frameIndex;
    }

    private async Task<bool> LoadTargetVideoFrameAsync(int frameIndex)
    {
        var video = _videoFrameCache.CurrentVideo;
        if (_isClosing || !IsVideoFrameMode || video is null)
        {
            return false;
        }

        var version = ++_videoFrameLoadVersion;
        _videoFrameLoadCts.Cancel();
        _videoFrameLoadCts = new CancellationTokenSource();
        var token = _videoFrameLoadCts.Token;
        _loadingVideoFrameIndex = frameIndex;
        VideoFrameText.Text = T("Loading frame ", "正在载入帧 ") + (frameIndex + 1).ToString(CultureInfo.InvariantCulture) + " / " + video.FrameCount.ToString(CultureInfo.InvariantCulture);
        VideoFrameBadge.Visibility = Visibility.Visible;

        try
        {
            var path = await _videoFrameCache.GetFrameForDisplayAsync(frameIndex, token);
            if (token.IsCancellationRequested || version != _videoFrameLoadVersion || _isClosing || !IsVideoFrameMode || NormalizeTargetVideoFrameIndex() != frameIndex)
            {
                return true;
            }

            var bitmap = LoadBitmap(path);
            _sourceBitmapByMode[AppMode.VideoFrames] = bitmap;
            _displayedVideoFrameIndex = frameIndex;
            ApplyImageEffects();
            ApplyImageViewState();
            QueueImageViewStateClamp();
            ResampleImageColorsIfEnabled();
            VideoFrameEmptyText.Visibility = Visibility.Collapsed;
            UpdateVideoFrameText();
            _videoFrameCache.PreloadAround(frameIndex);
            return true;
        }
        catch (OperationCanceledException)
        {
            // Newer frame request won.
            return true;
        }
        catch (Exception ex)
        {
            ShowToast(T("Cannot load frame: ", "无法载入帧：") + ex.Message);
            return false;
        }
        finally
        {
            if (_loadingVideoFrameIndex == frameIndex)
            {
                _loadingVideoFrameIndex = -1;
            }
        }
    }

    private static BitmapImage LoadBitmap(string path)
    {
        var bitmap = new BitmapImage();
        bitmap.BeginInit();
        bitmap.CacheOption = BitmapCacheOption.OnLoad;
        bitmap.UriSource = new Uri(path);
        bitmap.CreateOptions = BitmapCreateOptions.IgnoreColorProfile;
        bitmap.EndInit();
        bitmap.Freeze();
        return bitmap;
    }

    private void CancelVideoFrameLoad()
    {
        _videoFrameLoadVersion++;
        _videoFrameLoadCts.Cancel();
        _videoFrameCache.CancelPreload();
        _loadingVideoFrameIndex = -1;
    }

    private void UpdateVideoFrameText()
    {
        var video = _videoFrameCache.CurrentVideo;
        if (video is null)
        {
            VideoFrameBadge.Visibility = Visibility.Collapsed;
            return;
        }

        var frame = Math.Clamp(ActiveModeState().VideoFrameIndex, 0, video.FrameCount - 1);
        var prefix = frame != _displayedVideoFrameIndex
            ? T("Loading frame ", "正在载入帧 ")
            : T("Frame ", "帧 ");
        VideoFrameText.Text = prefix + (frame + 1).ToString(CultureInfo.InvariantCulture) + " / " + video.FrameCount.ToString(CultureInfo.InvariantCulture);
        VideoFrameBadge.Visibility = Visibility.Visible;
    }

    private void LoadCurrentImage()
    {
        if (IsVideoFrameMode)
        {
            RequestVideoFrameDisplay();
            return;
        }

        var entry = ActiveEntry;
        if (entry is null)
        {
            ActiveImage.Source = null;
            PhotoEmptyText.Visibility = _state.AppMode == AppMode.PhotoSwitching ? Visibility.Visible : Visibility.Collapsed;
            ColorPhotoEmptyText.Visibility = _state.AppMode == AppMode.ColorPhoto ? Visibility.Visible : Visibility.Collapsed;
            return;
        }

        try
        {
            var bitmap = LoadBitmap(entry.Path);
            _sourceBitmapByMode[_state.AppMode] = bitmap;
            var modeState = ActiveModeState();
            modeState.LastImagePath = entry.Path;
            modeState.GetPathPlaybackState(modeState.ImageRootPath).LastImagePath = entry.Path;
            ApplyImageEffects();
            ApplyImageViewState();
            QueueImageViewStateClamp();
            ResampleImageColorsIfEnabled();
            PhotoEmptyText.Visibility = Visibility.Collapsed;
            ColorPhotoEmptyText.Visibility = Visibility.Collapsed;
        }
        catch
        {
            ShowToast("Cannot open image");
        }
    }

    private void ApplyImageEffects()
    {
        if (!IsImageMode)
        {
            return;
        }

        if (!_sourceBitmapByMode.TryGetValue(_state.AppMode, out var bitmap) || bitmap is null)
        {
            return;
        }

        BitmapSource source = bitmap;
        if (ActiveModeState().MosaicEnabled)
        {
            source = CreateMosaic(source, _state.MosaicDownsampleFactor);
        }

        if (_grayscaleDisplayEnabled)
        {
            source = CreateGrayscale(source);
        }

        _displayBitmapByMode[_state.AppMode] = source;
        ActiveImage.Source = source;
        RenderSampledImageColors();
    }

    private static BitmapSource CreateGrayscale(BitmapSource source)
    {
        var converted = new FormatConvertedBitmap(source, PixelFormats.Gray8, null, 0);
        converted.Freeze();
        return converted;
    }

    private static BitmapSource CreateMosaic(BitmapSource source, double factor)
    {
        factor = Math.Clamp(factor, MosaicMinFactor, MosaicMaxFactor);
        var smallWidth = Math.Max(8, (int)Math.Round(source.PixelWidth / factor));
        var smallHeight = Math.Max(8, (int)Math.Round(source.PixelHeight / factor));
        var downsampled = new TransformedBitmap(source, new ScaleTransform((double)smallWidth / source.PixelWidth, (double)smallHeight / source.PixelHeight));
        downsampled.Freeze();
        var upsampled = new TransformedBitmap(downsampled, new ScaleTransform((double)source.PixelWidth / smallWidth, (double)source.PixelHeight / smallHeight));
        upsampled.Freeze();
        return upsampled;
    }

    private void ApplyImageViewState()
    {
        var state = GetCurrentImageViewState();
        ClampImageViewState(state);
        var transformGroup = new TransformGroup();
        transformGroup.Children.Add(new ScaleTransform(
            (_state.FlipHorizontal ? -1 : 1) * state.Scale,
            (_state.FlipVertical ? -1 : 1) * state.Scale));
        transformGroup.Children.Add(new RotateTransform(state.Rotation));
        transformGroup.Children.Add(new TranslateTransform(state.OffsetX, state.OffsetY));
        ActiveImage.RenderTransform = transformGroup;
    }

    private void QueueImageViewStateClamp()
    {
        Dispatcher.BeginInvoke(new Action(ApplyImageViewState), DispatcherPriority.Loaded);
    }

    private void ClampImageViewState(ImageViewState state)
    {
        if (!IsImageMode || ActiveImage.Source is null)
        {
            return;
        }

        state.Scale = Math.Clamp(state.Scale, 1.0, 8.0);
        var imageWidth = ActiveImage.RenderSize.Width;
        var imageHeight = ActiveImage.RenderSize.Height;
        if (imageWidth <= 0 || imageHeight <= 0)
        {
            imageWidth = ActiveImage.ActualWidth;
            imageHeight = ActiveImage.ActualHeight;
        }

        var viewportWidth = ActiveViewport.ActualWidth;
        var viewportHeight = ActiveViewport.ActualHeight;
        if (imageWidth <= 0 || imageHeight <= 0 || viewportWidth <= 0 || viewportHeight <= 0)
        {
            return;
        }

        var displayedWidth = imageWidth * state.Scale;
        var displayedHeight = imageHeight * state.Scale;
        if (NormalizeRotation(state.Rotation) is 90 or 270)
        {
            (displayedWidth, displayedHeight) = (displayedHeight, displayedWidth);
        }

        var maxOffsetX = Math.Max(0, (displayedWidth - viewportWidth) / 2);
        var maxOffsetY = Math.Max(0, (displayedHeight - viewportHeight) / 2);
        state.OffsetX = Math.Clamp(state.OffsetX, -maxOffsetX, maxOffsetX);
        state.OffsetY = Math.Clamp(state.OffsetY, -maxOffsetY, maxOffsetY);
    }

    private ImageViewState GetCurrentImageViewState()
    {
        var key = GetCurrentViewStateKey();
        if (string.IsNullOrWhiteSpace(key))
        {
            return new ImageViewState();
        }

        var modeState = ActiveModeState();
        if (!modeState.ImageViewStates.TryGetValue(key, out var state))
        {
            state = new ImageViewState();
            modeState.ImageViewStates[key] = state;
        }

        return state;
    }

    private string GetCurrentViewStateKey()
    {
        if (IsVideoFrameMode)
        {
            return ActiveModeState().ImageRootPath;
        }

        return ActiveEntry?.Path ?? "";
    }

    private void SaveCurrentImageViewState()
    {
        if (!IsImageMode || (!IsVideoFrameMode && ActiveEntry is null))
        {
            return;
        }

        var state = GetCurrentImageViewState();
        if (ActiveImage.RenderTransform is not TransformGroup group)
        {
            return;
        }

        foreach (var transform in group.Children)
        {
            switch (transform)
            {
                case ScaleTransform scale:
                    state.Scale = Math.Max(0.05, Math.Abs(scale.ScaleX));
                    break;
                case TranslateTransform translate:
                    state.OffsetX = translate.X;
                    state.OffsetY = translate.Y;
                    break;
                case RotateTransform rotate:
                    state.Rotation = NormalizeRotation((int)Math.Round(rotate.Angle));
                    break;
            }
        }
    }

    private static int NormalizeRotation(int value)
    {
        value %= 360;
        if (value < 0)
        {
            value += 360;
        }

        return value - value % 90;
    }

    private void Navigate(int delta)
    {
        if (!IsImageMode)
        {
            return;
        }

        if (IsVideoFrameMode)
        {
            NavigateVideoFrame(delta, random: false);
            return;
        }

        var entries = ActiveEntries;
        if (entries.Count == 0)
        {
            return;
        }

        SaveCurrentImageViewState();
        if (ActiveModeState().RandomPlayMode && Math.Abs(delta) == 1)
        {
            CurrentIndex = Random.Shared.Next(entries.Count);
        }
        else
        {
            CurrentIndex = (CurrentIndex + delta + entries.Count) % entries.Count;
        }

        _timerRemaining = ActiveModeState().TimerSeconds;
        _timerExpiredHold = false;
        _overtimeSeconds = 0;
        LoadCurrentImage();
        UpdateTimerText();
    }

    private void NavigateVideoFrame(int delta, bool random)
    {
        var video = _videoFrameCache.CurrentVideo;
        if (video is null)
        {
            return;
        }

        SaveCurrentImageViewState();
        var modeState = ActiveModeState();
        if (random)
        {
            modeState.VideoFrameIndex = Random.Shared.Next(video.FrameCount);
        }
        else
        {
            modeState.VideoFrameIndex = (modeState.VideoFrameIndex + delta + video.FrameCount) % video.FrameCount;
        }

        modeState.GetPathPlaybackState(modeState.ImageRootPath).VideoFrameIndex = modeState.VideoFrameIndex;
        CurrentIndex = modeState.VideoFrameIndex;
        RequestVideoFrameDisplay();
        UpdateVideoFrameText();
    }

    private void NavigateSameFolder(int delta)
    {
        if (IsVideoFrameMode || !IsImageMode || ActiveEntry is null || ActiveEntry.IsFromArchive)
        {
            Navigate(delta);
            return;
        }

        var folder = IoPath.GetDirectoryName(ActiveEntry.Path) ?? "";
        var entries = ActiveEntries;
        if (entries.Count == 0 || folder.Length == 0)
        {
            return;
        }

        var direction = delta >= 0 ? 1 : -1;
        var index = CurrentIndex;
        for (var i = 0; i < entries.Count; i++)
        {
            index = (index + direction + entries.Count) % entries.Count;
            var candidate = entries[index];
            if (!candidate.IsFromArchive && string.Equals(IoPath.GetDirectoryName(candidate.Path), folder, StringComparison.OrdinalIgnoreCase))
            {
                SaveCurrentImageViewState();
                CurrentIndex = index;
                _timerRemaining = ActiveModeState().TimerSeconds;
                _timerExpiredHold = false;
                _overtimeSeconds = 0;
                LoadCurrentImage();
                UpdateTimerText();
                return;
            }
        }
    }

    private void GeneratePalette()
    {
        _palette.Clear();
        _palette.AddRange(ColorTools.GeneratePalette(
            _state.ColorBlocksStripeCount,
            _state.ColorBlocksMinLuma,
            _state.ColorBlocksMaxLuma,
            _state.ColorBlocksMinSaturation));
        RenderColorBlocks();
    }

    private static BitmapSource CreateColorStripeBitmap(IReadOnlyList<MediaColor> colors)
    {
        var count = Math.Max(1, colors.Count);
        var width = Math.Max(96, count * 96);
        const int height = 96;
        var visual = new DrawingVisual();
        using (var dc = visual.RenderOpen())
        {
            for (var i = 0; i < count; i++)
            {
                var left = i * width / (double)count;
                var right = (i + 1) * width / (double)count;
                dc.DrawRectangle(new SolidColorBrush(colors[i]), null, new Rect(left, 0, right - left, height));
            }
        }

        var bitmap = new RenderTargetBitmap(width, height, 96, 96, PixelFormats.Pbgra32);
        bitmap.Render(visual);
        bitmap.Freeze();
        return bitmap;
    }

    private void RenderColorBlocks()
    {
        if (ColorBlocksCanvas is null)
        {
            return;
        }

        ColorBlocksCanvas.Children.Clear();
        var width = Math.Max(1, ColorBlocksCanvas.ActualWidth);
        var height = Math.Max(1, ColorBlocksCanvas.ActualHeight);
        var count = Math.Max(1, _palette.Count);
        ColorCountText.Text = "Colors: " + count;

        if (!_state.ColorBlocksShapeModeEnabled)
        {
            for (var i = 0; i < count; i++)
            {
                var color = _grayscaleDisplayEnabled ? ColorTools.ToGrayscale(_palette[i]) : _palette[i];
                var left = Math.Floor(i * width / count);
                var right = Math.Floor((i + 1) * width / count);
                var rectangle = new WpfRectangle
                {
                    Width = Math.Max(1, right - left),
                    Height = height,
                    Fill = new SolidColorBrush(color)
                };
                Canvas.SetLeft(rectangle, left);
                Canvas.SetTop(rectangle, 0);
                ColorBlocksCanvas.Children.Add(rectangle);
            }

            return;
        }

        for (var i = 0; i < 28; i++)
        {
            var color = _grayscaleDisplayEnabled ? ColorTools.ToGrayscale(_palette[i % count]) : _palette[i % count];
            var ellipse = new Ellipse
            {
                Width = Random.Shared.NextDouble() * width * 0.35 + width * 0.08,
                Height = Random.Shared.NextDouble() * height * 0.28 + height * 0.08,
                Fill = new SolidColorBrush(color),
                Opacity = 0.96
            };
            Canvas.SetLeft(ellipse, Random.Shared.NextDouble() * Math.Max(1, width - ellipse.Width));
            Canvas.SetTop(ellipse, Random.Shared.NextDouble() * Math.Max(1, height - ellipse.Height));
            ColorBlocksCanvas.Children.Add(ellipse);
        }
    }

    private void ResampleImageColorsIfEnabled()
    {
        if (!_sampleImageColorsEnabled)
        {
            ClearSampledImageColors();
            return;
        }

        SampleCurrentImageColors();
    }

    private void SampleCurrentImageColors()
    {
        _sampledImageColors.Clear();
        if (!IsImageMode || !_sourceBitmapByMode.TryGetValue(_state.AppMode, out var bitmap) || bitmap is null)
        {
            ClearSampledImageColors();
            return;
        }

        BitmapSource source = bitmap.Format == PixelFormats.Bgra32
            ? bitmap
            : new FormatConvertedBitmap(bitmap, PixelFormats.Bgra32, null, 0);
        var width = source.PixelWidth;
        var height = source.PixelHeight;
        if (width <= 0 || height <= 0)
        {
            ClearSampledImageColors();
            return;
        }

        const int sampleCount = 30;
        var pixels = new byte[4];
        for (var i = 0; i < sampleCount; i++)
        {
            var x = Random.Shared.Next(width);
            var y = Random.Shared.Next(height);
            source.CopyPixels(new Int32Rect(x, y, 1, 1), pixels, 4, 0);
            var color = MediaColor.FromArgb(pixels[3], pixels[2], pixels[1], pixels[0]);
            _sampledImageColors.Add(color);
        }

        RenderSampledImageColors();
        ShowToast("Sampled 30 image colors");
    }

    private void RenderSampledImageColors()
    {
        PhotoSampleColorsCanvas.Children.Clear();
        ColorPhotoSampleColorsCanvas.Children.Clear();
        if (!_sampleImageColorsEnabled || !IsImageMode || _sampledImageColors.Count == 0)
        {
            return;
        }

        var canvas = ActiveSampleColorsCanvas;
        var width = Math.Max(1, canvas.ActualWidth);
        var height = Math.Max(1, canvas.ActualHeight);
        if (width <= 1 || height <= 1)
        {
            return;
        }

        var blockSize = Math.Clamp(Math.Min(width, height) * 0.085, 28, 72);
        var maxLeft = Math.Max(0, width - blockSize);
        var maxTop = Math.Max(0, height - blockSize);
        var shuffled = _sampledImageColors.OrderBy(_ => Random.Shared.Next()).ToList();

        foreach (var rawColor in shuffled)
        {
            var color = _grayscaleDisplayEnabled ? ColorTools.ToGrayscale(rawColor) : rawColor;
            var border = new Border
            {
                Width = blockSize,
                Height = blockSize,
                Background = new SolidColorBrush(color),
                BorderBrush = new SolidColorBrush(MediaColor.FromArgb(220, 255, 255, 255)),
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(4),
                Opacity = 0.94,
                Effect = new DropShadowEffect
                {
                    BlurRadius = 10,
                    ShadowDepth = 2,
                    Opacity = 0.35
                }
            };
            Canvas.SetLeft(border, Random.Shared.NextDouble() * maxLeft);
            Canvas.SetTop(border, Random.Shared.NextDouble() * maxTop);
            canvas.Children.Add(border);
        }
    }

    private void NotifyTimerFinished()
    {
        if (!_state.TimerFinishNotificationEnabled)
        {
            return;
        }

        try
        {
            SystemSounds.Exclamation.Play();
        }
        catch
        {
            // Notification sounds are optional.
        }

        ShowToast(T("Timer finished", "计时结束"));
    }

    private void ClearSampledImageColors()
    {
        _sampledImageColors.Clear();
        PhotoSampleColorsCanvas.Children.Clear();
        ColorPhotoSampleColorsCanvas.Children.Clear();
        VideoFrameSampleColorsCanvas.Children.Clear();
    }

    private void UpdateAllUi()
    {
        ApplyLanguage();
        RebuildRecentPathsMenu();
        SetMenuChecked(PhotoSwitchingModeItem, _state.AppMode == AppMode.PhotoSwitching);
        SetMenuChecked(ColorBlocksModeItem, _state.AppMode == AppMode.ColorBlocks);
        SetMenuChecked(ColorPhotoModeItem, _state.AppMode == AppMode.ColorPhoto);
        SetMenuChecked(VideoFramesModeItem, _state.AppMode == AppMode.VideoFrames);
        SetMenuChecked(RandomPlayItem, ActiveModeState().RandomPlayMode);
        SetMenuChecked(PrestartCountdownItem, ActiveModeState().PrestartCountdownEnabled);
        SetMenuChecked(TimerNotificationItem, _state.TimerFinishNotificationEnabled);
        SetMenuChecked(ShapeModeItem, _state.ColorBlocksShapeModeEnabled);
        SetMenuChecked(MosaicEnabledItem, IsImageMode && ActiveModeState().MosaicEnabled);
        SetMenuChecked(StayOnTopItem, _state.StayOnTop);
        SetMenuChecked(LockAspectItem, _state.LockImageViewportAspectRatio);
        SetMenuChecked(ViewportRatio1x1Item, IsViewportAspectRatio(1, 1));
        SetMenuChecked(ViewportRatio4x3Item, IsViewportAspectRatio(4, 3));
        SetMenuChecked(ViewportRatio3x2Item, IsViewportAspectRatio(3, 2));
        SetMenuChecked(ViewportRatio16x10Item, IsViewportAspectRatio(16, 10));
        SetMenuChecked(ViewportRatio16x9Item, IsViewportAspectRatio(16, 9));
        SetMenuChecked(ViewportRatio21x9Item, IsViewportAspectRatio(21, 9));
        SetMenuChecked(ViewportRatio9x16Item, IsViewportAspectRatio(9, 16));
        SetMenuChecked(GrayscaleItem, _grayscaleDisplayEnabled);
        SetMenuChecked(SampleImageColorsItem, _sampleImageColorsEnabled);
        SampleImageColorsItem.IsEnabled = IsImageMode;
        RandomPlayItem.Visibility = IsImageLibraryMode ? Visibility.Visible : Visibility.Collapsed;
        SetMenuChecked(EnglishLanguageItem, !IsChinese);
        SetMenuChecked(ChineseLanguageItem, IsChinese);
        ProtectedVideoExportItem.IsEnabled = _videoTools.Available && !_videoExportBusy;
        VideoFramesModeItem.Visibility = _videoTools.Available ? Visibility.Visible : Visibility.Collapsed;
        SetMenuChecked(TimerAutoNextItem, ActiveModeState().TimerEndMode == TimerEndMode.AutoNext);
        SetMenuChecked(TimerHoldItem, ActiveModeState().TimerEndMode == TimerEndMode.Hold);
        SetMenuChecked(TimerOvertimeItem, ActiveModeState().TimerEndMode == TimerEndMode.Overtime);
        PauseTimerItem.Header = _timerPaused ? T("Resume Timer", "继续计时") : T("Pause Timer", "暂停计时");
        Topmost = _state.StayOnTop;
        TopMenu.Visibility = _state.StayOnTop ? Visibility.Collapsed : Visibility.Visible;
        ApplyMenuTheme();
        UpdateTimerText();
        ApplyViewportLayout();
    }

    private void ApplyLanguage()
    {
        Title = T("Just Draw!", "Just Draw!");
        FileMenu.Header = T("File", "文件");
        SetImageFolderItem.Header = T("Set Image Folder...", "选择图片文件夹...");
        RecentPathsMenu.Header = IsVideoFrameMode ? T("Recent Videos", "最近视频") : T("Recent Paths", "最近路径");
        DeletePathPlaybackStateItem.Header = IsVideoFrameMode ? T("Delete Video Playback State...", "删除视频播放状态...") : T("Delete Path Playback State...", "删除路径播放状态...");
        RefreshRandomItem.Header = IsVideoFrameMode ? T("Random Frame", "随机帧") : T("Refresh List Order + Random Image", "刷新顺序并随机图片");
        ResetCurrentImageStateItem.Header = IsVideoFrameMode ? T("Reset Current Video View", "重置当前视频视图") : T("Reset Current Image State", "重置当前图片状态");
        ResetCurrentPathImageStatesItem.Header = IsVideoFrameMode ? T("Reset Video View States", "重置视频视图状态") : T("Reset Current Path Image States", "重置当前路径图片状态");
        ExitItem.Header = T("Exit", "退出");
        WindowMenu.Header = T("Window", "窗口");
        ProtectedVideoExportItem.Header = T("Protected Video Export...", "受保护视频导出...");
        ModeMenu.Header = T("Mode", "模式");
        PhotoSwitchingModeItem.Header = T("Photo Switching", "图片切换");
        ColorBlocksModeItem.Header = T("Color Blocks", "色块练习");
        ColorPhotoModeItem.Header = T("Color Photo", "色彩照片");
        VideoFramesModeItem.Header = T("Video Frames", "视频逐帧");
        TimerMenu.Header = T("Timer", "计时器");
        SetTimerItem.Header = T("Set Timer...", "设置计时...");
        ResetTimerItem.Header = T("Reset Timer", "重置计时");
        RandomPlayItem.Header = T("Random Play", "随机播放");
        PrestartCountdownItem.Header = T("3-second Pre-start Countdown", "3 秒预倒计时");
        TimerNotificationItem.Header = T("Timer Finish Notification", "计时结束通知");
        TimerEndModeMenu.Header = T("Timer End Mode", "计时结束模式");
        TimerAutoNextItem.Header = T("Auto Next Image", "自动下一张");
        TimerHoldItem.Header = T("Stay On Current Image", "停在当前图片");
        TimerOvertimeItem.Header = T("Overtime Count Up", "超时正计时");
        ColorToolsMenu.Header = T("Color Sense Tools", "色感工具");
        IncreaseColorsItem.Header = T("Increase Colors", "增加颜色");
        DecreaseColorsItem.Header = T("Decrease Colors", "减少颜色");
        RefreshColorsItem.Header = T("Refresh Colors", "刷新颜色");
        ShapeModeItem.Header = T("Shape Mode", "形状模式");
        SetMinLumaItem.Header = T("Set Min Luma...", "设置最低亮度...");
        SetMaxLumaItem.Header = T("Set Max Luma...", "设置最高亮度...");
        SetMinSaturationItem.Header = T("Set Min Saturation...", "设置最低饱和度...");
        CopyColorsItem.Header = T("Copy Colors", "复制颜色");
        MosaicMenu.Header = T("Mosaic", "马赛克");
        MosaicEnabledItem.Header = T("Enable Mosaic", "启用马赛克");
        MosaicSizeItem.Header = T(
            $"Mosaic Size: {FormatMosaicSize(_state.MosaicDownsampleFactor)}...",
            $"马赛克尺寸：{FormatMosaicSize(_state.MosaicDownsampleFactor)}...");
        ViewportMenu.Header = T("Viewport", "视口");
        SettingsMenu.Header = _updateAvailable
            ? T("Settings *", "设置 *")
            : T("Settings", "设置");
        StayOnTopItem.Header = T("Stay On Top", "窗口置顶");
        LanguageMenu.Header = T("Language", "语言");
        EnglishLanguageItem.Header = T("English", "英文");
        ChineseLanguageItem.Header = T("Chinese", "中文");
        CheckForUpdatesItem.Header = _updateAvailable
            ? T("Update Available - Click to Install", "有可用更新 - 点击安装")
            : T("Check For Updates", "检查更新");
        VideoFrameBufferItem.Header = T(
            $"Video Frame Buffer: {_state.VideoFrameBufferSeconds}s...",
            $"视频逐帧缓冲：{_state.VideoFrameBufferSeconds} 秒...");
        ThemeAccentItem.Header = T("Theme Accent...", "主题色...");
        LockAspectItem.Header = T(
            $"Lock Viewport Aspect Ratio ({FormatViewportAspectRatio(_state.ImageViewportAspectRatio)})",
            $"锁定视口比例（{FormatViewportAspectRatio(_state.ImageViewportAspectRatio)}）");
        ViewportAspectRatioItem.Header = T("Custom Ratio...", "自定义比例...");
        GrayscaleItem.Header = T("Grayscale Display", "灰度显示");
        SampleImageColorsItem.Header = T("Sample 30 Image Colors", "采样 30 个图片颜色");
        OpenSourceNoticeItem.Header = T(
            "Free open-source software on GitHub. Paid copies are scams.",
            "本软件免费开源发布在 GitHub 上，付费购买皆为骗局。");
        GitHubRepositoryItem.Header = T(
            "Open GitHub Repository / Issues",
            "打开 GitHub 仓库 / Issue 反馈");
        var sourcePrompt = IsVideoFrameMode
            ? T("Import Video...", "导入视频...")
            : T("Set Image Folder...", "选择图片文件夹...");
        SetImageFolderItem.Header = sourcePrompt;
        PhotoEmptyText.Text = T("Set an image folder to begin", "请选择图片文件夹开始");
        ColorPhotoEmptyText.Text = T("Set an image folder to begin", "请选择图片文件夹开始");
        VideoFrameEmptyText.Text = T("Import a video to begin", "请导入视频开始");
        ColorCountText.Text = T("Colors: ", "颜色数：") + Math.Max(1, _palette.Count);
        UpdateVideoFrameText();
    }

    private void UpdateTimerText()
    {
        if (_timerExpiredHold && ActiveModeState().TimerEndMode == TimerEndMode.Overtime)
        {
            TimerText.Text = "+" + FormatTime(_overtimeSeconds);
            TimerText.Foreground = MediaBrushes.Red;
            return;
        }

        TimerText.Text = FormatTime(Math.Max(0, _timerRemaining));
        TimerText.Foreground = _timerPaused ? MediaBrushes.Gold : (_timerRemaining <= 5 ? MediaBrushes.Red : MediaBrushes.White);
    }

    private static string FormatTime(int seconds)
    {
        return $"{seconds / 60:00}:{seconds % 60:00}";
    }

    private void Timer_Tick(object? sender, EventArgs e)
    {
        if (_timerPaused || _state.AppMode != AppMode.PhotoSwitching)
        {
            return;
        }

        if (_timerExpiredHold)
        {
            if (ActiveModeState().TimerEndMode == TimerEndMode.Overtime)
            {
                _overtimeSeconds++;
            }

            UpdateTimerText();
            return;
        }

        _timerRemaining--;
        if (_timerRemaining <= 0)
        {
            switch (ActiveModeState().TimerEndMode)
            {
                case TimerEndMode.AutoNext:
                    NotifyTimerFinished();
                    Navigate(1);
                    break;
                case TimerEndMode.Hold:
                    NotifyTimerFinished();
                    _timerRemaining = 0;
                    _timerExpiredHold = true;
                    _timerPaused = true;
                    break;
                case TimerEndMode.Overtime:
                    NotifyTimerFinished();
                    _timerRemaining = 0;
                    _timerExpiredHold = true;
                    _overtimeSeconds = 0;
                    break;
            }
        }

        UpdateTimerText();
    }

    private void ToggleTimer()
    {
        if (_state.AppMode != AppMode.PhotoSwitching)
        {
            return;
        }

        if (_timerPaused && ActiveModeState().PrestartCountdownEnabled)
        {
            StartCountdown();
            return;
        }

        _timerPaused = !_timerPaused;
        if (!_timerPaused)
        {
            _timer.Start();
        }

        UpdateAllUi();
    }

    private void StartCountdown()
    {
        _countdownRemaining = 3;
        CountdownText.Text = _countdownRemaining.ToString();
        CountdownOverlay.Visibility = Visibility.Visible;
        _countdownTimer.Start();
    }

    private void CountdownTimer_Tick(object? sender, EventArgs e)
    {
        _countdownRemaining--;
        if (_countdownRemaining <= 0)
        {
            _countdownTimer.Stop();
            CountdownOverlay.Visibility = Visibility.Collapsed;
            _timerPaused = false;
            _timer.Start();
            UpdateAllUi();
            return;
        }

        CountdownText.Text = _countdownRemaining.ToString();
    }

    private void ShowToast(string message)
    {
        ToastText.Text = message;
        Toast.Visibility = Visibility.Visible;
        _toastTimer.Stop();
        _toastTimer.Start();
    }

    private async void StartupUpdateTimer_Tick(object? sender, EventArgs e)
    {
        _startupUpdateTimer.Stop();
        if (!OperatingSystem.IsWindows() || Environment.ProcessPath is null || !Environment.ProcessPath.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
        {
            return;
        }

        await CheckForUpdatesAsync(manual: false, installIfAvailable: false);
    }

    private async Task CheckForUpdatesAsync(bool manual, bool installIfAvailable)
    {
        if (_updateBusy)
        {
            if (manual)
            {
                ShowToast(T("Update check is already running", "更新检查正在进行"));
            }

            return;
        }

        try
        {
            _updateBusy = true;
            if (manual)
            {
                ShowToast(T("Checking GitHub for updates...", "正在检查 GitHub 更新..."));
            }

            var processPath = Environment.ProcessPath;
            if (string.IsNullOrWhiteSpace(processPath) || !processPath.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
            {
                if (manual)
                {
                    ShowToast(T("Update is only available in the packaged Windows app", "更新仅支持打包后的 Windows 应用"));
                }

                return;
            }

            var result = await _updateService.CheckLatestReleaseAsync(processPath);
            _updateAvailable = result.UpdateAvailable;
            UpdateAllUi();

            if (!result.UpdateAvailable)
            {
                if (manual)
                {
                    ShowToast(T("JustDraw is up to date", "JustDraw 已是最新版本"));
                }

                return;
            }

            if (!installIfAvailable)
            {
                if (manual)
                {
                    ShowToast(T("Update available. Click again to download.", "发现可用更新，再次点击即可下载。"));
                }

                return;
            }

            ShowToast(T("Downloading JustDraw update...", "正在下载 JustDraw 更新..."));
            var downloaded = await _updateService.DownloadReleaseExeAsync(result.Release);
            var script = _updateService.CreateUpdateScript(downloaded);
            UpdateService.LaunchUpdateScript(script);
            Close();
        }
        catch (UpdateNetworkException)
        {
            ShowToast(T("Network problem. Please check your internet connection or system proxy.", "网络有问题，请检查网络连接或系统代理。"));
        }
        catch (Exception ex)
        {
            if (manual)
            {
                ShowToast(T("Update failed: ", "更新失败：") + ex.Message);
            }
        }
        finally
        {
            _updateBusy = false;
            UpdateAllUi();
        }
    }

    private async Task ShowProtectedVideoExportDialogAsync()
    {
        var state = _state.ProtectedVideoExport;
        var dialog = new Window
        {
            Owner = this,
            Title = T("Protected Video Export", "受保护视频导出"),
            Width = 640,
            Height = 560,
            MinWidth = 520,
            MinHeight = 460,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            Topmost = _state.StayOnTop,
            Background = new SolidColorBrush(MediaColor.FromRgb(32, 32, 32))
        };

        var root = new DockPanel { Margin = new Thickness(14) };
        var list = new System.Windows.Controls.ListBox
        {
            AllowDrop = true,
            MinHeight = 150,
            Background = new SolidColorBrush(MediaColor.FromRgb(18, 18, 18)),
            Foreground = MediaBrushes.White
        };
        foreach (var path in state.InputPaths.Where(File.Exists))
        {
            list.Items.Add(path);
        }

        list.Drop += (_, e) =>
        {
            if (!e.Data.GetDataPresent(System.Windows.DataFormats.FileDrop))
            {
                return;
            }

            foreach (var path in ((string[])e.Data.GetData(System.Windows.DataFormats.FileDrop)!).Where(IsVideoPath))
            {
                if (!list.Items.Contains(path))
                {
                    list.Items.Add(path);
                }
            }
        };

        var form = new Grid();
        form.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(150) });
        form.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        for (var i = 0; i < 6; i++)
        {
            form.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        }

        var duration = new System.Windows.Controls.TextBox { Text = Math.Max(1, state.DurationSeconds).ToString(CultureInfo.InvariantCulture), Margin = new Thickness(0, 4, 0, 4) };
        var watermarkText = new System.Windows.Controls.TextBox { Text = state.WatermarkText, Margin = new Thickness(0, 4, 0, 4) };
        var watermarkPath = new System.Windows.Controls.TextBox { Text = state.WatermarkPath, Margin = new Thickness(0, 4, 0, 4) };
        var format = new System.Windows.Controls.ComboBox { ItemsSource = new[] { "mp4", "gif" }, SelectedItem = state.OutputFormat == "gif" ? "gif" : "mp4", Margin = new Thickness(0, 4, 0, 4) };
        var overlay = new System.Windows.Controls.ComboBox { ItemsSource = new[] { "noise", "off" }, SelectedItem = state.OverlayMode == "off" ? "off" : "noise", Margin = new Thickness(0, 4, 0, 4) };
        var deleteOriginal = new System.Windows.Controls.CheckBox { Content = T("Delete original after successful export", "导出成功后删除原视频"), IsChecked = state.DeleteOriginalAfterExport, Foreground = MediaBrushes.White, Margin = new Thickness(0, 6, 0, 6) };
        AddFormRow(form, 0, T("Target seconds", "目标秒数"), duration);
        AddFormRow(form, 1, T("Watermark text", "水印文字"), watermarkText);
        AddFormRow(form, 2, T("Watermark image", "水印图片"), watermarkPath);
        AddFormRow(form, 3, T("Output format", "输出格式"), format);
        AddFormRow(form, 4, T("Overlay", "叠加层"), overlay);
        Grid.SetColumn(deleteOriginal, 1);
        Grid.SetRow(deleteOriginal, 5);
        form.Children.Add(deleteOriginal);

        var buttons = new StackPanel { Orientation = System.Windows.Controls.Orientation.Horizontal, HorizontalAlignment = System.Windows.HorizontalAlignment.Right, Margin = new Thickness(0, 12, 0, 0) };
        var addButton = new System.Windows.Controls.Button { Content = T("Add Videos...", "添加视频..."), Margin = new Thickness(0, 0, 8, 0), Padding = new Thickness(12, 5, 12, 5) };
        var removeButton = new System.Windows.Controls.Button { Content = T("Remove Selected", "移除选中"), Margin = new Thickness(0, 0, 8, 0), Padding = new Thickness(12, 5, 12, 5) };
        var watermarkButton = new System.Windows.Controls.Button { Content = T("Browse Watermark...", "选择水印..."), Margin = new Thickness(0, 0, 8, 0), Padding = new Thickness(12, 5, 12, 5) };
        var exportButton = new System.Windows.Controls.Button { Content = T("Export", "导出"), Padding = new Thickness(16, 5, 16, 5) };
        buttons.Children.Add(addButton);
        buttons.Children.Add(removeButton);
        buttons.Children.Add(watermarkButton);
        buttons.Children.Add(exportButton);

        var status = new TextBlock { Foreground = MediaBrushes.White, Margin = new Thickness(0, 10, 0, 0), Text = _videoTools.Available ? T("Ready", "准备就绪") : _videoTools.MissingReason };
        DockPanel.SetDock(buttons, Dock.Bottom);
        DockPanel.SetDock(status, Dock.Bottom);
        DockPanel.SetDock(form, Dock.Bottom);
        root.Children.Add(buttons);
        root.Children.Add(status);
        root.Children.Add(form);
        root.Children.Add(list);
        dialog.Content = root;

        addButton.Click += (_, _) =>
        {
            var picker = new Microsoft.Win32.OpenFileDialog
            {
                Multiselect = true,
                Filter = "Video Files (*.mp4;*.mov;*.mkv;*.avi;*.webm;*.m4v;*.wmv;*.flv;*.ts;*.mts;*.m2ts)|*.mp4;*.mov;*.mkv;*.avi;*.webm;*.m4v;*.wmv;*.flv;*.ts;*.mts;*.m2ts|All Files (*.*)|*.*"
            };
            if (picker.ShowDialog(dialog) == true)
            {
                foreach (var path in picker.FileNames.Where(IsVideoPath))
                {
                    if (!list.Items.Contains(path))
                    {
                        list.Items.Add(path);
                    }
                }
            }
        };
        removeButton.Click += (_, _) =>
        {
            foreach (var item in list.SelectedItems.Cast<object>().ToArray())
            {
                list.Items.Remove(item);
            }
        };
        watermarkButton.Click += (_, _) =>
        {
            var picker = new Microsoft.Win32.OpenFileDialog
            {
                Filter = "Image Files (*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp)|*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp|All Files (*.*)|*.*"
            };
            if (picker.ShowDialog(dialog) == true)
            {
                watermarkPath.Text = picker.FileName;
            }
        };
        exportButton.Click += async (_, _) =>
        {
            if (_videoExportBusy)
            {
                return;
            }

            var paths = list.Items.Cast<string>().Where(File.Exists).ToList();
            if (paths.Count == 0)
            {
                status.Text = T("Add at least one video", "请至少添加一个视频");
                return;
            }

            if (!int.TryParse(duration.Text, NumberStyles.Integer, CultureInfo.InvariantCulture, out var seconds) || seconds <= 0)
            {
                status.Text = T("Target seconds must be positive", "目标秒数必须大于 0");
                return;
            }

            state.InputPaths = paths;
            state.DurationSeconds = seconds;
            state.WatermarkText = watermarkText.Text;
            state.WatermarkPath = watermarkPath.Text;
            state.OutputFormat = (format.SelectedItem as string) ?? "mp4";
            state.OverlayMode = (overlay.SelectedItem as string) ?? "noise";
            state.DeleteOriginalAfterExport = deleteOriginal.IsChecked == true;
            _videoExportBusy = true;
            exportButton.IsEnabled = false;
            try
            {
                var exported = new List<string>();
                for (var i = 0; i < paths.Count; i++)
                {
                    var input = paths[i];
                    var progress = new Progress<(int Percent, string Stage, string Detail)>(value =>
                    {
                        status.Text = $"{i + 1}/{paths.Count} {value.Percent}% - {value.Stage}: {value.Detail}";
                    });
                    var result = await _videoExportService.ExportProtectedShortVideoAsync(
                        _videoTools,
                        new VideoExportOptions(input, "", seconds, state.OutputFormat, state.WatermarkPath, state.WatermarkText, state.OverlayMode, state.DeleteOriginalAfterExport),
                        progress);
                    exported.Add(result.OutputPath);
                }

                status.Text = paths.Count == 1
                    ? T("Protected video exported: ", "受保护视频已导出：") + IoPath.GetFileName(exported[0])
                    : T("Protected video export complete: ", "受保护视频导出完成：") + exported.Count;
                ShowToast(status.Text);
            }
            catch (Exception ex)
            {
                status.Text = T("Protected video export failed: ", "受保护视频导出失败：") + ex.Message;
                ShowToast(status.Text);
            }
            finally
            {
                _videoExportBusy = false;
                exportButton.IsEnabled = true;
                UpdateAllUi();
            }
        };

        dialog.Closed += (_, _) =>
        {
            state.InputPaths = list.Items.Cast<string>().ToList();
            state.WatermarkText = watermarkText.Text;
            state.WatermarkPath = watermarkPath.Text;
            state.OutputFormat = (format.SelectedItem as string) ?? "mp4";
            state.OverlayMode = (overlay.SelectedItem as string) ?? "noise";
            state.DeleteOriginalAfterExport = deleteOriginal.IsChecked == true;
            if (int.TryParse(duration.Text, NumberStyles.Integer, CultureInfo.InvariantCulture, out var seconds) && seconds > 0)
            {
                state.DurationSeconds = seconds;
            }
        };

        dialog.Show();
        await Task.CompletedTask;
    }

    private static void AddFormRow(Grid form, int row, string label, System.Windows.Controls.Control control)
    {
        var text = new TextBlock { Text = label, Foreground = MediaBrushes.White, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 4, 12, 4) };
        Grid.SetRow(text, row);
        Grid.SetColumn(text, 0);
        Grid.SetRow(control, row);
        Grid.SetColumn(control, 1);
        form.Children.Add(text);
        form.Children.Add(control);
    }

    private static bool IsVideoPath(string path)
    {
        return File.Exists(path) && VideoExportService.VideoExtensions.Contains(IoPath.GetExtension(path), StringComparer.OrdinalIgnoreCase);
    }

    private void SetImageFolder_Click(object sender, RoutedEventArgs e)
    {
        if (IsVideoFrameMode)
        {
            _ = ImportVideoFrameSourceAsync();
            return;
        }

        using var dialog = new Forms.FolderBrowserDialog
        {
            Description = "Select image folder",
            UseDescriptionForTitle = true
        };

        if (dialog.ShowDialog() != Forms.DialogResult.OK)
        {
            return;
        }

        OpenImageSource(dialog.SelectedPath);
    }

    private async Task ImportVideoFrameSourceAsync()
    {
        if (!_videoTools.Available)
        {
            return;
        }

        var picker = new Microsoft.Win32.OpenFileDialog
        {
            Filter = "Video Files (*.mp4;*.mov;*.mkv;*.avi;*.webm;*.m4v;*.wmv;*.flv;*.ts;*.mts;*.m2ts)|*.mp4;*.mov;*.mkv;*.avi;*.webm;*.m4v;*.wmv;*.flv;*.ts;*.mts;*.m2ts|All Files (*.*)|*.*"
        };
        if (picker.ShowDialog(this) != true || !IsVideoPath(picker.FileName))
        {
            return;
        }

        await OpenVideoFrameSourceAsync(picker.FileName, showToast: true);
    }

    private void DeletePathPlaybackState_Click(object sender, RoutedEventArgs e)
    {
        var modeState = ActiveModeState();
        var path = modeState.ImageRootPath;
        if (string.IsNullOrWhiteSpace(path))
        {
            ShowToast(T("No active image path", "当前没有图片路径"));
            return;
        }

        modeState.RemovePathPlaybackState(path);
        modeState.LastImagePath = "";
        modeState.ImageOrder.Clear();
        modeState.VideoFrameIndex = 0;
        if (IsVideoFrameMode)
        {
            CurrentIndex = 0;
            RequestVideoFrameDisplay();
            ShowToast(T("Path playback state deleted", "已删除当前路径播放状态"));
            UpdateAllUi();
            return;
        }

        _entriesByMode.Remove(_state.AppMode);
        _currentIndexByMode[_state.AppMode] = 0;
        _loadedSources.Remove(_state.AppMode);
        LoadSourceForMode(_state.AppMode, showToast: false);
        RefreshActiveView();
        ShowToast(T("Path playback state deleted", "已删除当前路径播放状态"));
    }

    private void RefreshRandom_Click(object sender, RoutedEventArgs e)
    {
        if (!IsImageMode)
        {
            return;
        }

        if (IsVideoFrameMode)
        {
            NavigateVideoFrame(1, random: true);
            ShowToast(T("Random frame", "随机帧"));
            return;
        }

        var entries = ActiveEntries;
        for (var i = entries.Count - 1; i > 0; i--)
        {
            var j = Random.Shared.Next(i + 1);
            (entries[i], entries[j]) = (entries[j], entries[i]);
        }

        var modeState = ActiveModeState();
        var pathState = modeState.GetPathPlaybackState(modeState.ImageRootPath);
        pathState.UseCustomImageOrder = true;
        pathState.ImageOrder = entries.Select(e => e.Path).ToList();
        modeState.ImageOrder = pathState.ImageOrder.ToList();
        CurrentIndex = entries.Count == 0 ? 0 : Random.Shared.Next(entries.Count);
        LoadCurrentImage();
        ShowToast("Random image");
    }

    private void ResetImageView_Click(object sender, RoutedEventArgs e)
    {
        var key = GetCurrentViewStateKey();
        if (string.IsNullOrWhiteSpace(key))
        {
            return;
        }

        ActiveModeState().ImageViewStates[key] = new ImageViewState();
        ApplyImageViewState();
        ShowToast(T("Current image state reset", "已重置当前图片状态"));
    }

    private void ResetCurrentPathImageStates_Click(object sender, RoutedEventArgs e)
    {
        ActiveModeState().ImageViewStates.Clear();
        ApplyImageViewState();
        ShowToast(T("Current path image states reset", "已重置当前路径图片状态"));
    }

    private void Exit_Click(object sender, RoutedEventArgs e) => Close();

    private void PhotoSwitchingMode_Click(object sender, RoutedEventArgs e) => ApplyMode(AppMode.PhotoSwitching);

    private void ColorBlocksMode_Click(object sender, RoutedEventArgs e) => ApplyMode(AppMode.ColorBlocks);

    private void ColorPhotoMode_Click(object sender, RoutedEventArgs e) => ApplyMode(AppMode.ColorPhoto);

    private void VideoFramesMode_Click(object sender, RoutedEventArgs e)
    {
        if (!_videoTools.Available)
        {
            return;
        }

        ApplyMode(AppMode.VideoFrames);
    }

    private void PauseTimer_Click(object sender, RoutedEventArgs e) => ToggleTimer();

    private void SetTimer_Click(object sender, RoutedEventArgs e)
    {
        var input = Microsoft.VisualBasic.Interaction.InputBox(T("Set seconds", "设置秒数"), T("Timer", "计时器"), ActiveModeState().TimerSeconds.ToString());
        if (!int.TryParse(input, out var seconds) || seconds <= 0)
        {
            return;
        }

        ActiveModeState().TimerSeconds = seconds;
        _timerRemaining = seconds;
        _timerExpiredHold = false;
        _overtimeSeconds = 0;
        UpdateAllUi();
    }

    private void ResetTimer_Click(object sender, RoutedEventArgs e)
    {
        _timerRemaining = ActiveModeState().TimerSeconds;
        _timerExpiredHold = false;
        _overtimeSeconds = 0;
        UpdateAllUi();
    }

    private void RandomPlay_Click(object sender, RoutedEventArgs e)
    {
        ActiveModeState().RandomPlayMode = !ActiveModeState().RandomPlayMode;
        ShowToast(ActiveModeState().RandomPlayMode ? T("Random mode enabled", "已启用随机模式") : T("Sequence mode enabled", "已启用顺序模式"));
        UpdateAllUi();
    }

    private void PrestartCountdown_Click(object sender, RoutedEventArgs e)
    {
        ActiveModeState().PrestartCountdownEnabled = !ActiveModeState().PrestartCountdownEnabled;
        UpdateAllUi();
    }

    private void TimerNotification_Click(object sender, RoutedEventArgs e)
    {
        _state.TimerFinishNotificationEnabled = !_state.TimerFinishNotificationEnabled;
        ShowToast(_state.TimerFinishNotificationEnabled
            ? T("Timer finish notification enabled", "已启用计时结束通知")
            : T("Timer finish notification disabled", "已关闭计时结束通知"));
        UpdateAllUi();
    }

    private void TimerAutoNext_Click(object sender, RoutedEventArgs e) => SetTimerEndMode(TimerEndMode.AutoNext);

    private void TimerHold_Click(object sender, RoutedEventArgs e) => SetTimerEndMode(TimerEndMode.Hold);

    private void TimerOvertime_Click(object sender, RoutedEventArgs e) => SetTimerEndMode(TimerEndMode.Overtime);

    private void SetTimerEndMode(TimerEndMode mode)
    {
        ActiveModeState().TimerEndMode = mode;
        _timerExpiredHold = false;
        _overtimeSeconds = 0;
        UpdateAllUi();
    }

    private void IncreaseColors_Click(object sender, RoutedEventArgs e)
    {
        _state.ColorBlocksStripeCount = Math.Clamp(_state.ColorBlocksStripeCount + 1, 1, 20);
        GeneratePalette();
    }

    private void DecreaseColors_Click(object sender, RoutedEventArgs e)
    {
        _state.ColorBlocksStripeCount = Math.Clamp(_state.ColorBlocksStripeCount - 1, 1, 20);
        GeneratePalette();
    }

    private void RefreshColors_Click(object sender, RoutedEventArgs e)
    {
        GeneratePalette();
        ShowToast(T("Colors refreshed", "颜色已刷新"));
    }

    private void ShapeMode_Click(object sender, RoutedEventArgs e)
    {
        _state.ColorBlocksShapeModeEnabled = !_state.ColorBlocksShapeModeEnabled;
        RenderColorBlocks();
        UpdateAllUi();
    }

    private void CopyColors_Click(object sender, RoutedEventArgs e)
    {
        if (_palette.Count == 0)
        {
            return;
        }

        if (_palette.Count == 1)
        {
            System.Windows.Clipboard.SetImage(CreateColorStripeBitmap(_palette.Select(c => _grayscaleDisplayEnabled ? ColorTools.ToGrayscale(c) : c).ToList()));
        }
        else
        {
            System.Windows.Clipboard.SetImage(CreateColorStripeBitmap(_palette.Select(c => _grayscaleDisplayEnabled ? ColorTools.ToGrayscale(c) : c).ToList()));
        }

        ShowToast(T("Colors copied", "颜色已复制"));
    }

    private void SetMinLuma_Click(object sender, RoutedEventArgs e) => SetColorThreshold(
        T("Set Min Luma", "设置最低亮度"),
        _state.ColorBlocksMinLuma,
        value =>
        {
            if (value > _state.ColorBlocksMaxLuma)
            {
                ShowToast(T("Min luma cannot exceed max luma", "最低亮度不能高于最高亮度"));
                return;
            }

            _state.ColorBlocksMinLuma = value;
            GeneratePalette();
        });

    private void SetMaxLuma_Click(object sender, RoutedEventArgs e) => SetColorThreshold(
        T("Set Max Luma", "设置最高亮度"),
        _state.ColorBlocksMaxLuma,
        value =>
        {
            if (value < _state.ColorBlocksMinLuma)
            {
                ShowToast(T("Max luma cannot be below min luma", "最高亮度不能低于最低亮度"));
                return;
            }

            _state.ColorBlocksMaxLuma = value;
            GeneratePalette();
        });

    private void SetMinSaturation_Click(object sender, RoutedEventArgs e) => SetColorThreshold(
        T("Set Min Saturation", "设置最低饱和度"),
        _state.ColorBlocksMinSaturation,
        value =>
        {
            _state.ColorBlocksMinSaturation = value;
            GeneratePalette();
        });

    private void SetColorThreshold(string title, double currentValue, Action<double> apply)
    {
        var input = Microsoft.VisualBasic.Interaction.InputBox(T("Enter a value from 0 to 1", "请输入 0 到 1 之间的数值"), title, currentValue.ToString("0.###", CultureInfo.InvariantCulture));
        if (!double.TryParse(input, NumberStyles.Float, CultureInfo.InvariantCulture, out var value))
        {
            return;
        }

        apply(ClampUnit(value));
        UpdateAllUi();
    }

    private void MosaicEnabled_Click(object sender, RoutedEventArgs e)
    {
        if (!IsImageMode)
        {
            return;
        }

        ActiveModeState().MosaicEnabled = !ActiveModeState().MosaicEnabled;
        ApplyImageEffects();
        UpdateAllUi();
    }

    private void MosaicSize_Click(object sender, RoutedEventArgs e)
    {
        if (!IsImageMode)
        {
            return;
        }

        ShowMosaicSizeDialog();
    }

    private void ShowMosaicSizeDialog()
    {
        var original = ClampMosaicSize(_state.MosaicDownsampleFactor);
        var accepted = false;
        var dialog = new Window
        {
            Owner = this,
            Title = T("Mosaic Size", "马赛克尺寸"),
            Width = 420,
            Height = 220,
            ResizeMode = ResizeMode.NoResize,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            Background = (System.Windows.Media.Brush)Resources["SurfaceBrush"],
            Topmost = _state.StayOnTop
        };

        var root = new StackPanel { Margin = new Thickness(18) };
        var header = new Grid { Margin = new Thickness(0, 0, 0, 12) };
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        header.Children.Add(new TextBlock
        {
            Text = T("Size", "尺寸"),
            Foreground = (System.Windows.Media.Brush)Resources["TextBrush"],
            FontSize = 16,
            FontWeight = FontWeights.SemiBold,
            VerticalAlignment = VerticalAlignment.Center
        });
        var valueText = new TextBlock
        {
            Text = FormatMosaicSize(original),
            Foreground = (System.Windows.Media.Brush)Resources["AccentBrush"],
            FontSize = 18,
            FontWeight = FontWeights.SemiBold,
            VerticalAlignment = VerticalAlignment.Center
        };
        Grid.SetColumn(valueText, 1);
        header.Children.Add(valueText);

        var slider = new Slider
        {
            Minimum = MosaicMinFactor,
            Maximum = MosaicMaxFactor,
            Value = original,
            SmallChange = 0.25,
            LargeChange = 4,
            IsSnapToTickEnabled = false,
            Margin = new Thickness(0, 2, 0, 4),
            Foreground = (System.Windows.Media.Brush)Resources["AccentBrush"]
        };

        var range = new Grid { Margin = new Thickness(0, 0, 0, 18) };
        range.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        range.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        range.Children.Add(new TextBlock
        {
            Text = FormatMosaicSize(MosaicMinFactor),
            Foreground = (System.Windows.Media.Brush)Resources["MutedTextBrush"],
            FontSize = 12
        });
        var maxText = new TextBlock
        {
            Text = FormatMosaicSize(MosaicMaxFactor),
            Foreground = (System.Windows.Media.Brush)Resources["MutedTextBrush"],
            FontSize = 12
        };
        Grid.SetColumn(maxText, 1);
        range.Children.Add(maxText);

        slider.ValueChanged += (_, _) =>
        {
            var value = ClampMosaicSize(slider.Value);
            valueText.Text = FormatMosaicSize(value);
            ApplyMosaicSize(value, showToast: false);
        };

        var actions = new StackPanel { Orientation = System.Windows.Controls.Orientation.Horizontal, HorizontalAlignment = System.Windows.HorizontalAlignment.Right };
        var reset = new System.Windows.Controls.Button { Content = T("Default", "默认"), Padding = new Thickness(14, 5, 14, 5), Margin = new Thickness(0, 0, 8, 0) };
        var cancel = new System.Windows.Controls.Button { Content = T("Cancel", "取消"), Padding = new Thickness(14, 5, 14, 5), Margin = new Thickness(0, 0, 8, 0) };
        var apply = new System.Windows.Controls.Button { Content = T("Apply", "应用"), Padding = new Thickness(16, 5, 16, 5), Background = (System.Windows.Media.Brush)Resources["AccentBrush"], Foreground = System.Windows.Media.Brushes.White };
        reset.Click += (_, _) => slider.Value = 16;
        cancel.Click += (_, _) => dialog.DialogResult = false;
        apply.Click += (_, _) =>
        {
            accepted = true;
            ApplyMosaicSize(slider.Value, showToast: true);
            UpdateAllUi();
            dialog.DialogResult = true;
        };
        actions.Children.Add(reset);
        actions.Children.Add(cancel);
        actions.Children.Add(apply);

        dialog.Closing += (_, _) =>
        {
            if (!accepted)
            {
                ApplyMosaicSize(original, showToast: false);
                UpdateAllUi();
            }
        };

        root.Children.Add(header);
        root.Children.Add(slider);
        root.Children.Add(range);
        root.Children.Add(actions);
        dialog.Content = root;
        dialog.ShowDialog();
    }

    private void ApplyMosaicSize(double size, bool showToast)
    {
        _state.MosaicDownsampleFactor = ClampMosaicSize(size);
        ApplyImageEffects();
        if (showToast)
        {
            ShowToast(T("Mosaic size updated", "马赛克尺寸已更新"));
        }
    }

    private static double ClampMosaicSize(double size)
    {
        return double.IsNaN(size) || double.IsInfinity(size)
            ? 16
            : Math.Clamp(size, MosaicMinFactor, MosaicMaxFactor);
    }

    private void StayOnTop_Click(object sender, RoutedEventArgs e)
    {
        ToggleStayOnTop();
    }

    private void ViewportPreset_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not MenuItem { Tag: string value }
            || !TryParseViewportAspectRatio(value, out var width, out var height))
        {
            return;
        }

        ViewportController.SetViewportAspectRatio(width, height);
        var label = FormatViewportAspectRatio(_state.ImageViewportAspectRatio);
        ShowToast(T($"Image viewport locked to {label}", $"图片视口已锁定为 {label}"));
    }

    private void ViewportAspectRatio_Click(object sender, RoutedEventArgs e)
    {
        var input = Microsoft.VisualBasic.Interaction.InputBox(
            T(
                "Enter a viewport ratio such as 16:9, 4:3, 1:1, or 1.85. Applying it also enables the aspect-ratio lock.",
                "请输入视口宽高比，例如 16:9、4:3、1:1 或 1.85。应用后会同时启用比例锁定。"),
            T("Image Viewport Aspect Ratio", "图片视口比例"),
            FormatViewportAspectRatio(_state.ImageViewportAspectRatio));
        if (string.IsNullOrWhiteSpace(input))
        {
            return;
        }

        if (!TryParseViewportAspectRatio(input, out var width, out var height))
        {
            System.Windows.MessageBox.Show(
                this,
                T("Enter a valid positive ratio between 1:100 and 100:1.", "请输入 1:100 到 100:1 之间的有效正数比例。"),
                T("Invalid Viewport Ratio", "视口比例无效"),
                MessageBoxButton.OK,
                MessageBoxImage.Warning);
            return;
        }

        ViewportController.SetViewportAspectRatio(width, height);
        var label = FormatViewportAspectRatio(_state.ImageViewportAspectRatio);
        ShowToast(T($"Image viewport locked to {label}", $"图片视口已锁定为 {label}"));
    }

    private void LockAspect_Click(object sender, RoutedEventArgs e)
    {
        var enabled = !_state.LockImageViewportAspectRatio;
        ViewportController.SetViewportAspectRatioLock(enabled);
        ShowToast(enabled
            ? T($"Image viewport locked to {FormatViewportAspectRatio(_state.ImageViewportAspectRatio)}", $"图片视口已锁定为 {FormatViewportAspectRatio(_state.ImageViewportAspectRatio)}")
            : T("Image viewport aspect ratio unlocked", "图片视口比例已解锁"));
    }

    private void Grayscale_Click(object sender, RoutedEventArgs e)
    {
        _grayscaleDisplayEnabled = !_grayscaleDisplayEnabled;
        _state.GrayscaleDisplayEnabled = _grayscaleDisplayEnabled;
        ApplyImageEffects();
        RenderColorBlocks();
        RenderSampledImageColors();
        ShowToast(_grayscaleDisplayEnabled ? T("Grayscale display enabled", "已启用灰度显示") : T("Grayscale display disabled", "已关闭灰度显示"));
        UpdateAllUi();
    }

    private void SampleImageColors_Click(object sender, RoutedEventArgs e)
    {
        if (!IsImageMode)
        {
            return;
        }

        _sampleImageColorsEnabled = !_sampleImageColorsEnabled;
        _state.SampleImageColorsEnabled = _sampleImageColorsEnabled;
        if (_sampleImageColorsEnabled)
        {
            SampleCurrentImageColors();
        }
        else
        {
            ClearSampledImageColors();
            ShowToast(T("Image color samples hidden", "已隐藏图片颜色采样"));
        }

        UpdateAllUi();
    }

    private void EnglishLanguage_Click(object sender, RoutedEventArgs e)
    {
        _state.UiLanguage = "en";
        ShowToast("Language set to English");
        UpdateAllUi();
    }

    private void ChineseLanguage_Click(object sender, RoutedEventArgs e)
    {
        _state.UiLanguage = "zh";
        ShowToast("界面语言已切换为中文");
        UpdateAllUi();
    }

    private async void CheckForUpdates_Click(object sender, RoutedEventArgs e)
    {
        await CheckForUpdatesAsync(manual: true, installIfAvailable: _updateAvailable);
    }

    private void VideoFrameBuffer_Click(object sender, RoutedEventArgs e)
    {
        var input = Microsoft.VisualBasic.Interaction.InputBox(
            T("Set how many seconds before and after the current video frame should be buffered. Enter 1 to 60.",
                "设置当前视频帧前后各缓冲多少秒。请输入 1 到 60。"),
            T("Video Frame Buffer", "视频逐帧缓冲"),
            _state.VideoFrameBufferSeconds.ToString(CultureInfo.InvariantCulture));
        if (!int.TryParse(input, NumberStyles.Integer, CultureInfo.InvariantCulture, out var seconds))
        {
            return;
        }

        seconds = Math.Clamp(seconds, 1, 60);
        _state.VideoFrameBufferSeconds = seconds;
        _videoFrameCache.BufferSeconds = seconds;
        if (IsVideoFrameMode && _videoFrameCache.CurrentVideo is not null)
        {
            _videoFrameCache.PreloadAround(Math.Clamp(ActiveModeState().VideoFrameIndex, 0, _videoFrameCache.CurrentVideo.FrameCount - 1));
        }

        ShowToast(T($"Video frame buffer set to {seconds} seconds", $"视频逐帧缓冲已设置为 {seconds} 秒"));
        UpdateAllUi();
    }

    private void ThemeAccent_Click(object sender, RoutedEventArgs e)
    {
        var selected = ShowThemeAccentDialog();
        if (string.IsNullOrWhiteSpace(selected))
        {
            return;
        }

        if (!TryParseThemeColor(selected, out var color))
        {
            ShowToast(T("Theme color is invalid", "主题色无效"));
            return;
        }

        _state.ThemeAccentColor = ColorToHex(color);
        ApplyTheme();
        ShowToast(T("Theme color updated", "主题色已更新"));
        UpdateAllUi();
    }

    private string ShowThemeAccentDialog()
    {
        var dialog = new Window
        {
            Owner = this,
            Title = T("Theme Accent", "主题色"),
            Width = 360,
            Height = 260,
            ResizeMode = ResizeMode.NoResize,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            Background = (System.Windows.Media.Brush)Resources["SurfaceBrush"],
            Topmost = _state.StayOnTop
        };

        var root = new StackPanel { Margin = new Thickness(18) };
        root.Children.Add(new TextBlock
        {
            Text = T("Choose an accent color or enter a hex value.", "选择一个主题色，或输入十六进制颜色值。"),
            Foreground = (System.Windows.Media.Brush)Resources["TextBrush"],
            Margin = new Thickness(0, 0, 0, 12)
        });

        var swatches = new System.Windows.Controls.Primitives.UniformGrid { Columns = 6, Margin = new Thickness(0, 0, 0, 14) };
        var presets = new[] { "#0EA5A8", "#3B82F6", "#8B5CF6", "#E11D48", "#F59E0B", "#22C55E" };
        string? selected = null;
        foreach (var preset in presets)
        {
            var color = ParseThemeColor(preset);
            var button = new System.Windows.Controls.Button
            {
                Width = 42,
                Height = 34,
                Margin = new Thickness(4),
                Background = FrozenBrush(color),
                BorderBrush = System.Windows.Media.Brushes.White,
                BorderThickness = new Thickness(preset.Equals(ColorToHex(ParseThemeColor(_state.ThemeAccentColor)), StringComparison.OrdinalIgnoreCase) ? 2 : 0),
                ToolTip = preset
            };
            button.Click += (_, _) =>
            {
                selected = preset;
                dialog.DialogResult = true;
            };
            swatches.Children.Add(button);
        }

        var input = new System.Windows.Controls.TextBox
        {
            Text = ColorToHex(ParseThemeColor(_state.ThemeAccentColor)),
            Margin = new Thickness(0, 0, 0, 14),
            Padding = new Thickness(8, 5, 8, 5)
        };

        var actions = new StackPanel { Orientation = System.Windows.Controls.Orientation.Horizontal, HorizontalAlignment = System.Windows.HorizontalAlignment.Right };
        var cancel = new System.Windows.Controls.Button { Content = T("Cancel", "取消"), Padding = new Thickness(14, 5, 14, 5), Margin = new Thickness(0, 0, 8, 0) };
        var apply = new System.Windows.Controls.Button { Content = T("Apply", "应用"), Padding = new Thickness(16, 5, 16, 5), Background = (System.Windows.Media.Brush)Resources["AccentBrush"], Foreground = System.Windows.Media.Brushes.White };
        cancel.Click += (_, _) => dialog.DialogResult = false;
        apply.Click += (_, _) =>
        {
            selected = input.Text.Trim();
            dialog.DialogResult = true;
        };
        actions.Children.Add(cancel);
        actions.Children.Add(apply);

        root.Children.Add(swatches);
        root.Children.Add(input);
        root.Children.Add(actions);
        dialog.Content = root;
        return dialog.ShowDialog() == true ? selected ?? "" : "";
    }

    private void GitHubRepository_Click(object sender, RoutedEventArgs e)
    {
        Process.Start(new ProcessStartInfo
        {
            FileName = UpdateService.RepositoryUrl,
            UseShellExecute = true
        });
    }

    private async void ProtectedVideoExport_Click(object sender, RoutedEventArgs e)
    {
        if (!_videoTools.Available)
        {
            ShowToast(T("Protected video export is unavailable: ", "受保护视频导出不可用：") + _videoTools.MissingReason);
            return;
        }

        await ShowProtectedVideoExportDialogAsync();
    }

    private void ImageViewport_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (!IsImageMode || (!IsVideoFrameMode && ActiveEntry is null))
        {
            return;
        }

        if (e.ClickCount == 2)
        {
            ResetImageView_Click(sender, e);
            return;
        }

        _isDraggingImage = true;
        _dragStart = e.GetPosition(ActiveViewport);
        var state = GetCurrentImageViewState();
        _dragStartOffsetX = state.OffsetX;
        _dragStartOffsetY = state.OffsetY;
        ActiveViewport.CaptureMouse();
    }

    private void ImageViewport_MouseLeftButtonUp(object sender, MouseButtonEventArgs e)
    {
        _isDraggingImage = false;
        ActiveViewport.ReleaseMouseCapture();
        ClampImageViewState(GetCurrentImageViewState());
        ApplyImageViewState();
        SaveCurrentImageViewState();
    }

    private void ImageViewport_MouseMove(object sender, System.Windows.Input.MouseEventArgs e)
    {
        if (!_isDraggingImage || !IsImageMode)
        {
            return;
        }

        var point = e.GetPosition(ActiveViewport);
        var state = GetCurrentImageViewState();
        state.OffsetX = _dragStartOffsetX + point.X - _dragStart.X;
        state.OffsetY = _dragStartOffsetY + point.Y - _dragStart.Y;
        ApplyImageViewState();
    }

    private void ImageViewport_MouseWheel(object sender, MouseWheelEventArgs e)
    {
        if (!IsImageMode || (!IsVideoFrameMode && ActiveEntry is null))
        {
            return;
        }

        var state = GetCurrentImageViewState();
        var factor = e.Delta > 0 ? 1.12 : 1 / 1.12;
        state.Scale = Math.Clamp(state.Scale * factor, 1.0, 8.0);
        ApplyImageViewState();
    }

    private void ImageViewport_MouseRightButtonUp(object sender, MouseButtonEventArgs e)
    {
        if (!IsImageMode)
        {
            return;
        }

        var menu = new ContextMenu();
        menu.Items.Add(ContextItem(IsVideoFrameMode ? T("Previous Frame", "上一帧") : T("Previous Image", "上一张图片"), () => Navigate(-1)));
        if (!IsVideoFrameMode)
        {
            menu.Items.Add(ContextItem(T("Previous Image In Same Folder", "同文件夹上一张"), () => NavigateSameFolder(-1), ActiveEntry?.IsFromArchive == false));
            menu.Items.Add(ContextItem(T("Next Image In Same Folder", "同文件夹下一张"), () => NavigateSameFolder(1), ActiveEntry?.IsFromArchive == false));
        }

        menu.Items.Add(ContextItem(IsVideoFrameMode ? T("Next Frame", "下一帧") : T("Next Image", "下一张图片"), () => Navigate(1)));
        menu.Items.Add(new Separator());
        menu.Items.Add(ContextItem(IsVideoFrameMode ? T("Copy Frame", "复制当前帧") : T("Copy Image", "复制图片"), CopyCurrentImage));
        menu.Items.Add(ContextItem(IsVideoFrameMode ? T("Copy Video Path", "复制视频路径") : T("Copy Image Path", "复制图片路径"), CopyCurrentImagePath));
        menu.Items.Add(ContextItem(T("Show In File Explorer", "在文件资源管理器中显示"), RevealCurrentImage, IsVideoFrameMode || ActiveEntry?.IsFromArchive == false));
        menu.Items.Add(ContextItem(T("Resample 30 Image Colors", "重新采样 30 个图片颜色"), SampleCurrentImageColors, IsVideoFrameMode || ActiveEntry is not null));
        menu.Items.Add(new Separator());
        menu.Items.Add(ContextItem(T("Flip Horizontal", "水平翻转"), ToggleFlipHorizontal));
        menu.Items.Add(ContextItem(T("Flip Vertical", "垂直翻转"), ToggleFlipVertical));
        menu.Items.Add(ContextItem(T("Rotate -90", "旋转 -90"), () => RotateCurrentImage(-90)));
        menu.Items.Add(ContextItem(T("Rotate +90", "旋转 +90"), () => RotateCurrentImage(90)));
        menu.Items.Add(ContextItem(IsVideoFrameMode ? T("Reset Current Video View", "重置当前视频视图") : T("Reset Current Image State", "重置当前图片状态"), () => ResetImageView_Click(this, new RoutedEventArgs())));
        menu.Items.Add(new Separator());
        menu.Items.Add(ContextItem(_state.StayOnTop ? T("Disable Stay On Top", "取消窗口置顶") : T("Stay On Top", "窗口置顶"), ToggleStayOnTop));
        menu.IsOpen = true;
    }

    private void ColorBlocksPage_MouseRightButtonUp(object sender, MouseButtonEventArgs e)
    {
        var menu = new ContextMenu();
        menu.Items.Add(ContextItem(T("Refresh Colors", "刷新颜色"), () => RefreshColors_Click(this, new RoutedEventArgs())));
        menu.Items.Add(ContextItem(T("Increase Colors", "增加颜色"), () => IncreaseColors_Click(this, new RoutedEventArgs())));
        menu.Items.Add(ContextItem(T("Decrease Colors", "减少颜色"), () => DecreaseColors_Click(this, new RoutedEventArgs())));
        menu.Items.Add(ContextItem(T("Shape Mode", "形状模式"), () => ShapeMode_Click(this, new RoutedEventArgs())));
        menu.Items.Add(new Separator());
        menu.Items.Add(ContextItem(T("Copy Colors", "复制颜色"), () => CopyColors_Click(this, new RoutedEventArgs())));
        menu.Items.Add(ContextItem(_state.StayOnTop ? T("Disable Stay On Top", "取消窗口置顶") : T("Stay On Top", "窗口置顶"), ToggleStayOnTop));
        menu.IsOpen = true;
    }

    private static MenuItem ContextItem(string header, Action action, bool enabled = true)
    {
        var item = new MenuItem { Header = header, IsEnabled = enabled };
        item.Click += (_, _) => action();
        return item;
    }

    private void ToggleFlipHorizontal()
    {
        _state.FlipHorizontal = !_state.FlipHorizontal;
        ApplyImageViewState();
        UpdateAllUi();
    }

    private void ToggleFlipVertical()
    {
        _state.FlipVertical = !_state.FlipVertical;
        ApplyImageViewState();
        UpdateAllUi();
    }

    private void ToggleStayOnTop()
    {
        _state.StayOnTop = !_state.StayOnTop;
        UpdateAllUi();
    }

    private void RotateCurrentImage(int delta)
    {
        var state = GetCurrentImageViewState();
        state.Rotation = NormalizeRotation(state.Rotation + delta);
        ApplyImageViewState();
    }

    private void CopyCurrentImage()
    {
        if (!IsImageMode || ActiveImage.Source is null)
        {
            return;
        }

        var bitmap = CaptureActiveViewport();
        if (bitmap is null)
        {
            return;
        }

        System.Windows.Clipboard.SetImage(bitmap);
        ShowToast(T("Image copied", "图片已复制"));
    }

    private BitmapSource? CaptureActiveViewport()
    {
        var viewport = ActiveViewport;
        viewport.UpdateLayout();

        var width = viewport.ActualWidth;
        var height = viewport.ActualHeight;
        if (width <= 0 || height <= 0)
        {
            return null;
        }

        var dpi = VisualTreeHelper.GetDpi(viewport);
        var pixelWidth = Math.Max(1, (int)Math.Ceiling(width * dpi.DpiScaleX));
        var pixelHeight = Math.Max(1, (int)Math.Ceiling(height * dpi.DpiScaleY));
        var bitmap = new RenderTargetBitmap(
            pixelWidth,
            pixelHeight,
            96.0 * dpi.DpiScaleX,
            96.0 * dpi.DpiScaleY,
            PixelFormats.Pbgra32);
        bitmap.Render(viewport);
        bitmap.Freeze();
        return bitmap;
    }

    private void CopyCurrentImagePath()
    {
        var path = IsVideoFrameMode ? ActiveModeState().ImageRootPath : ActiveEntry?.Path ?? "";
        if (string.IsNullOrWhiteSpace(path))
        {
            return;
        }

        System.Windows.Clipboard.SetText(path);
        ShowToast(IsVideoFrameMode ? T("Video path copied", "视频路径已复制") : T("Image path copied", "图片路径已复制"));
    }

    private void RevealCurrentImage()
    {
        var path = IsVideoFrameMode ? ActiveModeState().ImageRootPath : ActiveEntry?.Path ?? "";
        if (string.IsNullOrWhiteSpace(path) || (!IsVideoFrameMode && ActiveEntry?.IsFromArchive == true))
        {
            return;
        }

        Process.Start(new ProcessStartInfo
        {
            FileName = "explorer.exe",
            Arguments = "/select,\"" + path + "\"",
            UseShellExecute = true
        });
    }

    private void ColorBlocksCanvas_SizeChanged(object sender, SizeChangedEventArgs e) => RenderColorBlocks();

    private void ColorBlocksPage_MouseWheel(object sender, MouseWheelEventArgs e)
    {
        if ((Keyboard.Modifiers & ModifierKeys.Control) == 0)
        {
            return;
        }

        if (e.Delta > 0)
        {
            IncreaseColors_Click(sender, e);
        }
        else
        {
            DecreaseColors_Click(sender, e);
        }
    }

    private void TimerText_MouseLeftButtonUp(object sender, MouseButtonEventArgs e) => ToggleTimer();

    private void Window_KeyDown(object sender, System.Windows.Input.KeyEventArgs e)
    {
        if (e.Key is Key.PageDown or Key.Right)
        {
            Navigate(1);
            e.Handled = true;
        }
        else if (e.Key is Key.PageUp or Key.Left)
        {
            Navigate(-1);
            e.Handled = true;
        }
        else if (e.Key == Key.Space)
        {
            ToggleTimer();
            e.Handled = true;
        }
        else if (e.Key == Key.C && Keyboard.Modifiers.HasFlag(ModifierKeys.Control))
        {
            CopyCurrentImage();
            e.Handled = true;
        }
    }

    private void Window_SizeChanged(object sender, SizeChangedEventArgs e)
    {
        if (WindowState == WindowState.Normal)
        {
            _state.WindowWidth = Math.Max(360, (int)Math.Round(Width));
            _state.WindowHeight = Math.Max(360, (int)Math.Round(Height));
        }

        ApplyViewportLayout();
    }

    private void Window_Closing(object? sender, System.ComponentModel.CancelEventArgs e)
    {
        _isClosing = true;
        CancelVideoFrameLoad();
        SaveCurrentImageViewState();
        if (WindowState == WindowState.Normal)
        {
            _state.WindowWidth = Math.Max(360, (int)Math.Round(Width));
            _state.WindowHeight = Math.Max(360, (int)Math.Round(Height));
        }

        foreach (var pair in _entriesByMode)
        {
            if (pair.Key is AppMode.PhotoSwitching or AppMode.ColorPhoto)
            {
                var modeState = _state.GetModeState(pair.Key);
                if (string.IsNullOrWhiteSpace(modeState.ImageRootPath))
                {
                    continue;
                }

                var pathState = modeState.GetPathPlaybackState(modeState.ImageRootPath);
                if (pathState.UseCustomImageOrder)
                {
                    pathState.ImageOrder = pair.Value.Select(entry => entry.Path).ToList();
                    modeState.ImageOrder = pathState.ImageOrder.ToList();
                }
            }
        }

        StateStore.Save(_state);
        _videoFrameLoadCts.Dispose();
        _videoFrameCache.Dispose();
        _imageLibrary.Dispose();
    }
}
