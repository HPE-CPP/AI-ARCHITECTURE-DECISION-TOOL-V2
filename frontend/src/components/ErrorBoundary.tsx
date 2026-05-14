"use client";
import React from "react";

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error?.message || "Unknown error" };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[ErrorBoundary] Caught error:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="w-full min-h-screen flex items-center justify-center px-6">
          <div className="flex flex-col items-center text-center max-w-sm">
            <div className="w-16 h-16 rounded-2xl bg-[color:var(--surface)] border border-[color:var(--border)] flex items-center justify-center mb-6 text-2xl">
              ⚠️
            </div>
            <h1 className="text-2xl font-black tracking-tight text-[color:var(--text-primary)] mb-2">
              Something went wrong
            </h1>
            <p className="text-sm text-[color:var(--text-secondary)] font-medium mb-8 leading-relaxed">
              An unexpected error occurred. Reloading the page usually fixes it.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-3 rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] font-bold text-sm hover:opacity-80 transition-opacity active:scale-95"
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
