interface LoadingStateProps {
  message?: string;
}

export function LoadingState({ message = "Working…" }: LoadingStateProps) {
  return (
    <div className="app-card flex items-center gap-3 p-4" role="status" aria-live="polite">
      <span aria-hidden="true" className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--border)] border-t-[var(--brand)]" />
      <span>{message}</span>
    </div>
  );
}
