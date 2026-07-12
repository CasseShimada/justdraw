using JustDraw.Wpf;
using Xunit;

namespace JustDraw.Wpf.Tests;

public sealed class ViewportAspectRatioLayoutTests
{
    [Theory]
    [InlineData("16:9", 16, 9)]
    [InlineData("16/9", 16, 9)]
    [InlineData("16x9", 16, 9)]
    [InlineData("16X9", 16, 9)]
    [InlineData("16×9", 16, 9)]
    [InlineData("16：9", 16, 9)]
    [InlineData("1.85", 1.85, 1)]
    public void TryParse_AcceptsSupportedFormats(string value, double expectedWidth, double expectedHeight)
    {
        var parsed = ViewportAspectRatioLayout.TryParse(value, out var width, out var height);

        Assert.True(parsed);
        Assert.Equal(expectedWidth, width, 8);
        Assert.Equal(expectedHeight, height, 8);
    }

    [Theory]
    [InlineData("")]
    [InlineData(" ")]
    [InlineData("0")]
    [InlineData("-1")]
    [InlineData("NaN")]
    [InlineData("Infinity")]
    [InlineData("16:")]
    [InlineData(":9")]
    [InlineData("16::9")]
    [InlineData("1e309")]
    [InlineData("1:5")]
    [InlineData("5:1")]
    public void TryParse_RejectsInvalidOrUnsupportedRatios(string value)
    {
        Assert.False(ViewportAspectRatioLayout.TryParse(value, out _, out _));
    }

    [Theory]
    [InlineData(0, 1)]
    [InlineData(1, 0)]
    [InlineData(-1, 1)]
    [InlineData(1, -1)]
    [InlineData(double.NaN, 1)]
    [InlineData(1, double.PositiveInfinity)]
    public void CalculateAspectRatio_RejectsInvalidDimensions(double width, double height)
    {
        Assert.Throws<ArgumentOutOfRangeException>(() => ViewportAspectRatioLayout.CalculateAspectRatio(width, height));
    }

    [Fact]
    public void CalculateAspectRatio_AllowsPersistedRatiosOutsideCustomInputRange()
    {
        Assert.Equal(8, ViewportAspectRatioLayout.CalculateAspectRatio(1600, 200), 8);
        Assert.Equal(5, ViewportAspectRatioLayout.Normalize(5), 8);
    }

    [Fact]
    public void ResolveAspectRatio_PrefersCurrentDisplayArea()
    {
        var ratio = ViewportAspectRatioLayout.ResolveAspectRatio(900, 600, 1920, 1080, 1);

        Assert.Equal(1.5, ratio, 8);
    }

    [Fact]
    public void ResolveAspectRatio_FallsBackToImageThenStoredThenDefault()
    {
        Assert.Equal(8, ViewportAspectRatioLayout.ResolveAspectRatio(1600, 200, 800, 600, 1), 8);
        Assert.Equal(4.0 / 3.0, ViewportAspectRatioLayout.ResolveAspectRatio(0, 0, 800, 600, 1), 8);
        Assert.Equal(5, ViewportAspectRatioLayout.ResolveAspectRatio(0, 0, 0, 0, 5), 8);
        Assert.Equal(ViewportAspectRatioLayout.DefaultAspectRatio,
            ViewportAspectRatioLayout.ResolveAspectRatio(0, 0, 0, 0, double.NaN), 8);
    }

    [Fact]
    public void CalculateMinimumOuterSize_KeepsDefaultMinimumsWhenTheyFit()
    {
        var size = ViewportAspectRatioLayout.CalculateMinimumOuterSize(
            16.0 / 9.0,
            new AspectRatioInsets(16, 64),
            320,
            320,
            1920,
            1080);

        Assert.Equal(320, size.Width, 8);
        Assert.Equal(320, size.Height, 8);
    }

