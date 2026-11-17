import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Shell } from "./components/Shell";
import { Logo } from "./components/ui";
import "./index.css";
import { AppProvider, useApp } from "./lib/app-state";
import { AskPage } from "./pages/AskPage";
import { AuthPage } from "./pages/AuthPage";
import { HomePage } from "./pages/HomePage";
import { LibraryPage } from "./pages/LibraryPage";
import { SearchPage } from "./pages/SearchPage";

function App() {
  const { user, booting, route } = useApp();
  if (booting) {
    return <div className="h-full grid place-items-center"><div className="pulse-dot"><Logo compact /></div></div>;
  }
  if (!user) return <AuthPage />;
  return (
    <Shell>
      {route.name === "home" && <HomePage />}
      {route.name === "ask" && <AskPage conversationId={route.conversationId} prefill={route.prefill} />}
      {route.name === "library" && <LibraryPage />}
      {route.name === "search" && <SearchPage initial={route.query} />}
    </Shell>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppProvider><App /></AppProvider>
  </StrictMode>,
);
