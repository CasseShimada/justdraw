using JustDraw.Wpf;
using Xunit;

namespace JustDraw.Wpf.Tests;

public sealed class VideoFrameCacheTests
{
    private static readonly VideoToolsInfo AvailableTools = new("ffmpeg", "ffprobe", true, "");

    [Fact]
    public async Task OpenAsync_NewerOpenWinsWhenOlderProbeFinishesLast()
    {
        var firstPath = Path.GetTempFileName();
        var secondPath = Path.GetTempFileName();
        var firstProbe = CreateProbeCompletion();
        var secondProbe = CreateProbeCompletion();
        using var cache = new VideoFrameCache((_, path, _) => path == firstPath ? firstProbe.Task : secondProbe.Task);
        try
        {
            var firstOpen = cache.OpenAsync(AvailableTools, firstPath);
            var secondOpen = cache.OpenAsync(AvailableTools, secondPath);

            var secondInfo = CreateVideoInfo(secondPath);
            secondProbe.SetResult(secondInfo);
            Assert.Equal(secondInfo, await secondOpen);

            firstProbe.SetResult(CreateVideoInfo(firstPath));
            await Assert.ThrowsAsync<OperationCanceledException>(() => firstOpen);
            Assert.Equal(secondInfo, cache.CurrentVideo);
        }
        finally
        {
            File.Delete(firstPath);
            File.Delete(secondPath);
        }
    }

    [Fact]
    public async Task Clear_InvalidatesPendingOpen()
    {
        var path = Path.GetTempFileName();
        var probe = CreateProbeCompletion();
        using var cache = new VideoFrameCache((_, _, _) => probe.Task);
        try
        {
            var open = cache.OpenAsync(AvailableTools, path);

            cache.Clear();
            probe.SetResult(CreateVideoInfo(path));

            await Assert.ThrowsAsync<OperationCanceledException>(() => open);
            Assert.Null(cache.CurrentVideo);
        }
        finally
        {
            File.Delete(path);
        }
    }

    private static TaskCompletionSource<VideoFrameInfo> CreateProbeCompletion()
    {
        return new TaskCompletionSource<VideoFrameInfo>(TaskCreationOptions.RunContinuationsAsynchronously);
    }

    private static VideoFrameInfo CreateVideoInfo(string path)
    {
        return new VideoFrameInfo(path, 1, 30, 30, 640, 480);
    }
}
