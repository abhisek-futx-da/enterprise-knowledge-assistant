import { CheckCircle2, FileStack, Home, Info, LogOut, MessageSquareText, Moon, ScanSearch, Sun, XCircle } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { routeHref, useApp, type Route } from "../lib/app-state";
import { Kbd, Logo, cx } from "./ui";

const NAV: { route: Route; label: string; icon: typeof Home }[] = [
  { route: { name: "home" }, label: "Home", icon: Home },
  { route: { name: "ask" }, label: "Ask", icon: MessageSquareText },
  { route: { name: "library" }, label: "Library", icon: FileStack },
  { route: { name: "search" }, label: "Search lab", icon: ScanSearch },
];

export function Shell({ children }: { children: ReactNode }) {
  const { route, navigate, user, signOut, dark, toggleTheme } = useApp();
  const [menu, setMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        navigate({ name: "ask" });
        setTimeout(() => document.getElementById("composer")?.focus(), 30);
      }
    };
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenu(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClick);
    };
  }, [navigate]);

  const go = (r: Route) => (e: React.MouseEvent) => {
    e.preventDefault();
    navigate(r);
  };

  return (
    <div className="min-h-full flex flex-col">
      <header className="sticky top-0 z-30 bg-bg/80 backdrop-blur-xl">
        <div className="mx-auto max-w-[1400px] px-4 sm:px-6 h-16 flex items-center gap-4">
          <a href="#/" onClick={go({ name: "home" })} aria-label="Home"><Logo /></a>
          <nav className="hidden md:flex mx-auto items-center gap-1 rounded-full bg-surface border border-line p-1 shadow-card" aria-label="Main">
            {NAV.map(({ route: r, label, icon: Icon }) => {
              const active = route.name === r.name;
              return (
                <a key={label} href={routeHref(r)} onClick={go(r)} aria-current={active ? "page" : undefined}
                  className={cx("inline-flex items-center gap-2 rounded-full px-4 h-9 text-sm font-medium transition",
                    active ? "bg-ink text-bg" : "text-muted hover:text-ink hover:bg-sunken")}>
                  <Icon className="size-4" />{label}
                </a>
              );
            })}
          </nav>
          <div className="ml-auto md:ml-0 flex items-center gap-2">
            <button onClick={() => navigate({ name: "ask" })}
              className="hidden lg:inline-flex items-center gap-2 h-9 rounded-full border border-line bg-surface px-3 text-sm text-muted hover:text-ink transition">
              Ask anything <Kbd>⌘K</Kbd>
            </button>
            <button onClick={toggleTheme} aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
              className="size-9 rounded-full grid place-items-center border border-line bg-surface hover:bg-surface-2 transition">
              {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </button>
            <div className="relative" ref={menuRef}>
              <button onClick={() => setMenu((m) => !m)} aria-haspopup="menu" aria-expanded={menu}
                className="size-9 rounded-full bg-accent text-on-accent font-semibold text-sm grid place-items-center uppercase">
                {user?.email[0]}
              </button>
              {menu && (
                <div role="menu" className="rise absolute right-0 mt-2 w-64 rounded-2xl border border-line bg-surface shadow-card p-2">
                  <div className="px-3 py-2">
                    <p className="text-sm font-medium truncate">{user?.email}</p>
                    <p className="label mt-1">{user?.role}</p>
                  </div>
                  <button role="menuitem" onClick={signOut}
                    className="w-full flex items-center gap-2 rounded-xl px-3 py-2 text-sm hover:bg-sunken text-left">
                    <LogOut className="size-4" /> Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-[1400px] px-4 sm:px-6 pb-28 md:pb-10">{children}</main>

      <nav className="md:hidden fixed bottom-3 inset-x-3 z-30 rounded-full bg-contrast text-on-contrast p-1.5 flex justify-between shadow-card" aria-label="Main">
        {NAV.map(({ route: r, label, icon: Icon }) => {
          const active = route.name === r.name;
          return (
            <a key={label} href={routeHref(r)} onClick={go(r)} aria-current={active ? "page" : undefined}
              className={cx("flex-1 flex flex-col items-center gap-0.5 rounded-full py-1.5 text-[10px] font-medium transition",
                active ? "bg-accent text-on-accent" : "text-contrast-muted")}>
              <Icon className="size-[18px]" />{label}
            </a>
          );
        })}
      </nav>
      <Toasts />
    </div>
  );
}

function Toasts() {
  const { toasts } = useApp();
  const icon = { info: Info, error: XCircle, success: CheckCircle2 };
  return (
    <div className="fixed z-50 bottom-24 md:bottom-6 left-1/2 -translate-x-1/2 flex flex-col gap-2 items-center w-[min(92vw,420px)]" aria-live="polite">
      {toasts.map((t) => {
        const Icon = icon[t.kind];
        return (
          <div key={t.id} className="rise w-full flex items-start gap-3 rounded-2xl bg-contrast text-on-contrast px-4 py-3 shadow-card text-sm">
            <Icon className={cx("size-4 mt-0.5 shrink-0", t.kind === "error" && "text-bad", t.kind === "success" && "text-accent")} />
            {t.text}
          </div>
        );
      })}
    </div>
  );
}
