using System.Text.Json;

namespace SecureLLMHarness;

public static class Reporter
{
    public static void WriteConsole(IReadOnlyList<TestResult> results, bool verbose, bool quiet)
    {
        if (!quiet)
        {
            Console.WriteLine($"{"Provider",-18} {"Model",-30} {"Result",-7} {"Latency",9}  Status");
            Console.WriteLine(new string('-', 95));
            foreach (var result in results)
            {
                var state = result.Success ? "PASS" : "FAIL";
                var status = verbose && result.HttpStatusCode is not null ? $"HTTP {result.HttpStatusCode}: {result.StatusMessage}" : result.StatusMessage;
                Console.WriteLine($"{Truncate(result.Provider, 18),-18} {Truncate(result.Model, 30),-30} {state,-7} {result.LatencyMs,6} ms  {status}");
            }
        }
        Console.WriteLine($"Summary: total {results.Count}, passed {results.Count(x => x.Success)}, failed {results.Count(x => !x.Success)}.");
    }

    public static async Task WriteJsonAsync(FileInfo file, IReadOnlyList<TestResult> results, CancellationToken cancellationToken)
    {
        var directory = file.Directory;
        if (directory is not null && !directory.Exists) directory.Create();
        await using var stream = file.Open(FileMode.Create, FileAccess.Write, FileShare.None);
        await JsonSerializer.SerializeAsync(stream, results, new JsonSerializerOptions { WriteIndented = true }, cancellationToken);
        Console.WriteLine($"Results written to {file.FullName}");
    }

    private static string Truncate(string text, int width) => text.Length <= width ? text : text[..(width - 1)] + "…";
}
