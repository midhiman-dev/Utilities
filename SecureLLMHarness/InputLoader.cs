using System.Text;

namespace SecureLLMHarness;

public static class InputLoader
{
    public static IReadOnlyList<TestCase> Load(CliOptions options)
    {
        if (options.CsvFile is not null)
        {
            if (!string.IsNullOrWhiteSpace(options.Provider) || !string.IsNullOrWhiteSpace(options.Url) || !string.IsNullOrWhiteSpace(options.Model))
                throw new InputException("Use either --csv or a single --provider, --url, and --model set.");
            return LoadCsv(options.CsvFile);
        }

        if (string.IsNullOrWhiteSpace(options.Provider) || string.IsNullOrWhiteSpace(options.Url) || string.IsNullOrWhiteSpace(options.Model))
            throw new InputException("Specify --csv, or all of --provider, --url, and --model.");
        var apiKey = ResolveApiKey(options.ApiKey, options.ApiKeyEnvironmentVariable);
        return [CreateCase(options.Provider, options.Url, apiKey, options.Model, 0)];
    }

    private static IReadOnlyList<TestCase> LoadCsv(FileInfo file)
    {
        if (!file.Exists) throw new InputException($"CSV file was not found: {file.FullName}");
        using var reader = new StreamReader(file.FullName, Encoding.UTF8, detectEncodingFromByteOrderMarks: true);
        var header = reader.ReadLine();
        if (header is null) throw new InputException("CSV file is empty.");
        var indexes = ParseCsvLine(header).Select((name, index) => (name: name.Trim(), index))
            .ToDictionary(x => x.name, x => x.index, StringComparer.OrdinalIgnoreCase);
        foreach (var required in new[] { "Provider", "Url", "ApiKey", "Model" })
            if (!indexes.ContainsKey(required)) throw new InputException($"CSV header must contain '{required}'.");

        var cases = new List<TestCase>();
        string? line;
        var row = 1;
        while ((line = reader.ReadLine()) is not null)
        {
            row++;
            if (string.IsNullOrWhiteSpace(line)) continue;
            var fields = ParseCsvLine(line);
            string Value(string column) => indexes[column] < fields.Count ? fields[indexes[column]].Trim() : string.Empty;
            cases.Add(CreateCase(Value("Provider"), Value("Url"), Value("ApiKey"), Value("Model"), row));
        }
        if (cases.Count == 0) throw new InputException("CSV contains no test rows.");
        return cases;
    }

    private static TestCase CreateCase(string provider, string url, string apiKey, string model, int row)
    {
        if (string.IsNullOrWhiteSpace(provider) || string.IsNullOrWhiteSpace(url) || string.IsNullOrWhiteSpace(model))
            throw new InputException($"Row {row}: Provider, Url, and Model are required.");
        if (!Uri.TryCreate(url, UriKind.Absolute, out var uri) || uri.Scheme is not ("https" or "http"))
            throw new InputException($"Row {row}: Url must be an absolute http(s) URL.");
        return new TestCase(provider, uri, apiKey, model, row);
    }

    private static string ResolveApiKey(string? directValue, string? environmentVariable)
    {
        if (!string.IsNullOrWhiteSpace(directValue)) return directValue;
        var envName = string.IsNullOrWhiteSpace(environmentVariable) ? "OPENAI_API_KEY" : environmentVariable;
        return Environment.GetEnvironmentVariable(envName) ?? string.Empty;
    }

    // RFC 4180-compatible for a single physical record. Multiline quoted fields are intentionally rejected.
    private static List<string> ParseCsvLine(string line)
    {
        var result = new List<string>(); var field = new StringBuilder(); var quoted = false;
        for (var i = 0; i < line.Length; i++)
        {
            if (line[i] == '"')
            {
                if (quoted && i + 1 < line.Length && line[i + 1] == '"') { field.Append('"'); i++; }
                else quoted = !quoted;
            }
            else if (line[i] == ',' && !quoted) { result.Add(field.ToString()); field.Clear(); }
            else field.Append(line[i]);
        }
        if (quoted) throw new InputException("CSV contains an unterminated quoted field.");
        result.Add(field.ToString()); return result;
    }
}
