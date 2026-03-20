using System;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using Microsoft.Web.WebView2.Wpf;
using MermaidPng.App.Services;

namespace MermaidPng.App.ViewModels
{
    public class MainViewModel : INotifyPropertyChanged, IDisposable
    {
        private readonly MermaidRenderer _renderer;
        private readonly FileDialogService _fileDialog;
        private readonly DebounceDispatcher _debouncer;
        private CancellationTokenSource? _renderCts;

        private string _mermaidCode = "graph TD\n    A[Start] --> B{Is it working?}\n    B -->|Yes| C[Great!]\n    B -->|No| D[Debug]\n    D --> A";
        private string _statusMessage = "Ready";
        private Brush _statusForeground = Brushes.Black;
        private bool _isRendering = false;
        private bool _hasError = false;
        private string _lastError = string.Empty;
        private string _selectedScale = "2x";
        private string _selectedTheme = "default";
        private string _selectedBackground = "Transparent";
        private string _customBackgroundColor = "#FFFFFF";
        private bool _isCustomColorVisible = false;
        private string _maxWidth = "20000";
        private string _maxHeight = "20000";

        public MainViewModel()
        {
            _renderer = new MermaidRenderer();
            _fileDialog = new FileDialogService();
            _debouncer = new DebounceDispatcher();

            // Initialize commands
            OpenFileCommand = new RelayCommand(async () => await OpenFileAsync());
            ExportPngCommand = new RelayCommand(async () => await ExportPngAsync(), () => !_isRendering && !_hasError);
            CopyErrorCommand = new RelayCommand(CopyError, () => _hasError);
            CancelRenderCommand = new RelayCommand(CancelRender, () => _isRendering);

            // Initialize collections
            ScaleOptions = new ObservableCollection<string> { "1x", "2x", "3x", "4x", "5x" };
            ThemeOptions = new ObservableCollection<string> { "default", "dark", "forest", "neutral" };
            BackgroundOptions = new ObservableCollection<string> { "Transparent", "White", "Custom" };
        }

        public event PropertyChangedEventHandler? PropertyChanged;

        // Properties
        public string MermaidCode
        {
            get => _mermaidCode;
            set
            {
                if (_mermaidCode != value)
                {
                    _mermaidCode = value;
                    OnPropertyChanged();
                    DebouncedRenderPreview();
                }
            }
        }

        public string StatusMessage
        {
            get => _statusMessage;
            set { _statusMessage = value; OnPropertyChanged(); }
        }

        public Brush StatusForeground
        {
            get => _statusForeground;
            set { _statusForeground = value; OnPropertyChanged(); }
        }

        public bool IsRendering
        {
            get => _isRendering;
            set
            {
                _isRendering = value;
                OnPropertyChanged();
                CommandManager.InvalidateRequerySuggested();
            }
        }

        public bool HasError
        {
            get => _hasError;
            set
            {
                _hasError = value;
                OnPropertyChanged();
                CommandManager.InvalidateRequerySuggested();
            }
        }

        public string SelectedScale
        {
            get => _selectedScale;
            set
            {
                if (_selectedScale != value)
                {
                    _selectedScale = value;
                    OnPropertyChanged();
                    DebouncedRenderPreview();
                }
            }
        }

        public string SelectedTheme
        {
            get => _selectedTheme;
            set
            {
                if (_selectedTheme != value)
                {
                    _selectedTheme = value;
                    OnPropertyChanged();
                    DebouncedRenderPreview();
                }
            }
        }

        public string SelectedBackground
        {
            get => _selectedBackground;
            set
            {
                if (_selectedBackground != value)
                {
                    _selectedBackground = value;
                    OnPropertyChanged();
                    IsCustomColorVisible = value == "Custom";
                    DebouncedRenderPreview();
                }
            }
        }

        public string CustomBackgroundColor
        {
            get => _customBackgroundColor;
            set
            {
                if (_customBackgroundColor != value)
                {
                    _customBackgroundColor = value;
                    OnPropertyChanged();
                    if (IsCustomColorVisible)
                    {
                        DebouncedRenderPreview();
                    }
                }
            }
        }

