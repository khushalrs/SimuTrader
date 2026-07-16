"use client";

import React, { Component, ReactNode } from "react";

interface Props {
    /** Rendered inside the error UI instead of the failed subtree. */
    fallback?: ReactNode;
    /** Called in development when an error is caught. */
    onError?: (error: Error, info: React.ErrorInfo) => void;
    children: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

/**
 * Catches render errors thrown by any child component tree (including failed
 * dynamic imports) and swaps them for a friendly fallback UI.
 *
 * Use at the top of each independently-loadable section so an isolated failure
 * in one tab never crashes the whole page.
 *
 * @example
 * <ErrorBoundary fallback={<p>Something went wrong loading this tab.</p>}>
 *   <MyHeavyDynamicComponent />
 * </ErrorBoundary>
 */
export class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, info: React.ErrorInfo): void {
        // Surface the stack in development; stay silent in production so
        // internals don't leak to browser consoles or log aggregators.
        if (process.env.NODE_ENV !== "production") {
            // eslint-disable-next-line no-console
            console.error("[ErrorBoundary] Caught error:", error, info.componentStack);
        }
        this.props.onError?.(error, info);
    }

    /** Allow a parent to programmatically reset the boundary. */
    reset(): void {
        this.setState({ hasError: false, error: null });
    }

    render(): ReactNode {
        if (this.state.hasError) {
            return (
                this.props.fallback ?? (
                    <DefaultFallback onRetry={() => this.reset()} />
                )
            );
        }
        return this.props.children;
    }
}

// ---------------------------------------------------------------------------
// Default fallback — shown when no custom fallback is provided.
// Offers a retry button that resets the boundary without a full page reload.
// ---------------------------------------------------------------------------
function DefaultFallback({ onRetry }: { onRetry: () => void }) {
    return (
        <div className="flex min-h-[200px] flex-col items-center justify-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-8 text-center">
            <p className="text-sm font-medium text-destructive">
                Something went wrong loading this section.
            </p>
            <p className="text-xs text-muted-foreground">
                This tab failed to load. Your other tabs are unaffected.
            </p>
            <button
                onClick={onRetry}
                className="mt-2 rounded-md bg-destructive/10 px-4 py-1.5 text-xs font-medium text-destructive transition-colors hover:bg-destructive/20"
            >
                Try again
            </button>
        </div>
    );
}
