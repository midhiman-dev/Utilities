using System;
using System.Windows;

namespace MermaidPng.App
{
    public partial class App : Application
    {
        public App()
        {
            // Handle unhandled exceptions
            this.DispatcherUnhandledException += (s, e) =>
            {
                MessageBox.Show($"An unexpected error occurred:\n\n{e.Exception.Message}\n\nStack Trace:\n{e.Exception.StackTrace}",
                    "Application Error", MessageBoxButton.OK, MessageBoxImage.Error);
                e.Handled = true;
            };

            AppDomain.CurrentDomain.UnhandledException += (s, e) =>
            {
                var ex = e.ExceptionObject as Exception;
                MessageBox.Show($"Fatal error:\n\n{ex?.Message ?? "Unknown error"}\n\n{ex?.StackTrace}",
                    "Fatal Error", MessageBoxButton.OK, MessageBoxImage.Error);
            };
        }

        protected override void OnStartup(StartupEventArgs e)
        {
            try
            {
                base.OnStartup(e);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Startup error:\n\n{ex.Message}\n\n{ex.StackTrace}",
                    "Startup Error", MessageBoxButton.OK, MessageBoxImage.Error);
                Shutdown(1);
            }
        }
    }
}
