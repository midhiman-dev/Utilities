using System.CommandLine;
using SecureLLMHarness;

var csvOption = new Option<FileInfo?>("--csv") { Description = "CSV input file (headers: Provider,Url,ApiKey,Model)." };
var providerOption = new Option<string?>("--provider") { Description = "Provider name (for example: OpenAI, Azure OpenAI, Groq)." };
var urlOption = new Option<string?>("--url") { Description = "Provider base URL or Azure resource endpoint." };
var apiKeyOption = new Option<string?>("--api-key") { Description = "API key. Prefer an environment variable." };
var apiKeyEnvOption = new Option<string?>("--api-key-env") { Description = "Environment variable containing the API key." };
var modelOption = new Option<string?>("--model") { Description = "Model name (Azure: deployment name)." };
var timeoutOption = new Option<int>("--timeout") { Description = "Request timeout in seconds (1-300).", DefaultValueFactory = _ => 45 };
var verboseOption = new Option<bool>("--verbose") { Description = "Show safe diagnostic details." };
var quietOption = new Option<bool>("--quiet") { Description = "Only print the summary." };
var resultsOption = new Option<FileInfo?>("--results") { Description = "Optional JSON results file. Secrets are never written." };

var root = new RootCommand("SecureLLMHarness - secure OpenAI-compatible chat completion checks.");
root.Options.Add(csvOption);
root.Options.Add(providerOption);
root.Options.Add(urlOption);
root.Options.Add(apiKeyOption);
root.Options.Add(apiKeyEnvOption);
root.Options.Add(modelOption);
root.Options.Add(timeoutOption);
root.Options.Add(verboseOption);
root.Options.Add(quietOption);
root.Options.Add(resultsOption);

root.SetAction(async parseResult =>
{
    var timeout = parseResult.GetValue(timeoutOption);
    if (timeout is < 1 or > 300)
    {
        Console.Error.WriteLine("--timeout must be between 1 and 300 seconds.");
        return 2;
    }

    var cli = new CliOptions(
        parseResult.GetValue(csvOption), parseResult.GetValue(providerOption), parseResult.GetValue(urlOption),
        parseResult.GetValue(apiKeyOption), parseResult.GetValue(apiKeyEnvOption), parseResult.GetValue(modelOption),
        timeout, parseResult.GetValue(verboseOption), parseResult.GetValue(quietOption), parseResult.GetValue(resultsOption));

    try
    {
        var cases = InputLoader.Load(cli);
        using var cancelSource = new CancellationTokenSource();
        Console.CancelKeyPress += (_, eventArgs) => { eventArgs.Cancel = true; cancelSource.Cancel(); };

        var runner = new ChatCompletionRunner();
        var results = new List<TestResult>();
        foreach (var testCase in cases)
        {
            results.Add(await runner.RunAsync(testCase, cli.TimeoutSeconds, cancelSource.Token));
        }

        Reporter.WriteConsole(results, cli.Verbose, cli.Quiet);
        if (cli.ResultsFile is not null)
        {
            await Reporter.WriteJsonAsync(cli.ResultsFile, results, cancelSource.Token);
        }

        return results.All(result => result.Success) ? 0 : 1;
    }
    catch (OperationCanceledException)
    {
        Console.Error.WriteLine("Cancelled.");
        return 1;
    }
    catch (InputException exception)
    {
        Console.Error.WriteLine($"Input error: {exception.Message}");
        return 2;
    }
    catch (Exception)
    {
        // Intentionally do not print exception details: SDK/network exceptions can contain request headers.
        Console.Error.WriteLine("Unexpected failure. Re-run with --verbose and verify the safe input values.");
        return 1;
    }
});

return await root.Parse(args).InvokeAsync();
