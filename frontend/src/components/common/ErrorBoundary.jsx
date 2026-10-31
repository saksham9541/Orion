import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('Captured by RailOpt ErrorBoundary:', error, errorInfo)
    this.setState({ errorInfo })
  }

  handleReload = () => {
    window.location.reload()
  }

  handleReset = () => {
    try {
      sessionStorage.clear()
      localStorage.removeItem('railopt_user')
      localStorage.removeItem('railopt_token')
      localStorage.removeItem('railopt_email')
    } catch {}
    window.location.href = '/login'
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-base p-6 text-ink font-sans">
          <div className="w-full max-w-lg rounded-2xl border border-rose-500/30 bg-surface p-7 shadow-2xl">
            <div className="flex items-center gap-3 border-b border-line pb-4">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-500/10 text-rose-500 font-bold text-lg">
                ⚠️
              </span>
              <div>
                <h1 className="text-base font-bold text-ink">ORION UI Recovered</h1>
                <p className="text-xs text-muted">An unexpected interface exception was safely intercepted.</p>
              </div>
            </div>

            <div className="my-4 rounded-lg border border-hair bg-base/80 p-3.5 font-mono text-[11.5px] text-rose-300 max-h-40 overflow-y-auto">
              <p className="font-semibold text-rose-200 mb-1">
                {this.state.error?.name || 'Error'}: {this.state.error?.message || 'Unknown runtime error'}
              </p>
              {this.state.error?.stack && (
                <pre className="text-[10px] text-faint whitespace-pre-wrap">
                  {this.state.error.stack.split('\n').slice(0, 5).join('\n')}
                </pre>
              )}
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={this.handleReset}
                className="rounded-lg border border-line bg-raised px-3.5 py-2 text-xs font-semibold text-muted hover:text-ink hover:bg-base transition-colors"
              >
                Reset Session & Sign In
              </button>
              <button
                type="button"
                onClick={this.handleReload}
                className="rounded-lg bg-accent text-white px-4 py-2 text-xs font-semibold hover:bg-accent/90 transition-colors shadow-sm"
              >
                Reload Page
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
