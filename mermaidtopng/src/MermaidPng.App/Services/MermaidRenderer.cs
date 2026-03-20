using System;
using System.IO;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.Wpf;
using MermaidPng.App.ViewModels;

namespace MermaidPng.App.Services
{
    public class MermaidRenderer
    {
        private WebView2? _webView;
        private bool _initialized = false;

        public async Task InitializeAsync(WebView2 webView, CancellationToken ct)
        {
            _webView = webView ?? throw new ArgumentNullException(nameof(webView));

            var userDataFolder = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "MermaidPng",
                "WebView2"
            );
            Directory.CreateDirectory(userDataFolder);

            var env = await CoreWebView2Environment.CreateAsync(userDataFolder: userDataFolder);

            await _webView.EnsureCoreWebView2Async(env);

            // Enable DevTools in debug builds only
#if DEBUG
            _webView.CoreWebView2.Settings.AreDevToolsEnabled = true;
#else
            _webView.CoreWebView2.Settings.AreDevToolsEnabled = false;
#endif
            _webView.CoreWebView2.Settings.AreDefaultContextMenusEnabled = false;

            // Load host HTML with embedded Mermaid.js
            var hostHtml = LoadHostHtml();
            
            // Write to temp file instead of using NavigateToString (which has size limits)
            var tempPath = Path.Combine(userDataFolder, "host.html");
            await File.WriteAllTextAsync(tempPath, hostHtml, ct);
            
            // Navigate to file
            _webView.CoreWebView2.Navigate($"file:///{tempPath.Replace("\\", "/")}");

            // Wait for navigation to complete
            var tcs = new TaskCompletionSource<bool>();
            void NavigationCompleted(object? s, CoreWebView2NavigationCompletedEventArgs e)
            {
                _webView.CoreWebView2.NavigationCompleted -= NavigationCompleted;
                tcs.SetResult(e.IsSuccess);
            }

            _webView.CoreWebView2.NavigationCompleted += NavigationCompleted;
            
            using var timeoutCts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
            using var linkedCts = CancellationTokenSource.CreateLinkedTokenSource(ct, timeoutCts.Token);
            
            await using (linkedCts.Token.Register(() => tcs.TrySetCanceled()))
            {
                var success = await tcs.Task;
                if (!success)
                {
                    throw new InvalidOperationException("Failed to load host HTML in WebView2");
                }
            }

            _initialized = true;
        }

        public async Task<RenderResult> RenderPreviewAsync(string mermaidCode, RenderOptions options, CancellationToken ct)
        {
            EnsureInitialized();

            try
            {
                var optionsJson = JsonSerializer.Serialize(new
                {
                    theme = options.Theme,
                    scale = options.Scale,
                    backgroundColor = options.BackgroundColor,
                    maxWidth = options.MaxWidth,
                    maxHeight = options.MaxHeight
                });

                var tcs = new TaskCompletionSource<string>();

                void MessageReceived(object? sender, CoreWebView2WebMessageReceivedEventArgs e)
                {
                    try
                    {
                        var message = e.TryGetWebMessageAsString();
                        tcs.TrySetResult(message);
                    }
                    catch (Exception ex)
                    {
                        tcs.TrySetException(ex);
                    }
                }

                _webView!.CoreWebView2.WebMessageReceived += MessageReceived;

                try
                {
                    var script = $@"
                        (function() {{
                            window.renderPreview({JsonSerializer.Serialize(mermaidCode)}, {optionsJson})
                                .then(() => {{
                                    window.chrome.webview.postMessage(JSON.stringify({{ success: true }}));
                                }})
                                .catch(error => {{
                                    window.chrome.webview.postMessage(JSON.stringify({{ success: false, error: error.message }}));
                                }});
                        }})();
                    ";

                    await _webView.CoreWebView2.ExecuteScriptAsync(script);

                    using var registration = ct.Register(() => tcs.TrySetCanceled());
                    var jsonString = await tcs.Task;
                    var result = JsonSerializer.Deserialize<JsonElement>(jsonString);

                    if (result.TryGetProperty("success", out var success) && success.GetBoolean())
                    {
                        return new RenderResult { Success = true };
                    }
                    else if (result.TryGetProperty("error", out var error))
                    {
                        return new RenderResult
                        {
                            Success = false,
                            ErrorMessage = error.GetString() ?? "Unknown error"
                        };
                    }

                    return new RenderResult { Success = false, ErrorMessage = "Unknown error" };
                }
                finally
                {
                    _webView.CoreWebView2.WebMessageReceived -= MessageReceived;
                }
            }
            catch (Exception ex)
            {
                return new RenderResult
                {
                    Success = false,
                    ErrorMessage = ex.Message
                };
            }
        }

