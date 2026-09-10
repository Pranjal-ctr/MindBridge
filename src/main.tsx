
  import { createRoot } from "react-dom/client";
  import App from "./app/App.tsx";
  import { initMonitoring } from "./lib/monitoring";
  import "./styles/index.css";

  // Before render, so an error thrown during the first paint is still caught.
  // No-ops unless VITE_SENTRY_DSN was set at build time.
  initMonitoring();

  createRoot(document.getElementById("root")!).render(<App />);
  