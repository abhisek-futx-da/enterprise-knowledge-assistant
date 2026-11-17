import type {
  ChatResult, Conversation, Doc, SearchHit, SearchMode, StoredMessage, StreamEvent, User, WorkspaceStats,
} from "./types";

const BASE = "/api";
const TOKEN_KEY = "eka-token";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

let onUnauthorized: () => void = () => {};
export const setUnauthorizedHandler = (fn: () => void) => (onUnauthorized = fn);

export const tokenStore = {
  get(): string | null {
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set(token: string | null) {
    try { token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY); } catch { /* private mode */ }
  },
};

function detail(body: unknown, fallback: string): string {
  const d = (body as { detail?: unknown })?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg).replace(/^Value error, /, "");
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = tokenStore.get();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let res: Response;
  try {
    res = await fetch(BASE + path, { ...init, headers });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check that the API is running.");
  }
  if (res.status === 401 && token) onUnauthorized();
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, detail(body, `Request failed (${res.status})`));
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const json = (body: unknown): RequestInit => ({
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST", body: new URLSearchParams({ username: email, password }),
    }),
  register: (email: string, password: string) => request<User>("/auth/register", json({ email, password })),
  me: () => request<User>("/auth/me"),
  stats: () => request<WorkspaceStats>("/stats"),
  documents: () => request<Doc[]>("/documents"),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Doc>("/documents", { method: "POST", body: form });
  },
  deleteDocument: (id: string) => request<void>(`/documents/${id}`, { method: "DELETE" }),
  search: (query: string, mode: SearchMode, top_k = 5) => request<SearchHit[]>("/search", json({ query, mode, top_k })),
  conversations: () => request<Conversation[]>("/conversations"),
  messages: (id: string) => request<StoredMessage[]>(`/conversations/${id}/messages`),
  chat: (question: string, conversation_id: string | null) =>
    request<ChatResult>("/chat", json({ question, conversation_id })),
};

/** POST /chat/stream and hand each Server-Sent Event to `onEvent` as it arrives. */
export async function streamChat(
  question: string, conversationId: string | null, onEvent: (e: StreamEvent) => void, signal?: AbortSignal,
): Promise<void> {
  const token = tokenStore.get();
  let res: Response;
  try {
    res = await fetch(`${BASE}/chat/stream`, {
      ...json({ question, conversation_id: conversationId }),
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "Can't reach the server. Check that the API is running.");
  }
  if (res.status === 401) onUnauthorized();
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, detail(body, `Request failed (${res.status})`));
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const data = frame.split("\n").filter((l) => l.startsWith("data: ")).map((l) => l.slice(6)).join("");
      if (data) onEvent(JSON.parse(data) as StreamEvent);
    }
  }
}
