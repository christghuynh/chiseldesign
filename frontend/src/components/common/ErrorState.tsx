interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="app-card border-l-4 border-l-[var(--danger)] p-4" role="alert">
      <p className="m-0 font-semibold">Something needs attention</p>
      <p className="mt-1 text-[var(--text-muted)]">{message}</p>
      {onRetry && <button type="button" className="app-button app-button--secondary mt-2" onClick={onRetry}>Try again</button>}
    </div>
  );
}
