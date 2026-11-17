import {
  ArrowUp, Check, ChevronDown, Copy, FileText, MessageSquarePlus, MessageSquareText, PanelRightOpen, Square, Wrench,
} from "lucide-react";
import { Fragment, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { AgentSteps, type Step } from "../components/AgentSteps";
import { AnswerBadge, Button, Highlight, Kbd, Skeleton, cx } from "../components/ui";
import { api, ApiError, streamChat } from "../lib/api";
import { useApp } from "../lib/app-state";
import { ANSWER_META, relativeTime } from "../lib/format";
import type { AnswerType, ChatResult, Citation, Conversation, Doc } from "../lib/types";
import { suggestionsFor } from "./HomePage";

let seq = 0;
const uid = () => `t${++seq}`; // crypto.randomUUID needs a secure context; plain-HTTP deploys lack one

interface Turn {
  id: string;
  question: string;
  steps: Step[];
  running: boolean;
  result?: Pick<ChatResult, "answer" | "answer_type" | "citations"> & Partial<ChatResult>;
  error?: string;
}

export function AskPage({ conversationId, prefill }: { conversationId?: string; prefill?: string }) {
  const { navigate, toast } = useApp();
  const [activeId, setActiveId] = useState<string | null>(conversationId ?? null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  const [convos, setConvos] = useState<Conversation[] | null>(null);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [focus, setFocus] = useState<{ turn: string; cite?: string } | null>(null);
  const abort = useRef<AbortController | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const sentPrefill = useRef<string | null>(null);
  const idRef = useRef<string | null>(activeId);
  idRef.current = activeId;

  const refreshConvos = useCallback(() => api.conversations().then(setConvos).catch(() => setConvos([])), []);
  useEffect(() => {
    refreshConvos();
    api.documents().then(setDocs).catch(() => {});
  }, [refreshConvos]);

  // Load history when the URL points at a conversation this page isn't already showing.
  useEffect(() => {
    if (!conversationId) {
      if (!prefill) { setActiveId(null); setTurns([]); }
      return;
    }
    if (conversationId === idRef.current && turns.length) return;
    setActiveId(conversationId);
    setLoading(true);
    api.messages(conversationId)
      .then((msgs) => {
        const out: Turn[] = [];
        for (const m of msgs) {
          if (m.role === "user") out.push({ id: uid(), question: m.content, steps: [], running: false });
          else if (out.length) out[out.length - 1].result = {
            answer: m.content, answer_type: (m.answer_type ?? "direct") as AnswerType, citations: m.citations ?? [],
          };
        }
        setTurns(out);
        setFocus(null);
      })
      .catch((e) => toast(e instanceof ApiError ? e.message : "Couldn't load that conversation", "error"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  const send = useCallback(async (question: string) => {
    const q = question.trim();
    if (!q || abort.current) return;
    const id = uid();
    const update = (fn: (t: Turn) => Turn) => setTurns((all) => all.map((t) => (t.id === id ? fn(t) : t)));
    setTurns((all) => [...all, { id, question: q, steps: [], running: true }]);
    setFocus(null);
    abort.current = new AbortController();
    try {
      await streamChat(q, idRef.current, (ev) => {
        if (ev.type === "start" && ev.conversation_id !== idRef.current) {
          idRef.current = ev.conversation_id;
          setActiveId(ev.conversation_id);
          navigate({ name: "ask", conversationId: ev.conversation_id }, { replace: true });
        } else if (ev.type === "step") {
          update((t) => ({ ...t, steps: [...t.steps, { node: ev.node, trace: ev.trace }] }));
        } else if (ev.type === "final") {
          update((t) => ({ ...t, running: false, result: ev }));
          if (ev.citations.length) setFocus({ turn: id });
        } else if (ev.type === "error") {
          update((t) => ({ ...t, running: false, error: ev.detail }));
        }
      }, abort.current.signal);
      refreshConvos();
    } catch (e) {
      const stopped = (e as Error).name === "AbortError";
      update((t) => ({ ...t, running: false, error: stopped ? "Stopped." : e instanceof ApiError ? e.message : "Something went wrong." }));
    } finally {
      abort.current = null;
      update((t) => (t.running ? { ...t, running: false, error: t.result ? undefined : "The answer stream ended early." } : t));
    }
  }, [navigate, refreshConvos]);

  useEffect(() => {
    if (prefill && sentPrefill.current !== prefill) {
      sentPrefill.current = prefill;
      setActiveId(null);
      idRef.current = null;
      setTurns([]);
      setTimeout(() => send(prefill), 0);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill]);

  const running = turns.some((t) => t.running);
  const evidenceTurn = (focus && turns.find((t) => t.id === focus.turn)) || [...turns].reverse().find((t) => t.result?.citations.length);

  return (
    <div className="pt-4 grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)] xl:grid-cols-[260px_minmax(0,1fr)_380px] h-[calc(100dvh-10.5rem)] md:h-[calc(100dvh-5rem)]">
      <aside className="hidden lg:flex flex-col rounded-card bg-surface border border-line shadow-card p-3 min-h-0">
        <Button variant="accent" className="w-full h-11" onClick={() => { navigate({ name: "ask" }); setTimeout(() => document.getElementById("composer")?.focus(), 30); }}>
          <MessageSquarePlus className="size-4" /> New conversation
        </Button>
        <p className="label px-2 mt-5 mb-2">History</p>
        <ul className="flex-1 overflow-y-auto scroll-thin space-y-0.5">
          {convos === null && [1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-11 m-1" />)}
          {convos?.length === 0 && <li className="text-sm text-muted px-2 py-3">No conversations yet.</li>}
          {convos?.map((c) => (
            <li key={c.id}>
              <a href={`#/ask/${c.id}`} onClick={(e) => { e.preventDefault(); navigate({ name: "ask", conversationId: c.id }); }}
                aria-current={c.id === activeId ? "page" : undefined}
                className={cx("block rounded-xl px-3 py-2 transition", c.id === activeId ? "bg-sunken" : "hover:bg-surface-2")}>
                <span className="block text-sm truncate">{c.title}</span>
                <span className="block text-[11px] text-faint">{relativeTime(c.created_at)}</span>
              </a>
            </li>
          ))}
        </ul>
      </aside>

      <section className="flex flex-col min-h-0 rounded-card bg-surface border border-line shadow-card overflow-hidden">
        <div ref={scroller} className="flex-1 overflow-y-auto scroll-thin px-4 sm:px-8 py-6">
          {loading ? (
            <div className="space-y-4 max-w-3xl mx-auto"><Skeleton className="h-10 w-2/3 ml-auto" /><Skeleton className="h-40" /></div>
          ) : turns.length === 0 ? (
            <Welcome docs={docs} onAsk={send} />
          ) : (
            <div className="max-w-3xl mx-auto space-y-8">
              {turns.map((t) => (
                <TurnView key={t.id} turn={t} focused={focus?.turn === t.id ? focus.cite : undefined}
                  onCite={(cite) => setFocus({ turn: t.id, cite })} />
              ))}
            </div>
          )}
        </div>
        <Composer running={running} onSend={send} onStop={() => abort.current?.abort()} />
      </section>

      <aside className="hidden xl:flex flex-col rounded-card bg-surface border border-line shadow-card min-h-0 overflow-hidden">
        <Evidence turn={evidenceTurn} activeCite={focus?.cite} />
      </aside>
    </div>
  );
}

function Welcome({ docs, onAsk }: { docs: Doc[]; onAsk: (q: string) => void }) {
  const suggestions = suggestionsFor(docs);
  return (
    <div className="h-full flex flex-col items-center justify-center text-center max-w-xl mx-auto py-10">
      <div className="size-14 shrink-0 rounded-2xl bg-accent text-on-accent grid place-items-center"><MessageSquareText className="size-6" /></div>
      <h1 className="text-3xl sm:text-4xl font-semibold tracking-[-0.035em] mt-5">Ask your documents anything</h1>
      <p className="text-muted mt-2">
        Answers cite the exact file and page. When your documents don't cover a question, you'll be told so instead of
        getting a guess.
      </p>
      {suggestions.length > 0 ? (
        <div className="mt-8 grid sm:grid-cols-2 gap-2 w-full">
          {suggestions.map((s) => (
            <button key={s} onClick={() => onAsk(s)}
              className="text-left rounded-2xl border border-line bg-surface-2 hover:border-ink px-4 py-3 text-sm transition">{s}</button>
          ))}
        </div>
      ) : (
        <a href="#/library" className="mt-8 text-sm underline underline-offset-4">Upload a document to get started</a>
      )}
    </div>
  );
}

function TurnView({ turn, focused, onCite }: { turn: Turn; focused?: string; onCite: (id: string) => void }) {
  const [showTrace, setShowTrace] = useState(false);
  const [copied, setCopied] = useState(false);
  const r = turn.result;
  return (
    <article className="space-y-4">
      <div className="flex justify-end">
        <p className="rise max-w-[85%] rounded-3xl rounded-br-lg bg-ink text-bg px-5 py-3 text-[15px] leading-relaxed whitespace-pre-wrap">{turn.question}</p>
      </div>
      <div className="rise">
        {turn.running && (
          <div className="rounded-3xl bg-surface-2 border border-line p-5">
            <p className="label mb-3">Working</p>
            <AgentSteps steps={turn.steps} running />
          </div>
        )}
        {turn.error && !r && (
          <div role="alert" className="rounded-3xl bg-bad/10 text-bad px-5 py-4 text-sm">{turn.error}</div>
        )}
        {r && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <AnswerBadge type={r.answer_type} />
              {r.cached && <span className="text-[11px] text-faint">served from cache</span>}
            </div>
            <div className={cx("text-[16px] leading-[1.7]", r.answer_type === "refused" || r.answer_type === "unverified" ? "text-muted" : "")}>
              <AnswerText text={r.answer} citations={r.citations} focused={focused} onCite={onCite} />
            </div>
            {(r.answer_type === "refused" || r.answer_type === "unverified") && (
              <p className="mt-3 text-sm text-faint">{ANSWER_META[r.answer_type].hint}</p>
            )}
            {r.citations.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2 xl:hidden">
                {r.citations.map((c) => <SourceChip key={c.id} c={c} onClick={() => onCite(c.id)} />)}
              </div>
            )}
            {r.citations.length > 0 && <MobileSources citations={r.citations} />}
            {r.tool_calls && r.tool_calls.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {r.tool_calls.map((tc, i) => (
                  <span key={i} className="inline-flex items-center gap-1.5 rounded-full bg-info/10 text-info px-3 py-1 font-mono text-xs">
                    <Wrench className="size-3" /> {tc.tool}()
                  </span>
                ))}
              </div>
            )}
            <div className="mt-4 flex items-center gap-1 text-muted">
              <button onClick={() => { void navigator.clipboard?.writeText(r.answer); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
                className="inline-flex items-center gap-1.5 rounded-full px-3 h-8 text-xs hover:bg-sunken hover:text-ink transition">
                {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}{copied ? "Copied" : "Copy"}
              </button>
              {turn.steps.length > 0 && (
                <button onClick={() => setShowTrace((s) => !s)} aria-expanded={showTrace}
                  className="inline-flex items-center gap-1.5 rounded-full px-3 h-8 text-xs hover:bg-sunken hover:text-ink transition">
                  <ChevronDown className={cx("size-3.5 transition", showTrace && "rotate-180")} /> How this was answered
                </button>
              )}
            </div>
            {showTrace && (
              <div className="mt-2 rounded-3xl bg-surface-2 border border-line p-5"><AgentSteps steps={turn.steps} /></div>
            )}
          </div>
        )}
      </div>
    </article>
  );
}

/** Renders paragraphs, simple lists and **bold**, turning [S1] markers into numbered citation chips. */
function AnswerText({ text, citations, focused, onCite }: {
  text: string; citations: Citation[]; focused?: string; onCite: (id: string) => void;
}) {
  const known = new Set(citations.map((c) => c.id));
  const inline = (line: string): ReactNode[] =>
    line.split(/(\[S\d+\]|\*\*[^*]+\*\*)/g).map((part, i) => {
      const cite = part.match(/^\[(S\d+)\]$/);
      if (cite) {
        if (!known.has(cite[1])) return null;
        return (
          <button key={i} onClick={() => onCite(cite[1])} aria-label={`Show source ${cite[1].slice(1)}`}
            className={cx("mx-0.5 inline-grid place-items-center min-w-5 h-5 px-1 rounded-md text-[11px] font-semibold align-[2px] transition",
              focused === cite[1] ? "bg-ink text-bg" : "bg-accent text-on-accent hover:bg-accent-strong")}>
            {cite[1].slice(1)}
          </button>
        );
      }
      if (part.startsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
      return <Fragment key={i}>{part}</Fragment>;
    });
  const blocks = text.split(/\n{2,}/);
  return (
    <div className="space-y-3">
      {blocks.map((block, i) => {
        const lines = block.split("\n");
        if (lines.every((l) => /^\s*([-*]|\d+\.)\s/.test(l))) {
          return (
            <ul key={i} className="space-y-1.5 pl-1">
              {lines.map((l, j) => (
                <li key={j} className="flex gap-2.5"><span className="mt-[11px] size-1.5 rounded-full bg-faint shrink-0" />
                  <span>{inline(l.replace(/^\s*([-*]|\d+\.)\s/, ""))}</span></li>
              ))}
            </ul>
          );
        }
        return <p key={i}>{lines.map((l, j) => <Fragment key={j}>{j > 0 && <br />}{inline(l)}</Fragment>)}</p>;
      })}
    </div>
  );
}

function SourceChip({ c, onClick }: { c: Citation; onClick: () => void }) {
  return (
    <button onClick={onClick} className="inline-flex items-center gap-2 rounded-full border border-line bg-surface-2 pl-1 pr-3 h-8 text-xs hover:border-ink transition">
      <span className="size-6 rounded-full bg-accent text-on-accent grid place-items-center font-semibold">{c.id.slice(1)}</span>
      <span className="truncate max-w-[180px]">{c.filename}</span><span className="text-faint">p.{c.page}</span>
    </button>
  );
}

function MobileSources({ citations }: { citations: Citation[] }) {
  return (
    <details className="xl:hidden mt-3 group">
      <summary className="list-none cursor-pointer inline-flex items-center gap-1.5 text-xs text-muted hover:text-ink">
        <PanelRightOpen className="size-3.5" /> Read the cited passages
      </summary>
      <div className="mt-3 space-y-2">
        {citations.map((c) => <SourceCard key={c.id} c={c} query="" />)}
      </div>
    </details>
  );
}

function SourceCard({ c, query, active }: { c: Citation; query: string; active?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (active) ref.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [active]);
  return (
    <div ref={ref} className={cx("rounded-2xl border p-4 transition", active ? "border-ink bg-surface-2 ring-4 ring-accent/40" : "border-line bg-surface-2")}>
      <div className="flex items-center gap-2.5">
        <span className="size-6 rounded-full bg-accent text-on-accent grid place-items-center text-xs font-semibold shrink-0">{c.id.slice(1)}</span>
        <FileText className="size-3.5 text-muted shrink-0" />
        <span className="text-sm font-medium truncate">{c.filename}</span>
        <span className="ml-auto font-mono text-[11px] text-faint shrink-0">PAGE {c.page}</span>
      </div>
      <p className="mt-3 text-[13px] leading-relaxed text-muted whitespace-pre-wrap">
        <Highlight text={c.snippet} query={query} />
      </p>
    </div>
  );
}

function Evidence({ turn, activeCite }: { turn?: Turn; activeCite?: string }) {
  const r = turn?.result;
  return (
    <>
      <div className="px-5 pt-5 pb-3 border-b border-line">
        <p className="label">Evidence</p>
        <p className="text-sm text-muted mt-1">
          {r?.citations.length ? `${r.citations.length} passage${r.citations.length > 1 ? "s" : ""} behind this answer` : "Sources appear here as you ask"}
        </p>
      </div>
      <div className="flex-1 overflow-y-auto scroll-thin p-4 space-y-3">
        {turn?.running && [1, 2].map((i) => <Skeleton key={i} className="h-36" />)}
        {r?.citations.map((c) => <SourceCard key={c.id} c={c} query={turn!.question} active={activeCite === c.id} />)}
        {!turn?.running && !r?.citations.length && (
          <div className="h-full grid place-items-center text-center px-6">
            <div>
              <div className="mx-auto size-12 rounded-2xl bg-sunken grid place-items-center text-faint"><FileText className="size-5" /></div>
              <p className="text-sm text-muted mt-3">
                Click a numbered chip in an answer to read the exact passage it came from. Words from your question are
                highlighted.
              </p>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

function Composer({ running, onSend, onStop }: { running: boolean; onSend: (q: string) => void; onStop: () => void }) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [value]);
  const submit = () => {
    if (!value.trim() || running) return;
    onSend(value);
    setValue("");
  };
  return (
    <div className="p-3 sm:p-4 border-t border-line bg-surface">
      <div className="max-w-3xl mx-auto flex items-end gap-2 rounded-[1.75rem] bg-sunken p-2 pl-5 focus-within:ring-4 focus-within:ring-accent/40 transition">
        <textarea id="composer" ref={ref} rows={1} value={value} onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); } }}
          placeholder="Ask about your documents…" aria-label="Your question" maxLength={2000}
          className="flex-1 resize-none bg-transparent py-2.5 text-[15px] leading-6 placeholder:text-faint focus:outline-none focus-visible:outline-none max-h-[180px]" />
        {running ? (
          <button onClick={onStop} aria-label="Stop" className="size-11 rounded-full bg-ink text-bg grid place-items-center shrink-0">
            <Square className="size-3.5 fill-current" />
          </button>
        ) : (
          <button onClick={submit} disabled={!value.trim()} aria-label="Send"
            className="size-11 rounded-full bg-accent text-on-accent grid place-items-center shrink-0 disabled:opacity-40 transition hover:bg-accent-strong">
            <ArrowUp className="size-5" />
          </button>
        )}
      </div>
      <p className="hidden sm:block text-center text-[11px] text-faint mt-2">
        <Kbd>Enter</Kbd> to send · <Kbd>Shift</Kbd>+<Kbd>Enter</Kbd> for a new line · answers only use your documents
      </p>
    </div>
  );
}
