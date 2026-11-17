// Runs before first paint so the saved or system theme never flashes the wrong colours.
try {
  const t = localStorage.getItem("eka-theme");
  const dark = t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.classList.toggle("dark", dark);
} catch {}
