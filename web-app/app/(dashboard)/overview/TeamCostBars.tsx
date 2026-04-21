"use client";

import type { TeamCost } from "@/lib/types";

const PALETTE = [
  "var(--provider-aws)",
  "var(--provider-gcp)",
  "var(--provider-azure)",
  "var(--status-healthy)",
  "var(--status-warning)",
  "#5C8A7A",
  "#A89F94",
];

export default function TeamCostBars({ items }: { items: TeamCost[] }) {
  const max = Math.max(...items.map((i) => i.cost));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
      {items.map((item, idx) => (
        <div key={item.team} style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span
            style={{
              width: "72px",
              flexShrink: 0,
              fontSize: "13px",
              fontWeight: 500,
              color: "var(--text-primary)",
              fontFamily: "Inter, sans-serif",
            }}
          >
            {item.team}
          </span>
          <div
            style={{
              flex: 1,
              height: "8px",
              background: "var(--bg-warm-subtle)",
              borderRadius: "var(--radius-full)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${(item.cost / max) * 100}%`,
                height: "100%",
                background: PALETTE[idx % PALETTE.length],
                borderRadius: "var(--radius-full)",
                transition: "width 0.4s ease",
              }}
            />
          </div>
          <span
            className="font-mono"
            style={{
              fontSize: "12px",
              color: "var(--text-secondary)",
              width: "64px",
              textAlign: "right",
            }}
          >
            <span className="currency-symbol">$</span>
            {(item.cost / 1000).toFixed(1)}k
          </span>
          <span
            style={{
              fontSize: "11px",
              color: "var(--text-tertiary)",
              width: "36px",
              textAlign: "right",
              fontFamily: "Inter, sans-serif",
            }}
          >
            {item.pct}%
          </span>
        </div>
      ))}
    </div>
  );
}
