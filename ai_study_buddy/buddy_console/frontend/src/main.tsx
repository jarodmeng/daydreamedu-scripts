import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import InventoryApp from "./InventoryApp";
import PdfApp from "./PdfApp";
import "./styles.css";

function resolveView(): "inventory" | "pdf" | "review" {
  const params = new URLSearchParams(window.location.search);
  const path = window.location.pathname;
  if (path === "/pdf") {
    return "pdf";
  }
  if (path === "/review" || params.has("attempt_id")) {
    return "review";
  }
  return "inventory";
}

const view = resolveView();
document.body.setAttribute("data-buddy-console-view", view);

function resolveRootComponent(): React.ReactNode {
  if (view === "pdf") {
    return <PdfApp />;
  }
  if (view === "review") {
    return <App />;
  }
  return <InventoryApp />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {resolveRootComponent()}
  </React.StrictMode>,
);
