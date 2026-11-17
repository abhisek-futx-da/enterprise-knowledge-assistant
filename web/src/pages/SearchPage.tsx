import { ArrowRight, Info, ScanSearch } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Button, Card, EmptyState, Highlight, Pill, Skeleton, cx } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useApp } from "../lib/app-state";
import type { SearchHit, SearchMode } from "../lib/types";

const MODES: { mode: SearchMode; title: string; blurb: string }[] = [
  { mode: "vector", title: "Semantic", blurb: "Embeddings match meaning, even with different words." },
  { mode: "bm25", title: "Keyword · BM25", blurb: "Exact terms, codes and names, weighted by rarity." },
  { mode: "hybrid", title: "Hybrid · RRF", blurb: "Both lists fused by rank. This is what the assistant uses." },
];
const EXAMPLES = ["E-417", "how much time off do I get", "hotel cap London", "report a security incident"];

export function SearchPage({ initial }: { initial?: string }) {
  const { navigate, toast } = useApp();
  const [query, setQuery] = useState(initial ?? "");
  const [ran, setRan] = useState<string | null>(null);
  const [results, setResults] = useState<Record<SearchMode, SearchHit[]> | null>(null);
  const [busy, setBusy] = useState(false);
  const [hover, setHover] = useState<string | null>(null);

  async function run(q: string) {
    if (!q.trim()) return;
    setBusy(true);
    try {
      const [vector, bm25, hybrid] = await Promise.all(MODES.map((m) => api.search(q, m.mode, 5)));
      setResults({ vector, bm25, hybrid });
      setRan(q);
      navigate({ name: "search", query: q }, { replace: true });
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Search failed", "error");
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => { if (initial) void run(initial); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const submit = (e: FormEvent) => { e.preventDefault(); void run(query); };

  return (
    <div className="pt-4 sm:pt-8 space-y-4">
      <header className="px-1">
        <p className="label">Search lab</p>
        <h1 className="text-4xl sm:text-5xl font-semibold tracking-[-0.04em] mt-2 leading-none">See how retrieval decides</h1>
        <p className="text-muted mt-3 max-w-2xl">
          One query, three retrievers. No language model is involved here. Hover a result to see where the same passage
          ranks in the other lists.
        </p>
      </header>

      <Card>
        <form onSubmit={submit} className="flex flex-col sm:flex-row gap-3">
          <input value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search query" placeholder="Try an error code, a policy, a phrase…"
            className="flex-1 h-14 rounded-full bg-sunken px-6 text-lg tracking-tight placeholder:text-faint focus:outline-none focus:ring-4 focus:ring-accent/50" />
          <Button type="submit" className="h-14 px-7 text-[15px]" loading={busy} disabled={!query.trim()}>
            Compare <ArrowRight className="size-4" />
          </Button>
        </form>
        <div className="flex flex-wrap gap-2 mt-4 items-center">
          <span className="label mr-1">Examples</span>
          {EXAMPLES.map((ex) => (
            <button key={ex} onClick={() => { setQuery(ex); void run(ex); }}
              className="rounded-full border border-line bg-surface-2 px-3 h-8 text-sm hover:border-ink transition font-mono text-[13px]">{ex}</button>
          ))}
        </div>
      </Card>

      {!results && !busy ? (
        <Card><EmptyState icon={<ScanSearch className="size-6" />} title="Run a query to compare"
          body="Exact identifiers like E-417 favour keyword search. Paraphrases like “time off” favour semantic search. Hybrid keeps both." /></Card>
      ) : (
        <div className="grid lg:grid-cols-3 gap-4">
          {MODES.map(({ mode, title, blurb }) => {
            const hits = results?.[mode] ?? [];
            const max = Math.max(1e-9, ...hits.map((h) => h.score));
            return (
              <Card key={mode} tone={mode === "hybrid" ? "contrast" : "surface"} className="!p-0 overflow-hidden flex flex-col">
                <div className="p-5 pb-4">
                  <div className="flex items-center justify-between">
                    <h2 className="font-semibold tracking-tight text-lg">{title}</h2>
                    {mode === "hybrid" && <Pill className="!bg-accent !text-on-accent">used by the agent</Pill>}
                  </div>
                  <p className={cx("text-sm mt-1", mode === "hybrid" ? "text-contrast-muted" : "text-muted")}>{blurb}</p>
                </div>
                <ol className="px-3 pb-3 space-y-2 flex-1">
                  {busy && [1, 2, 3].map((i) => <Skeleton key={i} className="h-28" />)}
                  {!busy && hits.length === 0 && (
                    <li className={cx("text-sm px-3 py-6 text-center", mode === "hybrid" ? "text-contrast-muted" : "text-muted")}>
                      No passages matched.
                    </li>
                  )}
                  {!busy && hits.map((h, i) => (
                    <li key={h.chunk_id} onMouseEnter={() => setHover(h.chunk_id)} onMouseLeave={() => setHover(null)}
                      className={cx("rounded-2xl p-4 transition",
                        mode === "hybrid" ? "bg-on-contrast/[0.07]" : "bg-surface-2 border border-line",
                        hover === h.chunk_id && "ring-2 ring-accent",
                        hover && hover !== h.chunk_id && "opacity-45")}>
                      <div className="flex items-center gap-2">
                        <span className={cx("font-mono text-xs font-semibold size-6 rounded-full grid place-items-center shrink-0",
                          i === 0 ? "bg-accent text-on-accent" : mode === "hybrid" ? "bg-on-contrast/10" : "bg-sunken")}>{i + 1}</span>
                        <span className="text-sm font-medium truncate">{h.filename}</span>
                        <span className={cx("ml-auto font-mono text-[11px] shrink-0", mode === "hybrid" ? "text-contrast-muted" : "text-faint")}>p.{h.page}</span>
                      </div>
                      <div className="mt-3 flex items-center gap-2">
                        <div className={cx("h-1.5 flex-1 rounded-full overflow-hidden", mode === "hybrid" ? "bg-on-contrast/10" : "bg-sunken")}>
                          <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${(h.score / max) * 100}%` }} />
                        </div>
                        <span className="font-mono text-[11px] tabular w-14 text-right">{h.score.toFixed(mode === "hybrid" ? 4 : 3)}</span>
                      </div>
                      {mode === "hybrid" && (
                        <p className="mt-2 font-mono text-[11px] text-contrast-muted">
                          semantic #{h.ranks.vector ?? "–"} · keyword #{h.ranks.bm25 ?? "–"}
                        </p>
                      )}
                      <p className={cx("mt-2.5 text-[13px] leading-relaxed line-clamp-4", mode === "hybrid" ? "text-on-contrast/80" : "text-muted")}>
                        <Highlight text={h.text} query={ran ?? ""} />
                      </p>
                    </li>
                  ))}
                </ol>
              </Card>
            );
          })}
        </div>
      )}

      <p className="text-xs text-faint flex items-start gap-2 px-1">
        <Info className="size-3.5 mt-0.5 shrink-0" />
        Scores are not comparable across columns: cosine similarity, BM25 and RRF use different scales. That is why hybrid
        fuses ranks, not scores.
      </p>
    </div>
  );
}
