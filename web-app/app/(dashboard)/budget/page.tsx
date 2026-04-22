import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { EmptyState, ErrorState } from "@/components/primitives/States";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/formatters";
import type { BudgetItem } from "@/lib/types";
import { getT } from "@/lib/i18n/server";

import BudgetManager from "./BudgetManager";

export const dynamic = "force-dynamic";

export const metadata = { title: "Budget — FinOps" };

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
  const t = getT();
  let data, filters;
  try {
    [data, filters] = await Promise.all([api.budget(), api.filters()]);
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const overCount = data.items.filter((i) => i.status === "over").length;
  const hasBudget = data.total_budget > 0;

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={t("page.budget.title")}
        description={
          hasBudget
            ? `${t("label.total_budget")} ${formatCurrency(data.total_budget)}`
            : t("empty.add_budget_hint")
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
          label={t("label.total_budget")}
          value={hasBudget ? formatCurrency(data.total_budget, { compact: true }) : "—"}
        />
        <MetricCard
          label={t("label.actual_spend")}
          value={formatCurrency(data.total_actual, { compact: true })}
        />
        <MetricCard
          label={t("label.over_budget")}
          value={String(overCount)}
          valueColor={overCount > 0 ? "var(--status-critical)" : "var(--status-healthy)"}
        />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
        <Card>
          <CardHeader>{t("section.budget_status")}</CardHeader>
          {data.items.length === 0 ? (
            <EmptyState
              title={t("empty.no_budget")}
              description={t("empty.add_budget_hint")}
            />
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {([
                    { key: "th.team", align: "left" },
                    { key: "th.env", align: "center" },
                    { key: "th.budget", align: "right" },
                    { key: "th.actual", align: "right" },
                    { key: "th.usage", align: "left" },
                    { key: "th.status", align: "center" },
                  ] as const).map((col, idx, arr) => (
                    <th
                      key={col.key}
                      style={{
                        textAlign: col.align,
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
                      {t(col.key)}
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
                        <span style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>{t("empty.no_budget_set")}</span>
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
