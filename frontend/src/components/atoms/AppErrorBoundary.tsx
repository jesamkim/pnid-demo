/**
 * Top-level React error boundary.
 *
 * Without this, a thrown error inside the tree (e.g. a stale-cursor
 * deref during a drawing switch) tears the entire #root down and the
 * user is left with a black screen. The boundary catches the throw,
 * keeps the chrome alive, and offers an explicit reload button so the
 * demo never silently dies on stage.
 *
 * The captured error is stashed on `window.__lastAppError` so screen
 * recordings / Playwright runs can pick it up after the fact.
 */
import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

declare global {
  interface Window {
    __lastAppError?: { message: string; stack?: string; at: string };
  }
}

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    if (typeof window !== "undefined") {
      window.__lastAppError = {
        message: error.message,
        stack: info.componentStack ?? error.stack,
        at: new Date().toISOString(),
      };
    }
    // eslint-disable-next-line no-console
    console.error("[AppErrorBoundary] caught:", error, info);
  }

  private handleReset = () => {
    this.setState({ error: null });
  };

  private handleReload = () => {
    if (typeof window !== "undefined") window.location.reload();
  };

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div
        role="alert"
        className="flex h-screen w-screen flex-col items-center justify-center gap-4 bg-canvas px-6 text-center text-fg-primary"
      >
        <div className="text-sm font-semibold uppercase tracking-[0.18em] text-accent">
          Demo paused
        </div>
        <h1 className="text-2xl font-semibold">
          Something tripped the renderer.
        </h1>
        <p className="max-w-xl text-sm text-fg-secondary">
          The viewer hit an unexpected state. The error has been logged to the
          console (and to <code>window.__lastAppError</code>). Recover by
          continuing in place or reloading.
        </p>
        <pre className="max-w-xl whitespace-pre-wrap text-left text-xs text-danger/90">
          {this.state.error.message}
        </pre>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={this.handleReset}
            className="rounded-md border border-accent/40 bg-[var(--accent-soft)] px-4 py-2 text-sm font-medium text-accent shadow-[var(--shadow-glow)] transition hover:bg-[var(--accent-soft)]/80"
          >
            Continue
          </button>
          <button
            type="button"
            onClick={this.handleReload}
            className="rounded-md border border-border-default px-4 py-2 text-sm font-medium text-fg-primary transition hover:bg-surface"
          >
            Reload page
          </button>
        </div>
      </div>
    );
  }
}
