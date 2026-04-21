import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { EmptyState, ErrorState } from "@/components/primitives/States";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/formatters";
import type { BudgetItem } from "@/lib/types";

import BudgetManager from "./BudgetManager";

function BudgetGauge({ usedPct, status }: { usedPct: number; status: string }) {
  const colorMap: Record<string, string> = {
    over: "var(--status-critical)",
    warning: "var(--status-warning)",
    ok: "var(--status-healthy)",
    healthy: "var(--status-healthy)",
  };
  const color = colorMap[status] ?? "var(--text-tertiary)";
  const w = Math.min(usedPct, 100);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
      <div
        style={{
          flex: 1,
          height: "6px",
          background: "var(--bg-warm-subtle)",
          borderRadius: "var(--radius-full)",
          overflow: "hidden",
          border: "1px solid var(--border)",
        }}
      >
        <div
          style={{
            width: `${w}%`,
            height: "100%",
            background: color,
            borderRadius: "var(--radius-full)",
            transition: "width 0.4s ease",
          }}
        />
      </div>
      <span
        className="font-mono"
        style={{ fontSize: "11px", color: "var(--text-secondary)", width: "40px", textAlign: "right" }}
      >
        {usedPct > 0 ? `${usedPct.toFixed(0)}%` : "—"}
      </span>
    </div>
  );
}

export default async function BudgetPage() {
  let data, filters;
  try {
    [data, filters] = await Promise.all([api.budget(), api.filters()]);
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const overCount = data.items.filter((i) => i.status === "over").length;
  const hasBudget = data.total_budget > 0;

  return (
    <div style={{ maxWidth: "1100px" }}>
      <PageHeader
        title="Budget"
        description={
          hasBudget
            ? `Total budget ${formatCurrency(data.total_budget)}`
            : "Add budget entries below or run the budget_alerts asset in Dagster."
        }
      />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "16px",
          marginBottom: "32px",
        }}
      >
        <MetricCard
          label="Total Budget"
          value={hasBudget ? formatCurrency(data.total_budget, { compact: true }) : "—"}
        />
        <MetricCard
          label="Actual Spend"
          value={formatCurrency(data.total_actual, { compact: true })}
        />
        <MetricCard
          label="Over Budget"
          value={String(overCount)}
          valueColor={overCount > 0 ? "var(--status-critical)" : "var(--status-healthy)"}
        />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
        <Card>
          <CardHeader>Budget Status by Team</CardHeader>
          {data.items.length === 0 ? (
            <EmptyState
              title="No budget status yet"
              description="Add budget entries below, then run budget_alerts in Dagster to compute status."
            />
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Team", "Env", "Budget", "Actual", "Usage", "Status"].map((h, idx, arr) => (
                    <th
                      key={h}
                      style={{
                        textAlign: ["Budget", "Actual"].includes(h) ? "right" : ["Env", "Status"].includes(h) ? "center" : "left",
                        fontSize: "10px",
                        fontWeight: 600,
                        fontFamily: "Inter, sans-serif",
                        color: "var(--text-tertiary)",
                        letterSpacing: "0.07em",
                        textTransform: "uppercase",
                        padding: idx === 0
                          ? "0 8px 12px 0"
                          : idx === arr.length - 1
                          ? "0 0 12px 8px"
                          : "0 8px 12px 8px",
                        borderBottom: "1px solid var(--border)",
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.items.map((item: BudgetItem, i: number) => (
                  <tr
                    key={i}
                    style={{
                      borderBottom: i < data.items.length - 1 ? "1px solid var(--border)" : "none",
                    }}
                  >
                    <td style={{ padding: "12px 0", fontSize: "13px", fontWeight: 500, color: "var(--text-primary)" }}>
                      {item.team}
                    </td>
                    <td style={{ padding: "12px 8px", textAlign: "center" }}>
                      <SeverityBadge severity={item.env} />
                    </td>
                    <td style={{ padding: "12px 8px", textAlign: "right" }}>
                      <span className="font-mono" style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                        {item.budget_amount > 0 ? (
                          <>
                            <span className="currency-symbol">$</span>
                            {Math.round(item.budget_amount).toLocaleString("en-US")}
                          </>
                        ) : "—"}
                      </span>
                    </td>
                    <td style={{ padding: "12px 8px", textAlign: "right" }}>
                      <span className="font-mono" style={{ fontSize: "12px" }}>
                        <span className="currency-symbol">$</span>
                        {Math.round(item.actual_cost).toLocaleString("en-US")}
                      </span>
                    </td>
                    <td style={{ padding: "12px 8px", minWidth: "160px" }}>
                      {item.budget_amount > 0 ? (
                        <BudgetGauge usedPct={item.used_pct} status={item.status} />
                      ) : (
                        <span style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>No budget set</span>
                      )}
                    </td>
                    <td style={{ padding: "12px 0 12px 8px", textAlign: "center" }}>
                      <SeverityBadge severity={item.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <BudgetManager filters={filters} />
      </div>
    </div>
  );
}
