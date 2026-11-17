import { UploadCloud } from "lucide-react";
import { useRef, useState, type ReactNode } from "react";
import { api, ApiError } from "../lib/api";
import { useApp } from "../lib/app-state";
import type { Doc } from "../lib/types";
import { cx } from "./ui";

export const ACCEPT = [".pdf", ".docx", ".txt", ".md"];
export const MAX_MB = 10;

/** Validates on the client first (instant feedback), then uploads one file at a time. */
export function useUploader(onUploaded?: (doc: Doc) => void) {
  const { toast } = useApp();
  const [busy, setBusy] = useState<string[]>([]);

  async function upload(files: File[]) {
    for (const file of files) {
      const ext = "." + (file.name.split(".").pop() ?? "").toLowerCase();
      if (!ACCEPT.includes(ext)) {
        toast(`${file.name}: only PDF, DOCX, TXT and MD files are supported.`, "error");
        continue;
      }
      if (file.size > MAX_MB * 1024 * 1024) {
        toast(`${file.name} is larger than ${MAX_MB} MB.`, "error");
        continue;
      }
      setBusy((b) => [...b, file.name]);
      try {
        onUploaded?.(await api.upload(file));
      } catch (e) {
        toast(`${file.name}: ${e instanceof ApiError ? e.message : "upload failed"}`, "error");
      } finally {
        setBusy((b) => b.filter((n) => n !== file.name));
      }
    }
  }
  return { upload, busy };
}

export function Dropzone({ onFiles, children, className, activeClassName }: {
  onFiles: (files: File[]) => void; children: ReactNode; className?: string; activeClassName?: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Upload documents: drop files here or press Enter to browse"
      onClick={() => input.current?.click()}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), input.current?.click())}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        onFiles([...e.dataTransfer.files]);
      }}
      className={cx("cursor-pointer transition", className, over && activeClassName)}
    >
      <input ref={input} type="file" multiple hidden accept={ACCEPT.join(",")}
        onChange={(e) => { onFiles([...(e.target.files ?? [])]); e.target.value = ""; }} />
      {children}
    </div>
  );
}

export function DropHint({ busy }: { busy: string[] }) {
  return (
    <>
      <UploadCloud className={cx("size-6", busy.length > 0 && "animate-bounce")} />
      <p className="font-semibold text-lg tracking-tight mt-3">
        {busy.length ? `Uploading ${busy[0]}${busy.length > 1 ? ` +${busy.length - 1}` : ""}…` : "Drop files to add knowledge"}
      </p>
      <p className="text-sm opacity-70 mt-1">or click to browse</p>
      <p className="font-mono text-[10.5px] tracking-[0.12em] uppercase opacity-60 mt-4">
        PDF · DOCX · TXT · MD — up to {MAX_MB} MB
      </p>
    </>
  );
}