        public async Task<byte[]> RenderPngAsync(string mermaidCode, RenderOptions options, TimeSpan timeout, CancellationToken ct)
        {
            EnsureInitialized();

            using var timeoutCts = new CancellationTokenSource(timeout);
            using var linkedCts = CancellationTokenSource.CreateLinkedTokenSource(ct, timeoutCts.Token);

            try
            {
                var optionsJson = JsonSerializer.Serialize(new
                {
                    theme = options.Theme,
                    scale = options.Scale,
                    backgroundColor = options.BackgroundColor,
                    maxWidth = options.MaxWidth,
                    maxHeight = options.MaxHeight
                });

                // Use a TaskCompletionSource to wait for the result
                var tcs = new TaskCompletionSource<string>();
                
                void MessageReceived(object? sender, CoreWebView2WebMessageReceivedEventArgs e)
                {
                    try
                    {
                        var message = e.TryGetWebMessageAsString();
                        tcs.TrySetResult(message);
                    }
                    catch (Exception ex)
                    {
                        tcs.TrySetException(ex);
                    }
                }

                _webView!.CoreWebView2.WebMessageReceived += MessageReceived;

                try
                {
                    // Trigger the render and send result via postMessage
                    var script = $@"
                        (function() {{
                            window.renderToPngBase64({JsonSerializer.Serialize(mermaidCode)}, {optionsJson})
                                .then(dataUrl => {{
                                    window.chrome.webview.postMessage(JSON.stringify({{ success: true, data: dataUrl }}));
                                }})
                                .catch(error => {{
                                    window.chrome.webview.postMessage(JSON.stringify({{ success: false, error: error.message }}));
                                }});
                        }})();
                    ";

                    await _webView.CoreWebView2.ExecuteScriptAsync(script);

                    // Wait for the message with timeout
                    using var registration = linkedCts.Token.Register(() => tcs.TrySetCanceled());
                    var jsonString = await tcs.Task;

                    var result = JsonSerializer.Deserialize<JsonElement>(jsonString);

                    if (result.TryGetProperty("success", out var success) && success.GetBoolean())
                    {
                        if (result.TryGetProperty("data", out var dataUrl))
                        {
                            var base64Data = dataUrl.GetString();
                            if (base64Data != null && base64Data.StartsWith("data:image/png;base64,"))
                            {
                                var pureBase64 = base64Data.Substring("data:image/png;base64,".Length);
                                return Convert.FromBase64String(pureBase64);
                            }
                            else
                            {
                                throw new InvalidOperationException($"Invalid PNG data URL format");
                            }
                        }
                        else
                        {
                            throw new InvalidOperationException("PNG data not returned from JavaScript");
                        }
                    }
                    else if (result.TryGetProperty("error", out var error))
                    {
                        var errorMsg = error.GetString() ?? "Unknown JavaScript error";
                        throw new InvalidOperationException($"JavaScript render error: {errorMsg}");
                    }

                    throw new InvalidOperationException($"Unexpected JavaScript response");
                }
                finally
                {
                    _webView!.CoreWebView2.WebMessageReceived -= MessageReceived;
                }
            }
            catch (OperationCanceledException)
            {
                if (timeoutCts.Token.IsCancellationRequested)
                    throw new TimeoutException($"Render operation timed out after {timeout.TotalSeconds} seconds");
                throw;
            }
        }

        private void EnsureInitialized()
        {
            if (!_initialized || _webView == null)
                throw new InvalidOperationException("Renderer not initialized");
        }

        private string LoadHostHtml()
        {
            // Load host.html from embedded resources
            var assembly = Assembly.GetExecutingAssembly();
            var resourceName = "MermaidPng.App.Web.host.html";

            using var stream = assembly.GetManifestResourceStream(resourceName);
            if (stream == null)
            {
                // List all available resources for debugging
                var availableResources = string.Join("\n", assembly.GetManifestResourceNames());
                throw new FileNotFoundException(
                    $"Embedded resource not found: {resourceName}\n\n" +
                    $"Available resources:\n{availableResources}");
            }

            using var reader = new StreamReader(stream);
            var html = reader.ReadToEnd();

            // Load mermaid.min.js
            var mermaidResourceName = "MermaidPng.App.Web.mermaid.min.js";
            using var mermaidStream = assembly.GetManifestResourceStream(mermaidResourceName);
            if (mermaidStream == null)
            {
                var availableResources = string.Join("\n", assembly.GetManifestResourceNames());
                throw new FileNotFoundException(
                    $"Embedded resource not found: {mermaidResourceName}\n\n" +
                    $"Available resources:\n{availableResources}");
            }

            using var mermaidReader = new StreamReader(mermaidStream);
            var mermaidJs = mermaidReader.ReadToEnd();

            // Replace placeholder with actual Mermaid.js content
            html = html.Replace("{{MERMAID_JS}}", mermaidJs);

            return html;
        }
    }
}