    [Fact]
    public void CalculateMinimumOuterSize_TallRatioPreservesDefaultHeight()
    {
        var size = ViewportAspectRatioLayout.CalculateMinimumOuterSize(
            0.25,
            new AspectRatioInsets(16, 64),
            320,
            320,
            1920,
            1080);

        Assert.Equal(80, size.Width, 8);
        Assert.Equal(320, size.Height, 8);
        AssertContentRatio(size, new AspectRatioInsets(16, 64), 0.25);

        var maximum = ViewportAspectRatioLayout.ConstrainOuterSize(
            1920,
            1080,
            0.25,
            new AspectRatioInsets(16, 64),
            size.Width,
            size.Height,
            1920,
            1080,
            AspectRatioDriver.Nearest);
        Assert.True(maximum.Width > size.Width);
        Assert.True(maximum.Height > size.Height);
    }

    [Fact]
    public void CalculateMinimumOuterSize_WideRatioPreservesDefaultWidth()
    {
        var size = ViewportAspectRatioLayout.CalculateMinimumOuterSize(
            4,
            new AspectRatioInsets(16, 64),
            320,
            320,
            600,
            1080);

        Assert.Equal(320, size.Width, 8);
        Assert.Equal(140, size.Height, 8);
        AssertContentRatio(size, new AspectRatioInsets(16, 64), 4);
    }

    [Fact]
    public void CalculateMinimumOuterSize_LeavesResizeRangeWhenNeitherDefaultAxisFits()
    {
        var size = ViewportAspectRatioLayout.CalculateMinimumOuterSize(
            1,
            new AspectRatioInsets(16, 64),
            320,
            320,
            200,
            200);

        Assert.Equal(17, size.Width, 8);
        Assert.Equal(65, size.Height, 8);
        AssertContentRatio(size, new AspectRatioInsets(16, 64), 1);
    }

    [Fact]
    public void ConstrainOuterSize_WidthDrivesHeight()
    {
        var size = ViewportAspectRatioLayout.ConstrainOuterSize(
            816,
            700,
            16.0 / 9.0,
            new AspectRatioInsets(16, 48),
            320,
            320,
            1920,
            1080,
            AspectRatioDriver.Width);

        Assert.Equal(816, size.Width, 6);
        Assert.Equal(498, size.Height, 6);
        AssertContentRatio(size, new AspectRatioInsets(16, 48), 16.0 / 9.0);
    }

    [Fact]
    public void ConstrainOuterSize_HeightDrivesWidth()
    {
        var size = ViewportAspectRatioLayout.ConstrainOuterSize(
            900,
            648,
            16.0 / 9.0,
            new AspectRatioInsets(16, 48),
            320,
            320,
            1920,
            1080,
            AspectRatioDriver.Height);

        Assert.Equal(1082.666667, size.Width, 6);
        Assert.Equal(648, size.Height, 6);
        AssertContentRatio(size, new AspectRatioInsets(16, 48), 16.0 / 9.0);
    }

    [Fact]
    public void ConstrainOuterSize_PreservesWorkAreaAndRatioWhenMinimumsCannotFit()
    {
        var size = ViewportAspectRatioLayout.ConstrainOuterSize(
            1920,
            1080,
            0.25,
            new AspectRatioInsets(16, 64),
            320,
            320,
            1920,
            1080,
            AspectRatioDriver.Nearest);

        Assert.True(size.Width <= 1920);
        Assert.True(size.Height <= 1080);
        Assert.True(size.Width < 320 || size.Height < 320);
        AssertContentRatio(size, new AspectRatioInsets(16, 64), 0.25);
    }

    [Theory]
    [InlineData((int)WindowSizingEdge.Left)]
    [InlineData((int)WindowSizingEdge.Right)]
    public void ConstrainSizingRect_SideEdgesKeepOppositeEdgeAndVerticalCenter(int edgeValue)
    {
        var edge = (WindowSizingEdge)edgeValue;
        var requested = new AspectRatioRect(100, 200, 916, 800);
        var constrained = ViewportAspectRatioLayout.ConstrainSizingRect(
            requested,
            edge,
            16.0 / 9.0,
            new AspectRatioInsets(16, 48),
            320,
            320);

        Assert.Equal(500, (constrained.Top + constrained.Bottom) / 2, 6);
        Assert.Equal(edge == WindowSizingEdge.Left ? requested.Right : requested.Left,
            edge == WindowSizingEdge.Left ? constrained.Right : constrained.Left, 6);
        AssertRectContentRatio(constrained, new AspectRatioInsets(16, 48), 16.0 / 9.0);
    }

