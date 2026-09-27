import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  children?: ReactNode;
  description?: ReactNode;
  eyebrow?: string;
  variant?: "default" | "design" | "confirm" | "plan" | "build";
}

export function EmptyState({ title, children, description, eyebrow, variant = "default" }: EmptyStateProps) {
  const hasDedicatedDescription = description !== undefined;
  return (
    <section className={`app-card empty-state empty-state--${variant}`}>
      <div className="empty-state__art" aria-hidden="true">
        <svg viewBox="0 0 148 124" role="presentation">
          <path d="M18 97H130M18 97l8-5M18 97l8 5M130 97l-8-5M130 97l-8 5" className="empty-state__line" />
          <path d="M27 81h25L94 39h27" className="empty-state__main" />
          <path d="M27 90h30l42-42h22" className="empty-state__detail" />
          <circle cx="27" cy="81" r="6" className="empty-state__node" />
          <circle cx="121" cy="39" r="6" className="empty-state__node" />
          <path d="M38 75V53h18M62 58V36h18M86 36V21h18" className="empty-state__detail" />
          <path d="M22 21h14M29 14v14M112 76h16M120 68v16" className="empty-state__spark" />
        </svg>
      </div>
      <div className="empty-state__content">
        {eyebrow && <p className="empty-state__eyebrow">{eyebrow}</p>}
        <h3>{title}</h3>
        {hasDedicatedDescription && <div className="empty-state__description">{description}</div>}
        {!hasDedicatedDescription && children && <div className="empty-state__description">{children}</div>}
        {hasDedicatedDescription && children && <div className="empty-state__actions">{children}</div>}
      </div>
    </section>
  );
}
