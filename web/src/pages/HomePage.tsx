import { ArrowRight, ArrowUpRight, FileText, MessageSquareText, Search } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { NODE_LABEL } from "../components/AgentSteps";
import { Dial } from "../components/charts";
import { Dropzone, DropHint, useUploader } from "../components/Dropzone";
import { Button, Card, Kbd, Pill, Skeleton, cx } from "../components/ui";
import { api } from "../lib/api";
import { useApp } from "../lib/app-state";
import { fileKind, greeting, relativeTime } from "../lib/format";
import type { Conversation, Doc, WorkspaceStats } from "../lib/types";

const SAMPLE_QUESTIONS: Record<string, string[]> = {
  "product_faq.txt": ["What does error code E-417 mean?", "How long is the HX-200 warranty?"],
  "employee_handbook.md": ["How many days of annual leave do I get?"],
  "travel_policy.md": ["What is the hotel limit per night in London?"],
  "it_security_policy.md": ["How quickly must a security incident be reported?"],
};

export function suggestionsFor(docs: Doc[]): string[] {
  const fromDocs = docs.flatMap((d) => SAMPLE_QUESTIONS[d.filename] ?? []);
  return [...fromDocs.slice(0, 4), ...(docs.length ? ["Which documents do I have?"] : [])];
}