    [Theory]
    [InlineData((int)WindowSizingEdge.Top)]
    [InlineData((int)WindowSizingEdge.Bottom)]
    public void ConstrainSizingRect_TopAndBottomKeepOppositeEdgeAndHorizontalCenter(int edgeValue)
    {
        var edge = (WindowSizingEdge)edgeValue;
        var requested = new AspectRatioRect(100, 200, 1100, 698);
        var constrained = ViewportAspectRatioLayout.ConstrainSizingRect(
            requested,
            edge,
            16.0 / 9.0,
            new AspectRatioInsets(16, 48),
            320,
            320);

        Assert.Equal(600, (constrained.Left + constrained.Right) / 2, 6);
        Assert.Equal(edge == WindowSizingEdge.Top ? requested.Bottom : requested.Top,
            edge == WindowSizingEdge.Top ? constrained.Bottom : constrained.Top, 6);
        AssertRectContentRatio(constrained, new AspectRatioInsets(16, 48), 16.0 / 9.0);
    }

    [Theory]
    [InlineData((int)WindowSizingEdge.TopLeft)]
    [InlineData((int)WindowSizingEdge.TopRight)]
    [InlineData((int)WindowSizingEdge.BottomLeft)]
    [InlineData((int)WindowSizingEdge.BottomRight)]
    public void ConstrainSizingRect_CornersKeepOppositeCorner(int edgeValue)
    {
        var edge = (WindowSizingEdge)edgeValue;
        var requested = new AspectRatioRect(100, 200, 916, 800);
        var constrained = ViewportAspectRatioLayout.ConstrainSizingRect(
            requested,
            edge,
            16.0 / 9.0,
            new AspectRatioInsets(16, 48),
            320,
            320,
            AspectRatioDriver.Width);

        if (edge is WindowSizingEdge.TopLeft or WindowSizingEdge.BottomLeft)
        {
            Assert.Equal(requested.Right, constrained.Right, 6);
        }
        else
        {
            Assert.Equal(requested.Left, constrained.Left, 6);
        }

        if (edge is WindowSizingEdge.TopLeft or WindowSizingEdge.TopRight)
        {
            Assert.Equal(requested.Bottom, constrained.Bottom, 6);
        }
        else
        {
            Assert.Equal(requested.Top, constrained.Top, 6);
        }

        AssertRectContentRatio(constrained, new AspectRatioInsets(16, 48), 16.0 / 9.0);
    }

    [Fact]
    public void ConstrainSizingRect_HandlesDpiScaledPhysicalPixels()
    {
        var constrained = ViewportAspectRatioLayout.ConstrainSizingRect(
            new AspectRatioRect(0, 0, 1224, 900),
            WindowSizingEdge.Right,
            16.0 / 9.0,
            new AspectRatioInsets(24, 72),
            480,
            480);

        Assert.Equal(1224, constrained.Width, 6);
        Assert.Equal(747, constrained.Height, 6);
        AssertRectContentRatio(constrained, new AspectRatioInsets(24, 72), 16.0 / 9.0);
    }

    [Fact]
    public void ConstrainSizingRect_RespectsWorkAreaMaximums()
    {
        var constrained = ViewportAspectRatioLayout.ConstrainSizingRect(
            new AspectRatioRect(0, 0, 2000, 1400),
            WindowSizingEdge.Right,
            16.0 / 9.0,
            new AspectRatioInsets(16, 48),
            320,
            320,
            maxWidth: 1000,
            maxHeight: 800);

        Assert.True(constrained.Width <= 1000);
        Assert.True(constrained.Height <= 800);
        AssertRectContentRatio(constrained, new AspectRatioInsets(16, 48), 16.0 / 9.0);
    }

