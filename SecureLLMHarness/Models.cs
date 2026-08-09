namespace SecureLLMHarness;

public sealed record CliOptions(FileInfo? CsvFile, string? Provider, string? Url, string? ApiKey, string? ApiKeyEnvironmentVariable,
    string? Model, int TimeoutSeconds, bool Verbose, bool Quiet, FileInfo? ResultsFile);

public sealed record TestCase(string Provider, Uri BaseUrl, string ApiKey, string Model, int RowNumber);

public sealed record TestResult(string Provider, string Model, bool Success, long LatencyMs, string StatusMessage, int? HttpStatusCode);

public sealed class InputException(string message) : Exception(message);
