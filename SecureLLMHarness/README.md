# SecureLLMHarness

`SecureLLMHarness` is a cross-platform .NET 8 command-line checker for OpenAI-compatible chat-completion endpoints. It sends one deterministic JSON-only request, validates the returned assistant JSON, and reports a safe result for each endpoint.

## Prerequisites

- .NET SDK 8 or later
- Network access to the endpoint(s) under test

Build and run from this directory:

```sh
dotnet restore
dotnet build
dotnet run -- --help
```

## Single test

Set a key in your shell instead of putting it on the command line. The default environment-variable name is `OPENAI_API_KEY`.

```sh
# PowerShell
$env:OPENAI_API_KEY = "your-key"
dotnet run -- --provider OpenAI --url https://api.openai.com/v1 --model gpt-4o-mini

# Bash/zsh
export OPENAI_API_KEY='your-key'
dotnet run -- --provider Groq --url https://api.groq.com/openai/v1 --model llama-3.1-70b-versatile
```

Use a differently named variable with `--api-key-env`:

```sh
dotnet run -- --provider OpenRouter --url https://openrouter.ai/api/v1 --model openai/gpt-4o-mini --api-key-env OPENROUTER_API_KEY
```

For a local endpoint without authentication:

```sh
dotnet run -- --provider Local --url http://localhost:11434/v1 --model llama3.1
```

Azure OpenAI is detected when the provider name includes `Azure`. The model value is its deployment name. The harness uses Azure's `api-key` header and constructs the deployment completion URL; an existing `api-version` query parameter in `--url` is preserved.

```sh
$env:AZURE_OPENAI_KEY = "your-key"
dotnet run -- --provider "Azure OpenAI" --url https://YOUR_RESOURCE.openai.azure.com --model YOUR_DEPLOYMENT_NAME --api-key-env AZURE_OPENAI_KEY
```

## Batch tests

Create a CSV with the required headers exactly as shown in [sample-tests.csv](sample-tests.csv). Relative paths are resolved from the current directory and absolute paths are supported.

```sh
dotnet run -- --csv sample-tests.csv --timeout 45 --verbose --results results.json
```

Each row is independent. `ApiKey` can be empty for local endpoints. Do not commit CSV files containing real keys. The sample contains placeholders only. For batch runs, use a local, access-restricted CSV supplied by your deployment or secret system; the harness never emits the key in console diagnostics or its JSON results.

### Azure deployment names and API versions

For Azure OpenAI, `Model` must be the deployment name configured in the Azure resource. It is not necessarily the public model name (`gpt-4o`, `gpt-4`, and so on). The harness uses API version `2024-10-21` by default; if your endpoint URL already includes an `api-version` query parameter, that value is preserved.

Embedding deployments such as `text-embedding-3-large` are not chat-completion models and should be tested with an embeddings-specific request, not this harness's chat request.

### Verified real-endpoint smoke test

A single-row Azure CSV was tested successfully with this harness: HTTP 200, valid expected JSON, and approximately 1.4 seconds latency. The test output contained no API key, URL, or raw provider response. This confirms the end-to-end C# HTTP client, Azure authentication header, chat-completion payload, and JSON validation path.

## Options and exit codes

| Option | Purpose |
| --- | --- |
| `--csv <path>` | Batch input with `Provider,Url,ApiKey,Model` headers. |
| `--provider`, `--url`, `--model` | Required together for a one-off test. |
| `--api-key <key>` | Direct key input; prefer `--api-key-env`. |
| `--api-key-env <name>` | Read a key from an environment variable; defaults to `OPENAI_API_KEY`. |
| `--timeout <seconds>` | Request timeout from 1 to 300 seconds; default 45. |
| `--verbose`, `--quiet` | Add safe HTTP status details or print only the summary. |
| `--results <path>` | Write results JSON without URLs or secrets. |

Exit code `0` means every test passed. `1` means one or more requests failed. `2` means CLI or input validation failed.

## Security notes

- API keys are never logged, printed, included in result files, or incorporated into error messages.
- The tool deliberately does not print raw HTTP response bodies or exception details, since providers can echo sensitive request metadata.
- Avoid `--api-key` in shared shell history/process listings; prefer an environment variable or an external secret manager that injects environment variables at runtime.
- Treat CSV files containing real keys as local secret material: restrict file permissions, do not commit them, and remove or rotate keys if they are accidentally shared.
