import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  children?: ReactNode;
}

export function EmptyState({ title, children }: EmptyStateProps) {
  return (
    <div className="app-card p-5 text-center">
      <p className="m-0 font-semibold">{title}</p>
      {children && <div className="mt-2 text-[var(--text-muted)]">{children}</div>}
    </div>
  );
}
