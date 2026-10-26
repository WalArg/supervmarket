import React, { Component, ErrorInfo, ReactNode } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'

interface Props {
  children: ReactNode
  fallbackTitle?: string
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-6 my-4 mx-auto max-w-md bg-white rounded-2xl border border-slate-200/80 shadow-md text-center space-y-3">
          <div className="w-12 h-12 mx-auto rounded-full bg-amber-50 text-amber-600 flex items-center justify-center">
            <AlertTriangle size={24} />
          </div>
          <h2 className="text-[17px] font-extrabold text-slate-900">
            {this.props.fallbackTitle || 'Hubo un inconveniente al mostrar esta pantalla'}
          </h2>
          <p className="text-[13px] text-slate-500 leading-relaxed">
            Podés reintentar ahora o recargar la página para volver a sincronizar.
          </p>
          <div className="pt-2 flex items-center justify-center gap-2">
            <button
              type="button"
              onClick={this.handleReset}
              className="px-4 py-2 rounded-xl bg-blue-600 text-white font-bold text-[13px] flex items-center gap-1.5 shadow-sm active:scale-95 transition-all"
            >
              <RotateCcw size={15} /> Reintentar
            </button>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 font-bold text-[13px] hover:bg-slate-200 active:scale-95 transition-all"
            >
              Recargar app
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
