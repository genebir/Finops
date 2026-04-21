"use client";

import { usePathname } from "next/navigation";

const LABELS: Record<string, string> = {
  "/overview":        "Overview",
  "/cost-explorer":   "Costs",
  "/anomalies":       "Anomalies",
  "/forecast":        "Forecast",
  "/budget":          "Budget",
  "/chargeback":      "Chargeback",
  "/recommendations": "Recommendations",
  "/settings":        "Settings",
};

export default function TopBar() {
  const pathname = usePathname();
  const base = "/" + (pathname.split("/")[1] ?? "");
  const label = LABELS[base] ?? "";

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        height: "56px",
        backgroundColor: "var(--bg-warm)",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        padding: "0 40px",
        zIndex: 30,
        gap: "8px",
      }}
    >
      <span
        style={{
          fontSize: "11px",
          color: "var(--text-tertiary)",
          fontFamily: "Inter, sans-serif",
        }}
      >
        FinOps
      </span>
      <span style={{ fontSize: "11px", color: "var(--border-strong)" }}>/</span>
      <span
        style={{
          fontSize: "13px",
          fontWeight: 500,
          color: "var(--text-secondary)",
          fontFamily: "Inter, sans-serif",
        }}
      >
        {label}
      </span>
    </header>
  );
}
