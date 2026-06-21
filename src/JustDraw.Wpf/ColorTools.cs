using MediaColor = System.Windows.Media.Color;

namespace JustDraw.Wpf;

public static class ColorTools
{
    public static List<MediaColor> GeneratePalette(int count, double minLuma, double maxLuma, double minSaturation)
    {
        var colors = new List<MediaColor>();
        var random = Random.Shared;
        var attempts = 0;

        while (colors.Count < count && attempts < count * 200)
        {
            attempts++;
            var hue = random.NextDouble() * 360.0;
            var saturation = minSaturation + random.NextDouble() * (1.0 - minSaturation);
            var lightness = 0.22 + random.NextDouble() * 0.58;
            var color = FromHsl(hue, saturation, lightness);
            var luma = RelativeLuma(color);
            if (luma < minLuma || luma > maxLuma)
            {
                continue;
            }

            colors.Add(color);
        }

        while (colors.Count < count)
        {
            colors.Add(MediaColor.FromRgb(128, 128, 128));
        }

        return colors;
    }

    public static double RelativeLuma(MediaColor color)
    {
        return (0.2126 * color.R + 0.7152 * color.G + 0.0722 * color.B) / 255.0;
    }

    public static MediaColor ToGrayscale(MediaColor color)
    {
        var gray = (byte)Math.Clamp(Math.Round(0.299 * color.R + 0.587 * color.G + 0.114 * color.B), 0, 255);
        return MediaColor.FromArgb(color.A, gray, gray, gray);
    }

    private static MediaColor FromHsl(double h, double s, double l)
    {
        h = ((h % 360) + 360) % 360;
        var c = (1 - Math.Abs(2 * l - 1)) * s;
        var x = c * (1 - Math.Abs((h / 60.0) % 2 - 1));
        var m = l - c / 2;
        double r1;
        double g1;
        double b1;

        if (h < 60) { r1 = c; g1 = x; b1 = 0; }
        else if (h < 120) { r1 = x; g1 = c; b1 = 0; }
        else if (h < 180) { r1 = 0; g1 = c; b1 = x; }
        else if (h < 240) { r1 = 0; g1 = x; b1 = c; }
        else if (h < 300) { r1 = x; g1 = 0; b1 = c; }
        else { r1 = c; g1 = 0; b1 = x; }

        return MediaColor.FromRgb(
            (byte)Math.Clamp(Math.Round((r1 + m) * 255), 0, 255),
            (byte)Math.Clamp(Math.Round((g1 + m) * 255), 0, 255),
            (byte)Math.Clamp(Math.Round((b1 + m) * 255), 0, 255));
    }
}
