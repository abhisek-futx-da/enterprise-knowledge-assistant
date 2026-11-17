import { ArrowRight, Eye, EyeOff, FileText, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { AgentSteps } from "../components/AgentSteps";
import { Button, Logo, cx } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useApp } from "../lib/app-state";

const DEMO = { email: "demo@example.com", password: "demo-password-1" };
const DEMO_STEPS = [
  { node: "route", trace: [] }, { node: "retrieve", trace: [] }, { node: "grade", trace: [] },
  { node: "generate", trace: [] }, { node: "verify", trace: [] },
];

export function AuthPage() {
  const { signIn, toast } = useApp();
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shakeKey, setShakeKey] = useState(0);

  async function submit(e?: FormEvent, creds = { email, password }) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "register") await api.register(creds.email, creds.password);
      const { access_token } = await api.login(creds.email, creds.password);
      await signIn(access_token);
      if (mode === "register") toast("Account created. Upload a document to get started.", "success");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Something went wrong";
      setError(err instanceof ApiError && err.status === 401
        ? "That email and password don't match an account."
        : msg);
      setShakeKey((k) => k + 1);
    } finally {
      setBusy(false);
    }
  }

  function useDemo() {
    setMode("signin");
    setEmail(DEMO.email);
    setPassword(DEMO.password);
    void submit(undefined, DEMO);
  }

  return (
    <div className="min-h-full grid lg:grid-cols-[1.05fr_1fr] p-3 gap-3">
      <Showcase />
      <div className="flex flex-col px-3 sm:px-10 py-8">
        <div className="lg:hidden"><Logo /></div>
        <div className="my-auto w-full max-w-[400px] mx-auto pt-10 lg:pt-0">
          <p className="label">{mode === "signin" ? "Welcome back" : "Get started"}</p>
          <h1 className="text-4xl font-semibold tracking-[-0.035em] mt-2 leading-[1.05]">
            {mode === "signin" ? "Sign in to your knowledge base" : "Create your private workspace"}
          </h1>
          <p className="text-muted mt-3">
            {mode === "signin"
              ? "Ask questions across your documents and get answers you can check."
              : "Your documents stay private to your account. Nobody else can search them."}
          </p>

          <div role="tablist" className="mt-8 grid grid-cols-2 rounded-full bg-sunken p-1 text-sm font-medium">
            {(["signin", "register"] as const).map((m) => (
              <button key={m} role="tab" aria-selected={mode === m} onClick={() => { setMode(m); setError(null); }}
                className={cx("h-9 rounded-full transition", mode === m ? "bg-surface shadow-card" : "text-muted hover:text-ink")}>
                {m === "signin" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
            <Field label="Work email">
              <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com" className="input" />
            </Field>
            <Field label="Password" hint={mode === "register" ? "At least 8 characters" : undefined}>
              <div className="relative">
                <input type={show ? "text" : "password"} required minLength={mode === "register" ? 8 : undefined}
                  autoComplete={mode === "signin" ? "current-password" : "new-password"}
                  value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" className="input pr-11" />
                <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide password" : "Show password"}
                  className="absolute right-2 top-1/2 -translate-y-1/2 size-8 grid place-items-center rounded-full text-muted hover:text-ink">
                  {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </Field>
            {error && (
              <p key={shakeKey} role="alert" className="shake text-sm text-bad bg-bad/10 rounded-2xl px-4 py-3">{error}</p>
            )}
            <Button type="submit" loading={busy} className="w-full h-12 text-[15px]"
              disabled={!email || password.length < (mode === "register" ? 8 : 1)}>
              {mode === "signin" ? "Sign in" : "Create account"} <ArrowRight className="size-4" />
            </Button>
          </form>

          <div className="flex items-center gap-3 my-6 text-faint text-xs">
            <span className="h-px flex-1 bg-line" />or<span className="h-px flex-1 bg-line" />
          </div>
          <Button variant="outline" className="w-full h-12" onClick={useDemo} disabled={busy}>
            <Sparkles className="size-4" /> Explore the demo workspace
          </Button>
          <p className="text-xs text-faint text-center mt-3">Four sample company documents, already indexed.</p>
        </div>
      </div>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="flex justify-between text-sm font-medium mb-1.5">
        {label}{hint && <span className="text-faint font-normal">{hint}</span>}
      </span>
      {children}
    </label>
  );
}

/** Left panel: a live-looking preview of a verified answer, so the product explains itself before sign-in. */
function Showcase() {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setShown((n) => (n >= DEMO_STEPS.length + 4 ? 0 : n + 1)), 900);
    return () => clearInterval(t);
  }, []);
  const steps = DEMO_STEPS.slice(0, Math.min(shown, DEMO_STEPS.length));
  const done = shown > DEMO_STEPS.length;

  return (
    <aside className="hidden lg:flex flex-col rounded-[2rem] bg-contrast text-on-contrast p-10 relative overflow-hidden">
      <div className="absolute -right-24 -top-24 size-80 rounded-full bg-accent/25 blur-3xl" aria-hidden />
      <span className="inline-flex items-center gap-2.5">
        <svg viewBox="0 0 32 32" className="size-8" aria-hidden>
          <rect width="32" height="32" rx="9" fill="var(--accent)" />
          <path d="M10 9v14M10 16l7-7M13 13l7 10" stroke="#121210" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" fill="none" />
          <circle cx="22.5" cy="10" r="2" fill="#121210" />
        </svg>
        <span className="text-[15px] font-semibold tracking-tight">Knowledge<span className="text-contrast-muted">.ai</span></span>
      </span>

      <h2 className="mt-auto text-[56px] leading-[0.98] font-semibold tracking-[-0.045em] max-w-[11ch]">
        Answers you can{" "}
        <span className="relative whitespace-nowrap">
          <span className="absolute inset-x-[-0.12em] bottom-[0.06em] top-[0.18em] -z-0 rounded-[0.3em] bg-accent -rotate-1" aria-hidden />
          <span className="relative text-on-accent">check.</span>
        </span>
      </h2>
      <p className="mt-5 text-contrast-muted max-w-md text-[15px] leading-relaxed">
        Every answer cites the exact document and page. If your files don't say it, the assistant tells you so
        instead of guessing.
      </p>

      <div className="mt-10 rounded-3xl bg-white/[0.06] border border-white/10 p-5 max-w-lg backdrop-blur [.dark_&]:bg-black/[0.05] [.dark_&]:border-black/10">
        <div className="flex justify-end">
          <p className="rounded-2xl rounded-br-md bg-accent text-on-accent px-4 py-2 text-sm font-medium">
            What does error code E-417 mean?
          </p>
        </div>
        <div className="mt-4 grid grid-cols-[1fr_auto] gap-4 items-start min-h-[148px]">
          <div className="[&_.text-muted]:text-contrast-muted [&_.bg-accent]:bg-accent">
            <AgentSteps steps={steps} running={!done && shown > 0} compact />
          </div>
          {done && (
            <div className="rise w-56 rounded-2xl bg-surface text-ink p-4 text-sm leading-relaxed">
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-good">
                <ShieldCheck className="size-3.5" /> Verified
              </span>
              <p className="mt-1.5">E-417 means a thermal sensor fault.<sup className="ml-0.5 rounded bg-accent text-on-accent px-1 text-[10px] font-semibold">1</sup></p>
              <p className="mt-2 inline-flex items-center gap-1.5 text-[11px] text-muted">
                <FileText className="size-3" /> product_faq.txt · p.1
              </p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
