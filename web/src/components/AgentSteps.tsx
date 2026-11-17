import { Check, CircleDashed } from "lucide-react";
import { cx } from "./ui";

export const NODE_LABEL: Record<string, string> = {
  route: "Understanding the question",
  retrieve: "Searching your documents",
  grade: "Checking which passages are relevant",
  rewrite: "Rephrasing the search",
  generate: "Drafting an answer from sources",
  verify: "Verifying every claim",
  tool_agent: "Calling library tools over MCP",
  direct: "Replying",
  refuse: "Nothing relevant found",
  unverified: "Withholding an unverified draft",
};

export interface Step { node: string; trace: string[] }

/** Live timeline of graph nodes. `running` adds a pulsing "working" row after the last finished step. */
export function AgentSteps({ steps, running, compact }: { steps: Step[]; running?: boolean; compact?: boolean }) {
  return (
    <ol className="relative space-y-0.5">
      {steps.map((s, i) => (
        <li key={i} className="rise flex gap-3 items-start">
          <span className="mt-0.5 size-5 rounded-full bg-accent text-on-accent grid place-items-center shrink-0">
            <Check className="size-3" strokeWidth={3} />
          </span>
          <div className="min-w-0 pb-2">
            <p className="text-sm font-medium leading-5">{NODE_LABEL[s.node] ?? s.node}</p>
            {!compact && s.trace.map((t, j) => (
              <p key={j} className="font-mono text-[11px] text-muted leading-4 mt-0.5 break-words">{t}</p>
            ))}
          </div>
        </li>
      ))}
      {running && (
        <li className="flex gap-3 items-center">
          <span className={cx("size-5 rounded-full grid place-items-center shrink-0 text-muted")}>
            <CircleDashed className="size-4 animate-spin [animation-duration:2.4s]" />
          </span>
          <span className="flex gap-1">
            {[0, 1, 2].map((d) => (
              <span key={d} className="pulse-dot size-1.5 rounded-full bg-muted" style={{ animationDelay: `${d * 0.15}s` }} />
            ))}
          </span>
        </li>
      )}
    </ol>
  );
}
