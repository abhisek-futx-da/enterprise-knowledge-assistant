import type { AnswerType } from "./types";

export function relativeTime(iso: string): string {
  const then = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`).getTime();
  const s = Math.max(0, (Date.now() - then) / 1000);
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  if (s < 604800) return `${Math.round(s / 86400)}d ago`;
  return new Date(then).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export function fileKind(name: string): string {
  return name.split(".").pop()?.toUpperCase() ?? "FILE";
}

export const ANSWER_META: Record<AnswerType, { label: string; hint: string; tone: string }> = {
  grounded: { label: "Verified", hint: "Every claim is backed by a cited passage and passed the fact-check.", tone: "good" },
  refused: { label: "Not in your documents", hint: "Nothing relevant was found, so the assistant declined instead of guessing.", tone: "muted" },
  unverified: { label: "Withheld", hint: "A draft answer failed verification twice, so it was not shown.", tone: "warn" },
  tool: { label: "Library tools", hint: "Answered by calling knowledge-base tools over MCP.", tone: "info" },
  direct: { label: "Assistant", hint: "A conversational reply with no document facts.", tone: "muted" },
};

const STOP = new Set("a an and are as at be by for from has have how i in is it its of on or that the this to was what when where which who why will with do does did can you your we our".split(" "));

export function queryTerms(q: string): string[] {
  return [...new Set(q.toLowerCase().match(/[a-z0-9][a-z0-9.-]*/g) ?? [])].filter((t) => t.length > 1 && !STOP.has(t));
}
