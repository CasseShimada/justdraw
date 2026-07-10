namespace JustDraw.Wpf;

public interface IViewportController
{
    bool IsViewportAspectRatioLocked { get; }

    double ViewportAspectRatio { get; }

    void SetViewportAspectRatio(double width, double height, bool lockAspectRatio = true);

    void SetViewportAspectRatioLock(bool enabled);
}

internal static class ViewportAspectRatioLayout
{
    public const double DefaultAspectRatio = 16.0 / 9.0;

    private const double MinAspectRatio = 0.01;
    private const double MaxAspectRatio = 100.0;

    public static double CalculateAspectRatio(double width, double height)
    {
        if (!double.IsFinite(width) || width <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(width), "Viewport width ratio must be a finite positive number.");
        }

        if (!double.IsFinite(height) || height <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(height), "Viewport height ratio must be a finite positive number.");
        }

        var aspectRatio = width / height;
        if (!IsValid(aspectRatio))
        {
            throw new ArgumentOutOfRangeException(nameof(width), $"Viewport aspect ratio must be between {MinAspectRatio} and {MaxAspectRatio}.");
        }

        return aspectRatio;
    }

    public static double Normalize(double aspectRatio)
    {
        return IsValid(aspectRatio) ? aspectRatio : DefaultAspectRatio;
    }

    public static (double Width, double Height) Fit(double availableWidth, double availableHeight, double aspectRatio)
    {
        if (!double.IsFinite(availableWidth) || !double.IsFinite(availableHeight) || availableWidth <= 0 || availableHeight <= 0)
        {
            return (0, 0);
        }

        aspectRatio = Normalize(aspectRatio);
        var width = availableWidth;
        var height = width / aspectRatio;
        if (height > availableHeight)
        {
            height = availableHeight;
            width = height * aspectRatio;
        }

        return (width, height);
    }

    private static bool IsValid(double aspectRatio)
    {
        return double.IsFinite(aspectRatio) && aspectRatio >= MinAspectRatio && aspectRatio <= MaxAspectRatio;
    }
}
