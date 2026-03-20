using System;
using System.Windows;
using MermaidPng.App.ViewModels;

namespace MermaidPng.App
{
    public partial class MainWindow : Window
    {
        private readonly MainViewModel _viewModel;

        public MainWindow()
        {
            try
            {
                InitializeComponent();
                _viewModel = new MainViewModel();
                DataContext = _viewModel;

                Loaded += async (s, e) =>
                {
                    try
                    {
                        await _viewModel.InitializeAsync(PreviewWebView);
                    }
                    catch (Exception ex)
                    {
                        MessageBox.Show($"Failed to initialize WebView2:\n\n{ex.Message}\n\nMake sure WebView2 Runtime is installed.", 
                            "Initialization Error", MessageBoxButton.OK, MessageBoxImage.Error);
                    }
                };

                Closing += (s, e) =>
                {
                    _viewModel.Dispose();
                };
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Failed to initialize application:\n\n{ex.Message}", 
                    "Startup Error", MessageBoxButton.OK, MessageBoxImage.Error);
                throw;
            }
        }
    }
}
