using System;
using System.Threading;
using System.Threading.Tasks;

namespace MermaidPng.App.Services
{
    public class DebounceDispatcher : IDisposable
    {
        private CancellationTokenSource? _cts;
        private readonly object _lock = new object();

        public void Debounce(int intervalMs, Action action)
        {
            lock (_lock)
            {
                _cts?.Cancel();
                _cts?.Dispose();
                _cts = new CancellationTokenSource();

                var token = _cts.Token;

                Task.Delay(intervalMs, token).ContinueWith(t =>
                {
                    if (!t.IsCanceled)
                    {
                        action();
                    }
                }, token);
            }
        }

        public void Dispose()
        {
            lock (_lock)
            {
                _cts?.Cancel();
                _cts?.Dispose();
                _cts = null;
            }
        }
    }
}
