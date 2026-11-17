import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setUnauthorizedHandler, tokenStore } from "./api";
import type { User } from "./types";

export type Route =
  | { name: "home" }
  | { name: "ask"; conversationId?: string; prefill?: string }
  | { name: "library" }
  | { name: "search"; query?: string };

function parseHash(): Route {
  const [path, query = ""] = window.location.hash.replace(/^#\/?/, "").split("?");
  const params = new URLSearchParams(query);
  const [head, id] = path.split("/");
  if (head === "ask") return { name: "ask", conversationId: id || undefined, prefill: params.get("q") ?? undefined };
  if (head === "library") return { name: "library" };
  if (head === "search") return { name: "search", query: params.get("q") ?? undefined };
  return { name: "home" };
}

export function routeHref(r: Route): string {
  switch (r.name) {
    case "home": return "#/";
    case "library": return "#/library";
    case "search": return r.query ? `#/search?q=${encodeURIComponent(r.query)}` : "#/search";
    case "ask": {
      const base = r.conversationId ? `#/ask/${r.conversationId}` : "#/ask";
      return r.prefill ? `${base}?q=${encodeURIComponent(r.prefill)}` : base;
    }
  }
}

interface Toast { id: number; kind: "info" | "error" | "success"; text: string }

interface AppState {
  user: User | null;
  booting: boolean;
  route: Route;
  navigate: (r: Route, opts?: { replace?: boolean }) => void;
  signIn: (token: string) => Promise<void>;
  signOut: () => void;
  toasts: Toast[];
  toast: (text: string, kind?: Toast["kind"]) => void;
  dark: boolean;
  toggleTheme: () => void;
}

const Ctx = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(true);
  const [route, setRoute] = useState<Route>(parseHash);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));

  const toast = useCallback((text: string, kind: Toast["kind"] = "info") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-2), { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200);
  }, []);

  const signOut = useCallback(() => {
    tokenStore.set(null);
    setUser(null);
  }, []);

  const signIn = useCallback(async (token: string) => {
    tokenStore.set(token);
    setUser(await api.me());
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      signOut();
      toast("Your session expired. Sign in again.", "info");
    });
    if (!tokenStore.get()) {
      setBooting(false);
      return;
    }
    api.me().then(setUser).catch(() => tokenStore.set(null)).finally(() => setBooting(false));
  }, [signOut, toast]);

  useEffect(() => {
    const onHash = () => setRoute(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const navigate = useCallback((r: Route, opts?: { replace?: boolean }) => {
    const href = routeHref(r);
    if (opts?.replace) history.replaceState(null, "", href);
    else if (window.location.hash !== href) history.pushState(null, "", href);
    setRoute(r);
  }, []);

  const toggleTheme = useCallback(() => {
    setDark((d) => {
      const next = !d;
      document.documentElement.classList.toggle("dark", next);
      try { localStorage.setItem("eka-theme", next ? "dark" : "light"); } catch { /* ignore */ }
      return next;
    });
  }, []);

  const value = useMemo(
    () => ({ user, booting, route, navigate, signIn, signOut, toasts, toast, dark, toggleTheme }),
    [user, booting, route, navigate, signIn, signOut, toasts, toast, dark, toggleTheme],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useApp outside AppProvider");
  return ctx;
}
