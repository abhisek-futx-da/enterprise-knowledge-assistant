import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { ANSWER_META, queryTerms } from "../lib/format";
import type { AnswerType } from "../lib/types";

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

export function Card({ className, children, tone = "surface" }: {
  className?: string; children: ReactNode; tone?: "surface" | "accent" | "contrast" | "sunken";
}) {
  const tones = {
    surface: "bg-surface border border-line shadow-card",
    accent: "bg-accent text-on-accent",
    contrast: "bg-contrast text-on-contrast",
    sunken: "bg-sunken",
  };
  return <section className={cx("rounded-card p-5 sm:p-6", tones[tone], className)}>{children}</section>;
}

type Variant = "primary" | "accent" | "ghost" | "outline" | "danger";
export function Button({ variant = "primary", loading, className, children, ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  const v: Record<Variant, string> = {
    primary: "bg-ink text-bg hover:opacity-90",
    accent: "bg-accent text-on-accent hover:bg-accent-strong",
    ghost: "text-ink hover:bg-sunken",
    outline: "border border-line bg-surface text-ink hover:bg-surface-2",
    danger: "bg-bad text-white hover:opacity-90",
  };
  return (
    <button
      {...props}
      disabled={props.disabled || loading}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-full px-4 h-10 text-sm font-medium transition",
        "disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]",
        v[variant], className,
      )}
    >
      {loading && <Loader2 className="size-4 animate-spin" />}
      {children}
    </button>
  );
}

const TONE: Record<string, string> = {
  good: "bg-good/12 text-good",
  warn: "bg-warn/14 text-warn",
  bad: "bg-bad/12 text-bad",
  info: "bg-info/12 text-info",
  muted: "bg-sunken text-muted",
};

export function Pill({ tone = "muted", children, className, title }: {
  tone?: string; children: ReactNode; className?: string; title?: string;
}) {
  return (
    <span title={title} className={cx("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium", TONE[tone], className)}>
      {children}
    </span>
  );
}

export function AnswerBadge({ type }: { type: AnswerType }) {
  const meta = ANSWER_META[type];
  return (
    <Pill tone={meta.tone} title={meta.hint}>
      <span className="size-1.5 rounded-full bg-current" />
      {meta.label}
    </Pill>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("skeleton", className)} />;
}

export function Logo({ compact }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="size-8 shrink-0" aria-hidden>
        <rect width="32" height="32" rx="9" className="fill-ink dark:fill-accent" />
        <path d="M10 9v14M10 16l7-7M13 13l7 10" className="stroke-accent dark:stroke-on-accent" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        <circle cx="22.5" cy="10" r="2" className="fill-accent dark:fill-on-accent" />
      </svg>
      {!compact && <span className="text-[15px] font-semibold tracking-tight">Knowledge<span className="text-muted">.ai</span></span>}
    </span>
  );
}

/** Wraps query terms found in `text` with <mark>. */
export function Highlight({ text, query }: { text: string; query: string }) {
  const terms = queryTerms(query);
  if (!terms.length) return <>{text}</>;
  const re = new RegExp(`(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  return <>{text.split(re).map((part, i) => (i % 2 ? <mark key={i}>{part}</mark> : part))}</>;
}

export function EmptyState({ icon, title, body, action }: {
  icon: ReactNode; title: string; body: string; action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-14 px-6">
      <div className="size-14 rounded-2xl bg-sunken grid place-items-center text-muted mb-4">{icon}</div>
      <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
      <p className="text-muted text-sm mt-1.5 max-w-sm">{body}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="font-mono text-[11px] rounded-md border border-line bg-surface-2 px-1.5 py-0.5 text-muted">{children}</kbd>;
}
