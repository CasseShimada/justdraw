using System.IO;
using System.IO.Compression;

namespace JustDraw.Wpf;

public sealed class ImageEntry
{
    public ImageEntry(string path, string? sourceArchive = null)
    {
        Path = path;
        SourceArchive = sourceArchive;
    }

    public string Path { get; }
    public string? SourceArchive { get; }
    public bool IsFromArchive => !string.IsNullOrWhiteSpace(SourceArchive);
}

public sealed class ImageLibrary : IDisposable
{
    private static readonly HashSet<string> ImageExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"
    };

    private readonly List<string> _tempDirectories = [];

    public List<ImageEntry> Load(string sourcePath)
    {
        var result = new List<ImageEntry>();
        if (string.IsNullOrWhiteSpace(sourcePath))
        {
            return result;
        }

        if (File.Exists(sourcePath))
        {
            AddFile(result, sourcePath);
            return result;
        }

        if (!Directory.Exists(sourcePath))
        {
            return result;
        }

        foreach (var file in Directory.EnumerateFiles(sourcePath, "*", SearchOption.AllDirectories))
        {
            AddFile(result, file);
        }

        return result;
    }

    private void AddFile(List<ImageEntry> result, string path)
    {
        var extension = System.IO.Path.GetExtension(path);
        if (ImageExtensions.Contains(extension))
        {
            result.Add(new ImageEntry(path));
            return;
        }

        if (!extension.Equals(".zip", StringComparison.OrdinalIgnoreCase))
        {
            return;
        }

        try
        {
            var tempDir = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "JustDrawZip_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(tempDir);
            _tempDirectories.Add(tempDir);

            using var archive = ZipFile.OpenRead(path);
            foreach (var entry in archive.Entries)
            {
                if (string.IsNullOrWhiteSpace(entry.Name))
                {
                    continue;
                }

                if (!ImageExtensions.Contains(System.IO.Path.GetExtension(entry.Name)))
                {
                    continue;
                }

                var targetPath = System.IO.Path.Combine(tempDir, Guid.NewGuid().ToString("N") + "_" + entry.Name);
                entry.ExtractToFile(targetPath, overwrite: true);
                result.Add(new ImageEntry(targetPath, path));
            }
        }
        catch
        {
            // Bad archives are skipped just like unsupported files.
        }
    }

    public void Dispose()
    {
        foreach (var directory in _tempDirectories)
        {
            try
            {
                if (Directory.Exists(directory))
                {
                    Directory.Delete(directory, recursive: true);
                }
            }
            catch
            {
                // Temporary cleanup is best effort.
            }
        }
    }
}
