using System;
using System.IO;
using System.Text.Json;
using Microsoft.Win32;

namespace MermaidPng.App.Services
{
    public class FileDialogService
    {
        private readonly UserSettings _settings;
        private readonly string _settingsPath;

        public FileDialogService()
        {
            var appDataPath = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "MermaidPng"
            );
            Directory.CreateDirectory(appDataPath);
            _settingsPath = Path.Combine(appDataPath, "settings.json");
            _settings = LoadSettings();
        }

        public string? OpenFile()
        {
            var dialog = new OpenFileDialog
            {
                Filter = "Mermaid Files (*.mmd;*.txt)|*.mmd;*.txt|All Files (*.*)|*.*",
                Title = "Open Mermaid Diagram",
                InitialDirectory = _settings.LastDirectory ?? Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments)
            };

            if (dialog.ShowDialog() == true)
            {
                _settings.LastDirectory = Path.GetDirectoryName(dialog.FileName);
                SaveSettings();
                return dialog.FileName;
            }

            return null;
        }

        public string? SaveFile()
        {
            var dialog = new SaveFileDialog
            {
                Filter = "PNG Image (*.png)|*.png",
                Title = "Export PNG",
                DefaultExt = ".png",
                FileName = _settings.LastFileName ?? "diagram.png",
                InitialDirectory = _settings.LastDirectory ?? Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments)
            };

            if (dialog.ShowDialog() == true)
            {
                _settings.LastDirectory = Path.GetDirectoryName(dialog.FileName);
                _settings.LastFileName = Path.GetFileName(dialog.FileName);
                SaveSettings();
                return dialog.FileName;
            }

            return null;
        }

        private UserSettings LoadSettings()
        {
            try
            {
                if (File.Exists(_settingsPath))
                {
                    var json = File.ReadAllText(_settingsPath);
                    return JsonSerializer.Deserialize<UserSettings>(json) ?? new UserSettings();
                }
            }
            catch
            {
                // Ignore errors loading settings
            }

            return new UserSettings();
        }

        private void SaveSettings()
        {
            try
            {
                var json = JsonSerializer.Serialize(_settings, new JsonSerializerOptions { WriteIndented = true });
                File.WriteAllText(_settingsPath, json);
            }
            catch
            {
                // Ignore errors saving settings
            }
        }

        private class UserSettings
        {
            public string? LastDirectory { get; set; }
            public string? LastFileName { get; set; }
        }
    }
}
