using System.Globalization;

namespace JustDraw.Wpf;

public interface IViewportController
{
    bool IsViewportAspectRatioLocked { get; }

    double ViewportAspectRatio { get; }

    double ViewportWidth { get; }

    double ViewportHeight { get; }

    void SetViewportAspectRatio(double width, double height, bool lockAspectRatio = true);

    void SetViewportAspectRatioLock(bool enabled);

    void SetViewportWidth(double width);

    void SetViewportHeight(double height);
}

internal enum AspectRatioDriver
{
    Width,
    Height,
    Nearest
}

internal enum WindowSizingEdge
{
    Left = 1,
    Right = 2,
    Top = 3,
    TopLeft = 4,
    TopRight = 5,
    Bottom = 6,
    BottomLeft = 7,
    BottomRight = 8
}

internal readonly record struct AspectRatioInsets(double Width, double Height);

internal readonly record struct AspectRatioSize(double Width, double Height);

internal readonly record struct AspectRatioRect(double Left, double Top, double Right, double Bottom)
{
    public double Width => Math.Max(0, Right - Left);

    public double Height => Math.Max(0, Bottom - Top);
}

internal static class ViewportAspectRatioLayout
{
    public const double DefaultAspectRatio = 16.0 / 9.0;
    public const double MinCustomAspectRatio = 0.25;
    public const double MaxCustomAspectRatio = 4.0;

    private const double MinAspectRatio = 0.01;
    private const double MaxAspectRatio = 100.0;

    public static double CalculateAspectRatio(double width, double height)
    {
        if (!IsPositiveFinite(width))
        {
            throw new ArgumentOutOfRangeException(nameof(width), "Viewport width ratio must be a finite positive number.");
        }

        if (!IsPositiveFinite(height))
        {
            throw new ArgumentOutOfRangeException(nameof(height), "Viewport height ratio must be a finite positive number.");
        }

        var aspectRatio = width / height;
        if (!IsValid(aspectRatio))
        {
            throw new ArgumentOutOfRangeException(nameof(width), $"Viewport aspect ratio must be between {MinAspectRatio}:1 and {MaxAspectRatio}:1.");
        }

        return aspectRatio;
    }

    public static double Normalize(double aspectRatio)
    {
        return IsValid(aspectRatio) ? aspectRatio : DefaultAspectRatio;
    }

    public static double ResolveAspectRatio(
        double currentWidth,
        double currentHeight,
        double imageWidth,
        double imageHeight,
        double storedAspectRatio)
    {
        if (TryCalculateAspectRatio(currentWidth, currentHeight, out var currentAspectRatio))
        {
            return currentAspectRatio;
        }

        if (TryCalculateAspectRatio(imageWidth, imageHeight, out var imageAspectRatio))
        {
            return imageAspectRatio;
        }

        return Normalize(storedAspectRatio);
    }

    public static bool TryParse(string value, out double width, out double height)
    {
        width = 0;
        height = 0;
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var normalized = value.Trim()
            .Replace('：', ':')
            .Replace('×', ':')
            .Replace('x', ':')
            .Replace('X', ':')
            .Replace('/', ':');
        var parts = normalized.Split(':', StringSplitOptions.TrimEntries);
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
            if (parts[0].Length == 0
                || parts[1].Length == 0
                || !TryParsePositiveNumber(parts[0], out width)
                || !TryParsePositiveNumber(parts[1], out height))
            {
                return false;
            }
        }
        else
        {
            return false;
        }