    [Fact]
    public void ConstrainSizingRect_TranslatesSideResizeInsideWorkArea()
    {
        var bounds = new AspectRatioRect(0, 0, 1920, 1080);
        var constrained = ViewportAspectRatioLayout.ConstrainSizingRect(
            new AspectRatioRect(100, 0, 1100, 400),
            WindowSizingEdge.Right,
            16.0 / 9.0,
            new AspectRatioInsets(16, 48),
            320,
            320,
            bounds: bounds);

        Assert.True(constrained.Left >= bounds.Left);
        Assert.True(constrained.Top >= bounds.Top);
        Assert.True(constrained.Right <= bounds.Right);
        Assert.True(constrained.Bottom <= bounds.Bottom);
        AssertRectContentRatio(constrained, new AspectRatioInsets(16, 48), 16.0 / 9.0);
    }

    [Fact]
    public void ConstrainSizingRect_AllowsSideResizeAcrossMonitorBoundary()
    {
        var constrained = ViewportAspectRatioLayout.ConstrainSizingRect(
            new AspectRatioRect(1500, 0, 2500, 400),
            WindowSizingEdge.Right,
            16.0 / 9.0,
            new AspectRatioInsets(16, 48),
            320,
            320,
            bounds: new AspectRatioRect(0, 0, 1920, 1080));

        Assert.True(constrained.Right > 1920);
        Assert.True(constrained.Top >= 0);
        AssertRectContentRatio(constrained, new AspectRatioInsets(16, 48), 16.0 / 9.0);
    }

    [Fact]
    public void ConstrainSizingRect_NearestCornerChoosesSmallestCorrection()
    {
        var constrained = ViewportAspectRatioLayout.ConstrainSizingRect(
            new AspectRatioRect(100, 200, 916, 800),
            WindowSizingEdge.BottomRight,
            16.0 / 9.0,
            new AspectRatioInsets(16, 48),
            320,
            320);

        Assert.Equal(816, constrained.Width, 6);
        Assert.Equal(498, constrained.Height, 6);
        AssertRectContentRatio(constrained, new AspectRatioInsets(16, 48), 16.0 / 9.0);
    }

    [Fact]
    public void RepeatedWidthChanges_DoNotAccumulateRatioDrift()
    {
        var insets = new AspectRatioInsets(16, 48);
        var size = new AspectRatioSize(816, 498);

        for (var i = 0; i < 100; i++)
        {
            size = ViewportAspectRatioLayout.ConstrainOuterSize(
                size.Width + 3.25,
                size.Height,
                16.0 / 9.0,
                insets,
                320,
                320,
                1920,
                1080,
                AspectRatioDriver.Width);
            AssertContentRatio(size, insets, 16.0 / 9.0);
        }
    }

    [Fact]
    public void ConstrainOuterSize_SanitizesNonFiniteInputs()
    {
        var size = ViewportAspectRatioLayout.ConstrainOuterSize(
            double.NaN,
            double.PositiveInfinity,
            double.NaN,
            new AspectRatioInsets(double.NaN, double.NegativeInfinity),
            320,
            320,
            1920,
            1080,
            AspectRatioDriver.Nearest);

        Assert.True(double.IsFinite(size.Width));
        Assert.True(double.IsFinite(size.Height));
        Assert.True(size.Width > 0);
        Assert.True(size.Height > 0);
    }

    [Fact]
    public void Matches_RejectsZeroAndNonFiniteDimensions()
    {
        Assert.False(ViewportAspectRatioLayout.Matches(0, 100, 1));
        Assert.False(ViewportAspectRatioLayout.Matches(100, double.NaN, 1));
    }

    private static void AssertContentRatio(AspectRatioSize size, AspectRatioInsets insets, double ratio)
    {
        Assert.Equal(ratio, (size.Width - insets.Width) / (size.Height - insets.Height), 8);
    }

    private static void AssertRectContentRatio(AspectRatioRect rect, AspectRatioInsets insets, double ratio)
    {
        Assert.Equal(ratio, (rect.Width - insets.Width) / (rect.Height - insets.Height), 8);
    }
}
