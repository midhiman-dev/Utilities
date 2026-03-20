namespace MermaidPng.App.ViewModels
{
    public class RenderOptions
    {
        public string Theme { get; set; } = "default";
        public double Scale { get; set; } = 2.0;
        public string? BackgroundColor { get; set; }
        public int MaxWidth { get; set; } = 20000;
        public int MaxHeight { get; set; } = 20000;
    }

    public class RenderResult
    {
        public bool Success { get; set; }
        public string? ErrorMessage { get; set; }
    }
}