        public bool IsCustomColorVisible
        {
            get => _isCustomColorVisible;
            set { _isCustomColorVisible = value; OnPropertyChanged(); }
        }

        public string MaxWidth
        {
            get => _maxWidth;
            set
            {
                if (_maxWidth != value)
                {
                    _maxWidth = value;
                    OnPropertyChanged();
                }
            }
        }

        public string MaxHeight
        {
            get => _maxHeight;
            set
            {
                if (_maxHeight != value)
                {
                    _maxHeight = value;
                    OnPropertyChanged();
                }
            }
        }

        public ObservableCollection<string> ScaleOptions { get; }
        public ObservableCollection<string> ThemeOptions { get; }
        public ObservableCollection<string> BackgroundOptions { get; }

        // Commands
        public ICommand OpenFileCommand { get; }
        public ICommand ExportPngCommand { get; }
        public ICommand CopyErrorCommand { get; }
        public ICommand CancelRenderCommand { get; }

        public async Task InitializeAsync(WebView2 webView)
        {
            try
            {
                StatusMessage = "Initializing renderer...";
                StatusForeground = Brushes.Blue;
                await _renderer.InitializeAsync(webView, CancellationToken.None);
                StatusMessage = "Ready";
                StatusForeground = Brushes.Black;
                await RenderPreviewAsync();
            }
            catch (Exception ex)
            {
                StatusMessage = $"Initialization error: {ex.Message}";
                StatusForeground = Brushes.Red;
                MessageBox.Show(
                    $"Failed to initialize renderer:\n\n{ex.Message}\n\nStack Trace:\n{ex.StackTrace}\n\n" +
                    "WebView2 Runtime may not be installed. Download from:\n" +
                    "https://developer.microsoft.com/microsoft-edge/webview2/",
                    "Initialization Error",
                    MessageBoxButton.OK,
                    MessageBoxImage.Error);
            }
        }

        private void DebouncedRenderPreview()
        {
            _debouncer.Debounce(500, async () =>
            {
                await Application.Current.Dispatcher.InvokeAsync(async () =>
                {
                    await RenderPreviewAsync();
                });
            });
        }

        private async Task RenderPreviewAsync()
        {
            if (string.IsNullOrWhiteSpace(MermaidCode))
            {
                StatusMessage = "Empty diagram";
                return;
            }

            _renderCts?.Cancel();
            _renderCts = new CancellationTokenSource();

            IsRendering = true;
            var startTime = DateTime.Now;
            StatusMessage = "Rendering preview...";
            StatusForeground = Brushes.Blue;

            try
            {
                var options = GetRenderOptions();
                var result = await _renderer.RenderPreviewAsync(MermaidCode, options, _renderCts.Token);

                if (result.Success)
                {
                    var elapsed = DateTime.Now - startTime;
                    StatusMessage = $"Rendered in {elapsed.TotalMilliseconds:F0}ms";
                    StatusForeground = Brushes.Green;
                    HasError = false;
                    _lastError = string.Empty;
                }
                else
                {
                    StatusMessage = $"Error: {result.ErrorMessage}";
                    StatusForeground = Brushes.Red;
                    HasError = true;
                    _lastError = result.ErrorMessage ?? "Unknown error";
                }
            }
            catch (OperationCanceledException)
            {
                StatusMessage = "Render cancelled";
                StatusForeground = Brushes.Orange;
            }
            catch (Exception ex)
            {
                StatusMessage = $"Error: {ex.Message}";
                StatusForeground = Brushes.Red;
                HasError = true;
                _lastError = ex.Message;
            }
            finally
            {
                IsRendering = false;
            }
        }

        private async Task OpenFileAsync()
        {
            try
            {
                var filePath = _fileDialog.OpenFile();
                if (!string.IsNullOrEmpty(filePath))
                {
                    MermaidCode = await System.IO.File.ReadAllTextAsync(filePath);
                    StatusMessage = $"Loaded: {System.IO.Path.GetFileName(filePath)}";
                    StatusForeground = Brushes.Black;
                }
            }
            catch (Exception ex)
            {
                StatusMessage = $"Error opening file: {ex.Message}";
                StatusForeground = Brushes.Red;
            }
        }

