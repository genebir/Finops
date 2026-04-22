import { API_BASE } from "../../../lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState, EmptyState } from "@/components/primitives/States";
import { getT } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";
export const metadata = { title: "Budget Forecast — FinOps" };

interface ForecastItem {
  team: string; env: string;
  days_elapsed: number; days_in_month: number;
  mtd_cost: number; projected_eom: number;
  lower_bound: number; upper_bound: number;
  budget_amount: number | null; projected_pct: number | null;
  risk_level: string;
}
interface ForecastData {
  billing_month: string;
  items: ForecastItem[];
  summary: { total_projected_eom: number; over_budget_count: number; warning_count: number; normal_count: number };
}

const RISK_COLOR: Record<string, string> = {
  over:    "var(--status-critical)",
  warning: "var(--status-warning)",
  normal:  "var(--status-healthy)",
};

async function fetchForecast(): Promise<ForecastData> {
  const res = await fetch(`${API_BASE}/api/budget-forecast`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error("Failed to load budget forecast");
  return res.json();
}

function ProjectionBar({ mtd, projected, budget, daysElapsed, daysInMonth }: {
  mtd: number; projected: number; budget: number | null;
  daysElapsed: number; daysInMonth: number;
}) {
  const maxVal = Math.max(projected, budget ?? projected, 1);
  const mtdW = Math.min(mtd / maxVal * 100, 100);
  const projW = Math.min(projected / maxVal * 100, 100);
  const budgetW = budget ? Math.min(budget / maxVal * 100, 100) : null;
  const elapsed = (daysElapsed / daysInMonth * 100);
  return (
    <div style={{ position: "relative", height: "12px", background: "var(--border)", borderRadius: "6px", overflow: "hidden", minWidth: "120px" }}>
      {/* Projected (faint) */}
      <div style={{ position: "absolute", top: 0, left: 0, height: "100%", width: `${projW}%`, background: "var(--status-critical)", opacity: 0.2, borderRadius: "6px" }} />
      {/* MTD actual */}
      <div style={{ position: "absolute", top: 0, left: 0, height: "100%", width: `${mtdW}%`, background: "var(--status-critical)", borderRadius: "6px" }} />
      {/* Budget line */}
      {budgetW && (
        <div style={{ position: "absolute", top: 0, left: `${budgetW}%`, width: "2px", height: "100%", background: "var(--status-healthy)" }} />
      )}
      {/* Elapsed marker */}
      <div style={{ position: "absolute", top: 0, left: `${elapsed}%`, width: "1px", height: "100%", background: "rgba(255,255,255,0.4)" }} />
    </div>
  );
}

export default async function BudgetForecastPage() {
  const t = getT();
  let data: ForecastData;
  try {
    data = await fetchForecast();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { summary, items, billing_month } = data;
  const HEADERS = [
    { key: "th.team", align: "left" },
    { key: "th.env", align: "center" },
    { key: "th.progress", align: "left" },
    { key: "th.mtd", align: "right" },
    { key: "th.projected", align: "right" },
    { key: "th.budget", align: "right" },
    { key: "th.proj_pct", align: "center" },
    { key: "th.risk", align: "center" },
  ] as const;

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={t("page.budget_forecast.title")}
        description={`${billing_month} — ${t("page.budget_forecast.desc")}`}
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "16px", marginBottom: "32px" }}>
        <MetricCard
          label={t("label.projected_eom")}
          value={`$${summary.total_projected_eom.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
        />
        <MetricCard
          label={t("label.over_budget")}
          value={String(summary.over_budget_count)}
          valueColor="var(--status-critical)"
        />
        <MetricCard
          label={t("label.warning_count")}
          value={String(summary.warning_count)}
          valueColor="var(--status-warning)"
        />
        <MetricCard
          label={t("label.on_track_count")}
          value={String(summary.normal_count)}
          valueColor="var(--status-healthy)"
        />
      </div>

      <Card>
        <CardHeader>{t("section.forecast_by_team")}</CardHeader>
        {items.length === 0 ? (
          <EmptyState title={t("empty.no_forecast")} description="Materialize the budget_forecast Dagster asset first." />
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {HEADERS.map((col, idx, arr) => (
                  <th key={col.key} style={{
                    textAlign: col.align,
                    fontSize: "10px",
                    fontWeight: 600,
                    fontFamily: "Inter, sans-serif",
                    color: "var(--text-tertiary)",
                    letterSpacing: "0.07em",
                    textTransform: "uppercase",
                    padding: idx === 0 ? "0 8px 12px 0" : idx === arr.length - 1 ? "0 0 12px 8px" : "0 8px 12px 8px",
                    borderBottom: "1px solid var(--border)",
                  }}>
                    {t(col.key)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item, idx) => {
                const color = RISK_COLOR[item.risk_level] ?? "var(--text-secondary)";
                return (
                  <tr key={idx} style={{ borderBottom: idx < items.length - 1 ? "1px solid var(--border)" : "none" }}>
                    <td style={{ padding: "10px 0" }}>
                      <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{item.team}</span>
                    </td>
                    <td style={{ padding: "10px 8px", fontSize: "13px", color: "var(--text-secondary)", textAlign: "center" }}>{item.env}</td>
                    <td style={{ padding: "10px 8px", minWidth: "140px" }}>
                      <ProjectionBar
                        mtd={item.mtd_cost} projected={item.projected_eom}
                        budget={item.budget_amount}
                        daysElapsed={item.days_elapsed} daysInMonth={item.days_in_month}
                      />
                      <div style={{ fontSize: "10px", color: "var(--text-tertiary)", marginTop: "2px" }}>
                        Day {item.days_elapsed}/{item.days_in_month}
                      </div>
                    </td>
                    <td style={{ padding: "10px 8px", textAlign: "right" }}>
                      <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-primary)" }}>
                        ${item.mtd_cost.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                      </span>
                    </td>
                    <td style={{ padding: "10px 8px", textAlign: "right" }}>
                      <div className="font-mono" style={{ fontSize: "13px", color: "var(--text-primary)" }}>
                        ${item.projected_eom.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                      </div>
                      <div className="font-mono" style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>
                        [{item.lower_bound.toLocaleString("en-US", { maximumFractionDigits: 0 })}–{item.upper_bound.toLocaleString("en-US", { maximumFractionDigits: 0 })}]
                      </div>
                    </td>
                    <td style={{ padding: "10px 8px", textAlign: "right" }}>
                      <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                        {item.budget_amount != null ? `$${item.budget_amount.toLocaleString("en-US", { maximumFractionDigits: 0 })}` : "—"}
                      </span>
                    </td>
                    <td style={{ padding: "10px 8px", textAlign: "center" }}>
                      <span className="font-mono" style={{ fontSize: "13px", color }}>
                        {item.projected_pct != null ? `${item.projected_pct.toFixed(1)}%` : "—"}
                      </span>
                    </td>
                    <td style={{ padding: "10px 0 10px 8px", textAlign: "center" }}>
                      <span style={{
                        display: "inline-block", padding: "2px 8px", borderRadius: "6px",
                        fontSize: "11px", fontWeight: 600, textTransform: "uppercase",
                        background: `color-mix(in srgb, ${color} 15%, transparent)`,
                        color,
                      }}>
                        {item.risk_level}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
