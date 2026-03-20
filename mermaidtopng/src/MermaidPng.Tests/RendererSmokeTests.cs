using System;
using System.Threading;
using System.Threading.Tasks;
using MermaidPng.App.Services;
using MermaidPng.App.ViewModels;
using Xunit;

namespace MermaidPng.Tests
{
    public class RendererSmokeTests
    {
        [Fact]
        public void RenderOptions_DefaultValues_AreCorrect()
        {
            // Arrange & Act
            var options = new RenderOptions();

            // Assert
            Assert.Equal("default", options.Theme);
            Assert.Equal(2.0, options.Scale);
            Assert.Null(options.BackgroundColor);
            Assert.Equal(20000, options.MaxWidth);
            Assert.Equal(20000, options.MaxHeight);
        }

        [Fact]
        public void RenderResult_SuccessfulResult_HasCorrectState()
        {
            // Arrange & Act
            var result = new RenderResult
            {
                Success = true,
                ErrorMessage = null
            };

            // Assert
            Assert.True(result.Success);
            Assert.Null(result.ErrorMessage);
        }

        [Fact]
        public void RenderResult_ErrorResult_HasCorrectState()
        {
            // Arrange & Act
            var result = new RenderResult
            {
                Success = false,
                ErrorMessage = "Test error"
            };

            // Assert
            Assert.False(result.Success);
            Assert.Equal("Test error", result.ErrorMessage);
        }

        [Fact]
        public void DebounceDispatcher_CanBeDisposed()
        {
            // Arrange
            var dispatcher = new DebounceDispatcher();

            // Act & Assert (should not throw)
            dispatcher.Dispose();
        }

        [Fact]
        public async Task DebounceDispatcher_DebounceAction_ExecutesAfterDelay()
        {
            // Arrange
            var dispatcher = new DebounceDispatcher();
            var executed = false;

            // Act
            dispatcher.Debounce(100, () => executed = true);
            await Task.Delay(50);
            Assert.False(executed);

            await Task.Delay(100);

            // Assert
            Assert.True(executed);
            dispatcher.Dispose();
        }

        [Fact]
        public async Task DebounceDispatcher_MultipleDebounces_OnlyLastExecutes()
        {
            // Arrange
            var dispatcher = new DebounceDispatcher();
            var counter = 0;

            // Act
            dispatcher.Debounce(100, () => counter = 1);
            await Task.Delay(30);
            dispatcher.Debounce(100, () => counter = 2);
            await Task.Delay(30);
            dispatcher.Debounce(100, () => counter = 3);
            await Task.Delay(150);

            // Assert
            Assert.Equal(3, counter);
            dispatcher.Dispose();
        }
    }
}