        private async Task ExportPngAsync()
        {
            if (string.IsNullOrWhiteSpace(MermaidCode))
            {
                MessageBox.Show("No diagram to export.", "Export", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            try
            {
                var filePath = _fileDialog.SaveFile();
                if (string.IsNullOrEmpty(filePath))
                    return;

                _renderCts?.Cancel();
                _renderCts = new CancellationTokenSource();

                IsRendering = true;
                StatusMessage = "Exporting PNG...";
                StatusForeground = Brushes.Blue;

                var options = GetRenderOptions();
                var startTime = DateTime.Now;
                var pngBytes = await _renderer.RenderPngAsync(MermaidCode, options, TimeSpan.FromSeconds(30), _renderCts.Token);

                await System.IO.File.WriteAllBytesAsync(filePath, pngBytes, _renderCts.Token);

                var elapsed = DateTime.Now - startTime;
                StatusMessage = $"Exported to {System.IO.Path.GetFileName(filePath)} in {elapsed.TotalMilliseconds:F0}ms";
                StatusForeground = Brushes.Green;

                MessageBox.Show($"PNG exported successfully to:\n{filePath}", "Export Complete", 
                    MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (OperationCanceledException)
            {
                StatusMessage = "Export cancelled";
                StatusForeground = Brushes.Orange;
            }
            catch (Exception ex)
            {
                StatusMessage = $"Export error: {ex.Message}";
                StatusForeground = Brushes.Red;
                MessageBox.Show($"Failed to export PNG:\n{ex.Message}", "Export Error", 
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
            finally
            {
                IsRendering = false;
            }
        }

        private void CopyError()
        {
            if (!string.IsNullOrEmpty(_lastError))
            {
                Clipboard.SetText(_lastError);
                StatusMessage = "Error copied to clipboard";
                StatusForeground = Brushes.Black;
            }
        }

        private void CancelRender()
        {
            _renderCts?.Cancel();
        }

        private RenderOptions GetRenderOptions()
        {
            int.TryParse(MaxWidth, out var maxWidth);
            int.TryParse(MaxHeight, out var maxHeight);

            var scale = double.Parse(SelectedScale.TrimEnd('x'));

            string? backgroundColor = SelectedBackground switch
            {
                "White" => "#FFFFFF",
                "Custom" => CustomBackgroundColor,
                _ => null // Transparent
            };

            return new RenderOptions
            {
                Theme = SelectedTheme,
                Scale = scale,
                BackgroundColor = backgroundColor,
                MaxWidth = maxWidth > 0 ? maxWidth : 20000,
                MaxHeight = maxHeight > 0 ? maxHeight : 20000
            };
        }

        public void Dispose()
        {
            _renderCts?.Cancel();
            _renderCts?.Dispose();
            _debouncer.Dispose();
        }

        protected void OnPropertyChanged([CallerMemberName] string? propertyName = null)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
        }
    }

    // Simple RelayCommand implementation
    public class RelayCommand : ICommand
    {
        private readonly Func<Task>? _executeAsync;
        private readonly Func<bool>? _canExecute;
        private readonly Action? _execute;

        public RelayCommand(Action execute, Func<bool>? canExecute = null)
        {
            _execute = execute ?? throw new ArgumentNullException(nameof(execute));
            _canExecute = canExecute;
        }

        public RelayCommand(Func<Task> executeAsync, Func<bool>? canExecute = null)
        {
            _executeAsync = executeAsync ?? throw new ArgumentNullException(nameof(executeAsync));
            _canExecute = canExecute;
        }

        public event EventHandler? CanExecuteChanged
        {
            add { CommandManager.RequerySuggested += value; }
            remove { CommandManager.RequerySuggested -= value; }
        }

        public bool CanExecute(object? parameter) => _canExecute?.Invoke() ?? true;

        public async void Execute(object? parameter)
        {
            if (_executeAsync != null)
                await _executeAsync();
            else
                _execute?.Invoke();
        }
    }
}
