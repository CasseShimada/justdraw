using System.IO;
using System.IO.Compression;
using System.Text.RegularExpressions;

namespace JustDraw.Wpf;

public sealed class ImageEntry
{
    public ImageEntry(string path, string? sourceArchive = null, string? sortPath = null)
    {
        Path = path;
        SourceArchive = sourceArchive;
        SortPath = sortPath ?? path;
    }

    public string Path { get; }
    public string? SourceArchive { get; }
    public string SortPath { get; }
    public bool IsFromArchive => !string.IsNullOrWhiteSpace(SourceArchive);
}

public sealed class ImageLibrary : IDisposable
{
    private static readonly HashSet<string> ImageExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"
    };
    private static readonly Regex NumberRegex = new(@"\d+", RegexOptions.Compiled);

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
            SortNatural(result);
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

        SortNatural(result);
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
                result.Add(new ImageEntry(targetPath, path, System.IO.Path.Combine(path, entry.FullName)));
            }
        }
        catch
        {
            // Bad archives are skipped just like unsupported files.
        }
    }

    public static void SortNatural(List<ImageEntry> entries)
    {
        entries.Sort((left, right) => NaturalCompare(left.SortPath, right.SortPath));
    }

    public static int NaturalCompare(string? left, string? right)
    {
        left ??= "";
        right ??= "";

        var leftParts = NumberRegex.Split(left);
        var rightParts = NumberRegex.Split(right);
        var leftNumbers = NumberRegex.Matches(left);
        var rightNumbers = NumberRegex.Matches(right);
        var count = Math.Max(leftParts.Length, rightParts.Length);
        for (var i = 0; i < count; i++)
        {
            if (i < leftParts.Length && i < rightParts.Length)
            {
                var textCompare = string.Compare(leftParts[i], rightParts[i], StringComparison.CurrentCultureIgnoreCase);
                if (textCompare != 0)
                {
                    return textCompare;
                }
            }
            else
            {
                return leftParts.Length.CompareTo(rightParts.Length);
            }

            if (i >= leftNumbers.Count || i >= rightNumbers.Count)
            {
                continue;
            }

            var numberCompare = CompareNumberText(leftNumbers[i].Value, rightNumbers[i].Value);
            if (numberCompare != 0)
            {
                return numberCompare;
            }
        }

        return string.Compare(left, right, StringComparison.CurrentCultureIgnoreCase);
    }

    private static int CompareNumberText(string left, string right)
    {
        var trimmedLeft = left.TrimStart('0');
        var trimmedRight = right.TrimStart('0');
        if (trimmedLeft.Length == 0)
        {
            trimmedLeft = "0";
        }

        if (trimmedRight.Length == 0)
        {
            trimmedRight = "0";
        }

        var lengthCompare = trimmedLeft.Length.CompareTo(trimmedRight.Length);
        if (lengthCompare != 0)
        {
            return lengthCompare;
        }

        var valueCompare = string.CompareOrdinal(trimmedLeft, trimmedRight);
        return valueCompare != 0 ? valueCompare : left.Length.CompareTo(right.Length);
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
