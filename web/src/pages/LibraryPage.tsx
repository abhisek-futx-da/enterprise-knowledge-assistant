import { AlertTriangle, FileText, Loader2, Search, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Dropzone, DropHint, useUploader } from "../components/Dropzone";
import { Button, Card, EmptyState, Pill, Skeleton, cx } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useApp } from "../lib/app-state";
import { fileKind, relativeTime } from "../lib/format";
import type { Doc } from "../lib/types";

const STATUS_TONE = { ready: "good", pending: "warn", failed: "bad" } as const;
const STATUS_LABEL = { ready: "Ready", pending: "Indexing", failed: "Failed" } as const;

export function LibraryPage() {
  const { toast, navigate } = useApp();
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [filter, setFilter] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const refresh = useCallback(() => api.documents().then(setDocs).catch(() => setDocs((d) => d ?? [])), []);
  const { upload, busy } = useUploader((doc) => setDocs((d) => [doc, ...(d ?? [])]));

  useEffect(() => { refresh(); }, [refresh]);

  const pending = docs?.some((d) => d.status === "pending");
  useEffect(() => {
    if (!pending) return;
    const t = setInterval(refresh, 1500);
    return () => clearInterval(t);
  }, [pending, refresh]);

  const shown = useMemo(
    () => (docs ?? []).filter((d) => d.filename.toLowerCase().includes(filter.toLowerCase())),
    [docs, filter],
  );
  const totals = useMemo(() => ({
    pages: (docs ?? []).reduce((s, d) => s + d.num_pages, 0),
    chunks: (docs ?? []).reduce((s, d) => s + d.num_chunks, 0),
  }), [docs]);

  async function remove(doc: Doc) {
    setDeleting(doc.id);
    try {
      await api.deleteDocument(doc.id);
      setDocs((d) => d?.filter((x) => x.id !== doc.id) ?? null);
      toast(`Removed ${doc.filename}. It will no longer be searched.`, "success");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Couldn't delete the document", "error");
    } finally {
      setDeleting(null);
      setConfirming(null);
    }
  }

  return (
    <div className="pt-4 sm:pt-8 space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-4 px-1">
        <div>
          <p className="label">Library</p>
          <h1 className="text-4xl sm:text-5xl font-semibold tracking-[-0.04em] mt-2 leading-none">Your documents</h1>
        </div>
        <div className="flex gap-6 text-sm">
          {[["Documents", docs?.length], ["Pages", totals.pages], ["Passages", totals.chunks]].map(([l, v]) => (
            <div key={l as string}>
              <p className="text-2xl font-semibold tabular tracking-tight">{docs ? (v as number) : "—"}</p>
              <p className="text-muted text-xs">{l}</p>
            </div>
          ))}
        </div>
      </header>

      <Dropzone onFiles={upload}
        className="rounded-card border-2 border-dashed border-line bg-surface hover:border-ink hover:bg-surface-2 p-10 flex flex-col items-center text-center"
        activeClassName="!border-ink !bg-accent text-on-accent">
        <DropHint busy={busy} />
      </Dropzone>

      <Card className="!p-0 overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 p-4 sm:px-6 border-b border-line">
          <p className="font-semibold tracking-tight">All documents</p>
          {pending && <Pill tone="warn"><Loader2 className="size-3 animate-spin" />Indexing in progress</Pill>}
          <div className="relative ml-auto w-full sm:w-72">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 size-4 text-faint" />
            <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter by name" aria-label="Filter documents"
              className="w-full h-10 rounded-full bg-sunken pl-10 pr-4 text-sm placeholder:text-faint focus:outline-none focus:ring-4 focus:ring-accent/40" />
          </div>
        </div>

        {docs === null ? (
          <div className="p-6 space-y-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div>
        ) : docs.length === 0 ? (
          <EmptyState icon={<FileText className="size-6" />} title="No documents yet"
            body="Upload policies, manuals, FAQs or reports. They are split into passages, indexed for meaning and keywords, and only you can search them." />
        ) : shown.length === 0 ? (
          <EmptyState icon={<Search className="size-6" />} title="No matches" body={`No document names contain "${filter}".`} />
        ) : (
          <ul className="divide-y divide-line">
            {shown.map((d) => (
              <li key={d.id} className="rise flex flex-wrap sm:flex-nowrap items-center gap-4 px-4 sm:px-6 py-4 hover:bg-surface-2 transition">
                <span className="size-11 rounded-2xl bg-sunken grid place-items-center font-mono text-[10px] font-semibold tracking-wider text-muted shrink-0">
                  {fileKind(d.filename)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-medium truncate">{d.filename}</p>
                  <p className="text-xs text-faint mt-0.5">
                    Uploaded {relativeTime(d.created_at)}
                    {d.status === "ready" && <> · {d.num_pages} page{d.num_pages === 1 ? "" : "s"} · {d.num_chunks} passages</>}
                  </p>
                  {d.error && (
                    <p className="text-xs text-bad mt-1 inline-flex items-center gap-1"><AlertTriangle className="size-3" />{d.error}</p>
                  )}
                </div>
                <Pill tone={STATUS_TONE[d.status]}>
                  {d.status === "pending" ? <Loader2 className="size-3 animate-spin" /> : <span className="size-1.5 rounded-full bg-current" />}
                  {STATUS_LABEL[d.status]}
                </Pill>
                <div className="flex items-center gap-1 ml-auto sm:ml-0">
                  {d.status === "ready" && confirming !== d.id && (
                    <Button variant="ghost" className="h-9 text-xs"
                      onClick={() => navigate({ name: "ask", prefill: `Summarise the key points of ${d.filename}` })}>
                      Ask about it
                    </Button>
                  )}
                  {confirming === d.id ? (
                    <span className="flex items-center gap-1">
                      <span className="text-xs text-muted mr-1">Delete permanently?</span>
                      <Button variant="danger" className="h-9 text-xs" loading={deleting === d.id} onClick={() => remove(d)}>Delete</Button>
                      <Button variant="ghost" className="h-9 text-xs" onClick={() => setConfirming(null)}>Cancel</Button>
                    </span>
                  ) : (
                    <button onClick={() => setConfirming(d.id)} aria-label={`Delete ${d.filename}`}
                      className={cx("size-9 rounded-full grid place-items-center text-faint hover:text-bad hover:bg-bad/10 transition")}>
                      <Trash2 className="size-4" />
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
