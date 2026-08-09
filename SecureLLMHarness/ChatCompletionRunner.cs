using System.Diagnostics;
using System.Net;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;

namespace SecureLLMHarness;

public sealed class ChatCompletionRunner
{
    private const string SystemPrompt = "You are a helpful assistant. Always reply with valid JSON only.";
    private const string UserPrompt = "Return a JSON object with exactly two fields: \"status\": \"ok\" and \"message\": \"hello\".";

    public async Task<TestResult> RunAsync(TestCase testCase, int timeoutSeconds, CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        try
        {
            var isAzure = testCase.Provider.Contains("azure", StringComparison.OrdinalIgnoreCase);
            var requestUri = EndpointBuilder.Create(testCase.BaseUrl, testCase.Model, isAzure);
            using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(timeoutSeconds) };
            using var request = new HttpRequestMessage(HttpMethod.Post, requestUri);
            if (!string.IsNullOrEmpty(testCase.ApiKey))
            {
                if (isAzure) request.Headers.Add("api-key", testCase.ApiKey);
                else request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", testCase.ApiKey);
            }
            var payload = new { model = testCase.Model, temperature = 0, response_format = new { type = "json_object" }, messages = new[]
            {
                new { role = "system", content = SystemPrompt }, new { role = "user", content = UserPrompt }
            }};
            request.Content = new StringContent(JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json");
            using var response = await client.SendAsync(request, HttpCompletionOption.ResponseContentRead, cancellationToken);
            var body = await response.Content.ReadAsStringAsync(cancellationToken);
            stopwatch.Stop();
            if (!response.IsSuccessStatusCode)
                return Failure(testCase, stopwatch, response.StatusCode, DescribeHttpFailure(response.StatusCode));
            return ValidateResponse(testCase, stopwatch, body);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            stopwatch.Stop(); return Failure(testCase, stopwatch, null, "Request timed out.");
        }
        catch (HttpRequestException exception)
        {
            stopwatch.Stop();
            return Failure(testCase, stopwatch, exception.StatusCode, exception.StatusCode is null ? "Connection failed. Check URL, DNS, and network access." : DescribeHttpFailure(exception.StatusCode.Value));
        }
        catch (JsonException)
        {
            stopwatch.Stop(); return Failure(testCase, stopwatch, null, "Provider returned malformed JSON.");
        }
    }

    private static TestResult ValidateResponse(TestCase testCase, Stopwatch stopwatch, string responseBody)
    {
        try
        {
            using var envelope = JsonDocument.Parse(responseBody);
            var content = envelope.RootElement.GetProperty("choices")[0].GetProperty("message").GetProperty("content").GetString();
            if (string.IsNullOrWhiteSpace(content)) return Failure(testCase, stopwatch, null, "Response contained no assistant content.");
            using var contentJson = JsonDocument.Parse(content);
            var root = contentJson.RootElement;
            var valid = root.ValueKind == JsonValueKind.Object
                && root.TryGetProperty("status", out var status) && status.ValueKind == JsonValueKind.String && status.GetString() == "ok"
                && root.TryGetProperty("message", out var message) && message.ValueKind == JsonValueKind.String && message.GetString() == "hello";
            return valid
                ? new TestResult(testCase.Provider, testCase.Model, true, stopwatch.ElapsedMilliseconds, "Valid expected JSON received.", 200)
                : Failure(testCase, stopwatch, null, "Assistant JSON did not match the expected status/message values.");
        }
        catch (KeyNotFoundException) { return Failure(testCase, stopwatch, null, "Response does not use the expected chat-completions structure."); }
        catch (IndexOutOfRangeException) { return Failure(testCase, stopwatch, null, "Response has no completion choices."); }
        catch (JsonException) { return Failure(testCase, stopwatch, null, "Assistant response was not valid JSON."); }
    }

    private static TestResult Failure(TestCase testCase, Stopwatch stopwatch, HttpStatusCode? status, string message) =>
        new(testCase.Provider, testCase.Model, false, stopwatch.ElapsedMilliseconds, message, status is null ? null : (int)status);

    private static string DescribeHttpFailure(HttpStatusCode status) => (int)status switch
    {
        401 => "Authentication failed (HTTP 401). Verify the API key.",
        403 => "Access denied (HTTP 403). Verify key permissions and model access.",
        404 => "Endpoint or model deployment was not found (HTTP 404).",
        429 => "Rate limited (HTTP 429). Try again later.",
        >= 500 and <= 599 => $"Provider server error (HTTP {(int)status}). Try again later.",
        _ => $"Request failed (HTTP {(int)status})."
    };
}

public static class EndpointBuilder
{
    public static Uri Create(Uri baseUrl, string model, bool isAzure)
    {
        if (isAzure)
        {
            var builder = new UriBuilder(baseUrl);
            var root = builder.Path.TrimEnd('/');
            builder.Path = $"{root}/openai/deployments/{Uri.EscapeDataString(model)}/chat/completions";
            builder.Query = string.IsNullOrEmpty(builder.Query.TrimStart('?')) ? "api-version=2024-10-21" : builder.Query.TrimStart('?');
            return builder.Uri;
        }
        return new Uri(baseUrl.ToString().TrimEnd('/') + "/chat/completions");
    }
}