        return TryCalculateAspectRatio(width, height, out var aspectRatio)
            && aspectRatio >= MinCustomAspectRatio
            && aspectRatio <= MaxCustomAspectRatio;
    }

    public static AspectRatioSize CalculateMinimumOuterSize(
        double aspectRatio,
        AspectRatioInsets insets,
        double defaultMinWidth,
        double defaultMinHeight,
        double maxWidth,
        double maxHeight)
    {
        aspectRatio = Normalize(aspectRatio);
        insets = new AspectRatioInsets(
            SanitizeNonNegative(insets.Width),
            SanitizeNonNegative(insets.Height));
        defaultMinWidth = SanitizePositive(defaultMinWidth, 1);
        defaultMinHeight = SanitizePositive(defaultMinHeight, 1);
        maxWidth = SanitizePositive(maxWidth, defaultMinWidth);
        maxHeight = SanitizePositive(maxHeight, defaultMinHeight);

        var widthAnchoredClientHeight = Math.Max(1, defaultMinWidth - insets.Width) / aspectRatio;
        var heightAnchoredClientHeight = Math.Max(1, defaultMinHeight - insets.Height);
        var maxClientWidth = Math.Max(0, maxWidth - insets.Width);
        var maxClientHeight = Math.Max(0, maxHeight - insets.Height);
        var maxCompatibleClientHeight = Math.Min(maxClientHeight, maxClientWidth / aspectRatio);

        if (Math.Max(widthAnchoredClientHeight, heightAnchoredClientHeight) <= maxCompatibleClientHeight + 0.01)
        {
            return new AspectRatioSize(defaultMinWidth, defaultMinHeight);
        }

        var minimumClientHeight = heightAnchoredClientHeight <= maxCompatibleClientHeight + 0.01
            ? heightAnchoredClientHeight
            : widthAnchoredClientHeight <= maxCompatibleClientHeight + 0.01
                ? widthAnchoredClientHeight
                : Math.Min(maxCompatibleClientHeight, Math.Max(1, 1 / aspectRatio));
        return BuildOuterSize(minimumClientHeight, aspectRatio, insets);
    }

    public static AspectRatioSize ConstrainOuterSize(
        double requestedWidth,
        double requestedHeight,
        double aspectRatio,
        AspectRatioInsets insets,
        double minWidth,
        double minHeight,
        double maxWidth,
        double maxHeight,
        AspectRatioDriver driver)
    {
        aspectRatio = Normalize(aspectRatio);
        insets = new AspectRatioInsets(
            SanitizeNonNegative(insets.Width),
            SanitizeNonNegative(insets.Height));
        minWidth = SanitizePositive(minWidth, 1);
        minHeight = SanitizePositive(minHeight, 1);
        maxWidth = Math.Max(minWidth, SanitizePositive(maxWidth, double.MaxValue / 4));
        maxHeight = Math.Max(minHeight, SanitizePositive(maxHeight, double.MaxValue / 4));
        requestedWidth = Math.Clamp(SanitizePositive(requestedWidth, minWidth), minWidth, maxWidth);
        requestedHeight = Math.Clamp(SanitizePositive(requestedHeight, minHeight), minHeight, maxHeight);

        var minClientWidth = Math.Max(1, minWidth - insets.Width);
        var minClientHeight = Math.Max(1, minHeight - insets.Height);
        var maxClientWidth = Math.Max(minClientWidth, maxWidth - insets.Width);
        var maxClientHeight = Math.Max(minClientHeight, maxHeight - insets.Height);
        var minAllowedClientHeight = Math.Max(minClientHeight, minClientWidth / aspectRatio);
        var maxAllowedClientHeight = Math.Min(maxClientHeight, maxClientWidth / aspectRatio);
        if (maxAllowedClientHeight < minAllowedClientHeight)
        {
            minAllowedClientHeight = maxAllowedClientHeight;
        }

        var widthDrivenClientHeight = Math.Clamp(
            Math.Max(1, requestedWidth - insets.Width) / aspectRatio,
            minAllowedClientHeight,
            maxAllowedClientHeight);
        var heightDrivenClientHeight = Math.Clamp(
            Math.Max(1, requestedHeight - insets.Height),
            minAllowedClientHeight,
            maxAllowedClientHeight);
        var widthDriven = BuildOuterSize(widthDrivenClientHeight, aspectRatio, insets);
        var heightDriven = BuildOuterSize(heightDrivenClientHeight, aspectRatio, insets);

        return driver switch
        {
            AspectRatioDriver.Width => widthDriven,
            AspectRatioDriver.Height => heightDriven,
            _ => DistanceSquared(widthDriven, requestedWidth, requestedHeight)
                <= DistanceSquared(heightDriven, requestedWidth, requestedHeight)
                    ? widthDriven
                    : heightDriven
        };
    }

    public static AspectRatioRect ConstrainSizingRect(
        AspectRatioRect requested,
        WindowSizingEdge edge,
        double aspectRatio,
        AspectRatioInsets insets,
        double minWidth,
        double minHeight,
        AspectRatioDriver cornerDriver = AspectRatioDriver.Nearest,
        double maxWidth = double.MaxValue / 4,
        double maxHeight = double.MaxValue / 4,
        AspectRatioRect? bounds = null)
    {
        var driver = edge switch
        {
            WindowSizingEdge.Left or WindowSizingEdge.Right => AspectRatioDriver.Width,
            WindowSizingEdge.Top or WindowSizingEdge.Bottom => AspectRatioDriver.Height,
            _ => cornerDriver
        };
        var size = ConstrainOuterSize(
            requested.Width,
            requested.Height,
            aspectRatio,
            insets,
            minWidth,
            minHeight,
            maxWidth,
            maxHeight,
            driver);

        var centerX = (requested.Left + requested.Right) / 2;
        var centerY = (requested.Top + requested.Bottom) / 2;
        AspectRatioRect constrained = edge switch
        {
            WindowSizingEdge.Left => new(requested.Right - size.Width, centerY - size.Height / 2, requested.Right, centerY + size.Height / 2),
            WindowSizingEdge.Right => new(requested.Left, centerY - size.Height / 2, requested.Left + size.Width, centerY + size.Height / 2),
            WindowSizingEdge.Top => new(centerX - size.Width / 2, requested.Bottom - size.Height, centerX + size.Width / 2, requested.Bottom),
            WindowSizingEdge.Bottom => new(centerX - size.Width / 2, requested.Top, centerX + size.Width / 2, requested.Top + size.Height),
            WindowSizingEdge.TopLeft => new(requested.Right - size.Width, requested.Bottom - size.Height, requested.Right, requested.Bottom),
            WindowSizingEdge.TopRight => new(requested.Left, requested.Bottom - size.Height, requested.Left + size.Width, requested.Bottom),
            WindowSizingEdge.BottomLeft => new(requested.Right - size.Width, requested.Top, requested.Right, requested.Top + size.Height),
            _ => new(requested.Left, requested.Top, requested.Left + size.Width, requested.Top + size.Height)
        };
        return bounds is { } availableBounds
            ? TranslateInsideBounds(
                constrained,
                availableBounds,
                constrainHorizontal: edge is WindowSizingEdge.Top or WindowSizingEdge.Bottom,
                constrainVertical: edge is WindowSizingEdge.Left or WindowSizingEdge.Right)
            : constrained;
    }

    public static bool Matches(double width, double height, double aspectRatio, double tolerance = 0.001)
    {
        return TryCalculateAspectRatio(width, height, out var actual)
            && Math.Abs(actual - Normalize(aspectRatio)) <= Math.Max(tolerance, tolerance * aspectRatio);
    }

    private static bool TryCalculateAspectRatio(double width, double height, out double aspectRatio)
    {
        aspectRatio = 0;
        if (!IsPositiveFinite(width) || !IsPositiveFinite(height))
        {
            return false;
        }

        var candidate = width / height;
        if (!IsValid(candidate))
        {
            return false;
        }

        aspectRatio = candidate;
        return true;
    }

    private static bool TryParsePositiveNumber(string value, out double number)
    {
        var parsed = double.TryParse(value, NumberStyles.Float, CultureInfo.CurrentCulture, out number)
            || double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out number);
        return parsed && IsPositiveFinite(number);
    }

    private static AspectRatioSize BuildOuterSize(double clientHeight, double aspectRatio, AspectRatioInsets insets)
    {
        return new AspectRatioSize(clientHeight * aspectRatio + insets.Width, clientHeight + insets.Height);
    }

    private static double DistanceSquared(AspectRatioSize size, double requestedWidth, double requestedHeight)
    {
        var deltaWidth = size.Width - requestedWidth;
        var deltaHeight = size.Height - requestedHeight;
        return deltaWidth * deltaWidth + deltaHeight * deltaHeight;
    }

    private static AspectRatioRect TranslateInsideBounds(
        AspectRatioRect rect,
        AspectRatioRect bounds,
        bool constrainHorizontal,
        bool constrainVertical)
    {
        var offsetX = constrainHorizontal && rect.Left < bounds.Left
            ? bounds.Left - rect.Left
            : constrainHorizontal && rect.Right > bounds.Right
                ? bounds.Right - rect.Right
                : 0;
        var offsetY = constrainVertical && rect.Top < bounds.Top
            ? bounds.Top - rect.Top
            : constrainVertical && rect.Bottom > bounds.Bottom
                ? bounds.Bottom - rect.Bottom
                : 0;
        return new AspectRatioRect(
            rect.Left + offsetX,
            rect.Top + offsetY,
            rect.Right + offsetX,
            rect.Bottom + offsetY);
    }

    private static double SanitizeNonNegative(double value)
    {
        return double.IsFinite(value) && value > 0 ? value : 0;
    }

    private static double SanitizePositive(double value, double fallback)
    {
        return IsPositiveFinite(value) ? value : fallback;
    }

    private static bool IsPositiveFinite(double value)
    {
        return double.IsFinite(value) && value > 0;
    }

    private static bool IsValid(double aspectRatio)
    {
        return double.IsFinite(aspectRatio)
            && aspectRatio >= MinAspectRatio
            && aspectRatio <= MaxAspectRatio;
    }
}