export function HomePage() {
  const { navigate, user } = useApp();
  const [stats, setStats] = useState<WorkspaceStats | null>(null);
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [convos, setConvos] = useState<Conversation[] | null>(null);
  const [question, setQuestion] = useState("");
  const { upload, busy } = useUploader();

  useEffect(() => {
    api.stats().then(setStats).catch(() => setStats(null));
    api.documents().then(setDocs).catch(() => setDocs([]));
    api.conversations().then(setConvos).catch(() => setConvos([]));
  }, []);

  const ask = (q: string) => q.trim() && navigate({ name: "ask", prefill: q.trim() });
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    ask(question);
  };
  const a = stats?.answers_by_type ?? {};
  const checked = (a.grounded ?? 0) + (a.refused ?? 0) + (a.unverified ?? 0);
  const name = user?.email.split("@")[0].replace(/[._-]+/g, " ") ?? "";

  return (
    <div className="pt-4 sm:pt-8 space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-4 px-1">
        <div>
          <p className="label">{new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}</p>
          <h1 className="text-[40px] sm:text-5xl font-semibold tracking-[-0.04em] mt-2 leading-none">
            {greeting()}, <span className="text-muted capitalize">{name}</span>
          </h1>
        </div>
        {stats && (
          <p className="text-muted text-sm">
            <span className="text-ink font-medium tabular">{stats.documents}</span> documents ·{" "}
            <span className="text-ink font-medium tabular">{stats.pages}</span> pages indexed
          </p>
        )}
      </header>

      <div className="grid grid-cols-12 gap-4">
        <Card className="col-span-12 lg:col-span-8 flex flex-col justify-between gap-8 min-h-[280px]">
          <div>
            <p className="label">Ask your knowledge base</p>
            <form onSubmit={onSubmit} className="mt-4 relative">
              <Search className="absolute left-6 top-1/2 -translate-y-1/2 size-5 text-muted" />
              <input value={question} onChange={(e) => setQuestion(e.target.value)} aria-label="Ask a question"
                placeholder="What would you like to know?"
                className="w-full h-16 sm:h-[72px] rounded-full bg-sunken pl-14 pr-16 sm:pr-36 text-base sm:text-xl tracking-tight placeholder:text-faint focus:outline-none focus:ring-4 focus:ring-accent/50 transition" />
              <Button type="submit" variant="accent" aria-label="Ask" className="absolute right-2.5 sm:right-3 top-1/2 -translate-y-1/2 h-11 sm:h-12 w-11 sm:w-auto !px-0 sm:!px-5" disabled={!question.trim()}>
                <span className="hidden sm:inline">Ask</span> <ArrowRight className="size-4" />
              </Button>
            </form>
          </div>
          <div>
            <p className="label mb-3">Try asking</p>
            <div className="flex flex-wrap gap-2">
              {docs === null
                ? [1, 2, 3].map((i) => <Skeleton key={i} className="h-9 w-48 rounded-full" />)
                : suggestionsFor(docs).length
                  ? suggestionsFor(docs).map((s) => (
                      <button key={s} onClick={() => ask(s)}
                        className="group inline-flex items-center gap-1.5 text-left rounded-[1.25rem] border border-line bg-surface-2 px-4 min-h-9 py-2 text-sm hover:border-ink transition">
                        {s}<ArrowUpRight className="size-3.5 text-faint group-hover:text-ink transition" />
                      </button>
                    ))
                  : <p className="text-sm text-muted">Upload a document first, then ask about it here.</p>}
            </div>
          </div>
        </Card>

        <Dropzone onFiles={(f) => upload(f).then(() => navigate({ name: "library" }))}
          className="col-span-12 sm:col-span-6 lg:col-span-4 rounded-card bg-accent text-on-accent p-6 flex flex-col justify-end min-h-[280px] relative overflow-hidden hover:bg-accent-strong"
          activeClassName="ring-4 ring-ink scale-[0.99]">
          <svg className="absolute -right-6 -top-6 size-48 opacity-[0.13]" viewBox="0 0 100 100" aria-hidden>
            {[0, 1, 2, 3].map((i) => <rect key={i} x={20 + i * 7} y={10 + i * 9} width="50" height="64" rx="8" fill="none" stroke="currentColor" strokeWidth="2.5" />)}
          </svg>
          <DropHint busy={busy} />
        </Dropzone>

        <Metric className="col-span-6 sm:col-span-6 lg:col-span-3" label="Documents" value={stats?.documents}
          sub={stats ? `${stats.documents_by_status.ready ?? 0} ready · ${stats.documents_by_status.failed ?? 0} failed` : undefined} />
        <Metric className="col-span-6 lg:col-span-3" label="Passages indexed" value={stats?.chunks}
          sub={stats ? `from ${stats.pages} pages` : undefined} />
        <Metric className="col-span-6 lg:col-span-3" label="Questions asked" value={stats?.questions}
          sub={stats ? `in ${stats.conversations} conversations` : undefined} />
        <Metric className="col-span-6 lg:col-span-3" label="Verified answers" value={a.grounded}
          sub={checked ? `${Math.round(((a.grounded ?? 0) / checked) * 100)}% of document questions` : "no document questions yet"} />

        <Card className="col-span-12 md:col-span-6 lg:col-span-4">
          <div className="flex items-center justify-between">
            <p className="label">Answer quality</p>
            <Pill tone="muted">all time</Pill>
          </div>
          <div className="flex flex-col items-center mt-3">
            {stats ? (
              <Dial
                center={checked ? `${Math.round(((a.grounded ?? 0) / checked) * 100)}%` : "—"}
                caption="verified"
                segments={[
                  { label: "Verified", value: a.grounded ?? 0, color: "var(--accent)" },
                  { label: "Declined", value: a.refused ?? 0, color: "var(--faint)" },
                  { label: "Withheld", value: a.unverified ?? 0, color: "var(--warn)" },
                ]}
              />
            ) : <Skeleton className="size-44 rounded-full" />}
          </div>
          <ul className="mt-2 grid grid-cols-3 gap-2 text-center">
            {[["Verified", a.grounded, "bg-accent"], ["Declined", a.refused, "bg-faint"], ["Withheld", a.unverified, "bg-warn"]].map(([l, v, c]) => (
              <li key={l as string} className="rounded-2xl bg-surface-2 py-2.5">
                <p className="text-xl font-semibold tabular">{(v as number) ?? 0}</p>
                <p className="text-[11px] text-muted inline-flex items-center gap-1.5"><span className={cx("size-1.5 rounded-full", c as string)} />{l}</p>
              </li>
            ))}
          </ul>
          <p className="text-xs text-faint mt-3">Declining when the documents don't contain the answer is a success, not a failure.</p>
        </Card>

        <Card tone="contrast" className="col-span-12 md:col-span-6 lg:col-span-4">
          <p className="label !text-contrast-muted">How every answer is checked</p>
          <ol className="mt-5 space-y-3">
            {["route", "retrieve", "grade", "generate", "verify"].map((n, i) => (
              <li key={n} className="flex items-center gap-3">
                <span className={cx("size-7 rounded-full grid place-items-center text-xs font-mono font-semibold shrink-0",
                  i === 4 ? "bg-accent text-on-accent" : "bg-on-contrast/10")}>{i + 1}</span>
                <span className="text-sm">{NODE_LABEL[n]}</span>
              </li>
            ))}
          </ol>
          <p className="text-[13px] text-contrast-muted mt-5 leading-relaxed">
            Hybrid search (meaning + exact keywords) finds the passages. Code rejects made-up citations, and a second
            pass checks every claim against the sources.
          </p>
        </Card>

        <Card className="col-span-12 lg:col-span-4 flex flex-col">
          <div className="flex items-center justify-between">
            <p className="label">Recent conversations</p>
            <button onClick={() => navigate({ name: "ask" })} className="text-xs text-muted hover:text-ink inline-flex items-center gap-1">
              New <Kbd>⌘K</Kbd>
            </button>
          </div>
          <ul className="mt-3 -mx-2 flex-1">
            {convos === null && [1, 2, 3].map((i) => <Skeleton key={i} className="h-12 m-2" />)}
            {convos?.length === 0 && (
              <li className="h-full grid place-items-center text-center text-sm text-muted py-8">
                <span><MessageSquareText className="size-5 mx-auto mb-2 text-faint" />Your questions will show up here.</span>
              </li>
            )}
            {convos?.slice(0, 5).map((c) => (
              <li key={c.id}>
                <a href={`#/ask/${c.id}`} onClick={(e) => { e.preventDefault(); navigate({ name: "ask", conversationId: c.id }); }}
                  className="flex items-center gap-3 rounded-2xl px-2 py-2.5 hover:bg-surface-2 transition">
                  <span className="size-9 rounded-xl bg-sunken grid place-items-center shrink-0"><MessageSquareText className="size-4 text-muted" /></span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium truncate">{c.title}</span>
                    <span className="block text-xs text-faint">{c.questions} question{c.questions > 1 ? "s" : ""} · {relativeTime(c.created_at)}</span>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="col-span-12">
          <div className="flex items-center justify-between">
            <p className="label">Library</p>
            <button onClick={() => navigate({ name: "library" })} className="text-sm text-muted hover:text-ink inline-flex items-center gap-1">
              Manage <ArrowRight className="size-3.5" />
            </button>
          </div>
          <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {docs === null && [1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-28" />)}
            {docs?.length === 0 && <p className="col-span-full text-sm text-muted py-4">No documents yet. Drop a file on the lime card above.</p>}
            {docs?.slice(0, 6).map((d) => (
              <div key={d.id} className="rounded-2xl bg-surface-2 border border-line p-4 flex flex-col justify-between h-28">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] tracking-wider rounded-md bg-sunken px-1.5 py-0.5 text-muted">{fileKind(d.filename)}</span>
                  <FileText className="size-4 text-faint" />
                </div>
                <div>
                  <p className="text-sm font-medium truncate" title={d.filename}>{d.filename}</p>
                  <p className="text-xs text-faint">{d.status === "ready" ? `${d.num_pages} page${d.num_pages === 1 ? "" : "s"} · ${d.num_chunks} passages` : d.status}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

function Metric({ label, value, sub, className }: { label: string; value?: number; sub?: string; className?: string }) {
  return (
    <Card className={cx("flex flex-col justify-between min-h-[140px]", className)}>
      <p className="label">{label}</p>
      {value === undefined && sub === undefined
        ? <Skeleton className="h-12 w-24 mt-4" />
        : <p className="text-5xl font-semibold tracking-[-0.04em] tabular mt-4 leading-none">{value ?? 0}</p>}
      <p className="text-xs text-muted mt-2 truncate">{sub ?? " "}</p>
    </Card>
  );
}
