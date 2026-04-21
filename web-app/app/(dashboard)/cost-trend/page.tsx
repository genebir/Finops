import { API_BASE } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState, EmptyState } from "@/components/primitives/States";

export const dynamic = "force-dynamic";

interface TrendPoint {
  billing_month: string;
  total_cost: number;
  resource_count: number | string;
  anomaly_count: number;
}

interface TrendSummary {
  latest_month: string | null;
  latest_cost: number;
  mom_change_pct: number | null;
  avg_monthly_cost: number;
}

interface TrendData {
  series: TrendPoint[];
  months: string[];
  summary: TrendSummary;
}

interface CompareItem {
  team: string;
  env: string;
  provider: string;
  period1_cost: number;
  period2_cost: number;
  change: number;
  change_pct: number | null;
}

interface CompareData {
  period1: string;
  period2: string;
  items: CompareItem[];
  summary: {
    total_period1: number;
    total_period2: number;
    total_change: number;
    overall_change_pct: number | null;
  };
}

async function fetchTrend(): Promise<TrendData> {
  const res = await fetch(`${API_BASE}/api/cost-trend?months=24`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch cost trend");
  return res.json();
}

async function fetchCompare(period1: string, period2: string): Promise<CompareData | null> {
  try {
    const res = await fetch(
      `${API_BASE}/api/cost-trend/compare?period1=${encodeURIComponent(period1)}&period2=${encodeURIComponent(period2)}`,
      { cache: "no-store" }
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

function MoMBadge({ pct }: { pct: number | null }) {
  if (pct == null) return null;
  const isUp = pct > 0;
  const color = isUp ? "var(--status-critical)" : "var(--status-healthy)";
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: "var(--radius-full)",
        fontSize: "11px",
        fontWeight: 600,
        color,
        background: `color-mix(in srgb, ${color} 15%, transparent)`,
      }}
    >
      {isUp ? "+" : ""}{pct.toFixed(1)}%
    </span>
  );
}

function TrendBar({ cost, maxCost, month }: { cost: number; maxCost: number; month: string }) {
  const pct = maxCost > 0 ? (cost / maxCost) * 100 : 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
      <span
        className="font-mono"
        style={{
          fontSize: "11px",
          color: "var(--text-tertiary)",
          width: "60px",
          flexShrink: 0,
        }}
      >
        {month}
      </span>
      <div
        style={{
          flex: 1,
          height: "18px",
          backgroundColor: "var(--border)",
          borderRadius: "3px",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            backgroundColor: "var(--provider-aws)",
            borderRadius: "3px",
          }}
        />
      </div>
      <span
        className="font-mono"
        style={{ fontSize: "12px", color: "var(--text-primary)", width: "80px", textAlign: "right" }}
      >
        ${Math.round(cost).toLocaleString("en-US")}
      </span>
    </div>
  );
}

const COMPARE_HEADERS = ["Team", "Env", "Provider", "Period 1", "Period 2", "Change", "Δ%"];

const SERIES_HEADERS = ["Month", "Total Cost", "Resources", "Anomalies"];

export default async function CostTrendPage() {
  let trend: TrendData;
  try {
    trend = await fetchTrend();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { series, summary } = trend;
  const maxCost = Math.max(...series.map((s) => s.total_cost), 1);

  // Compare the two most recent months if we have at least 2
  let compare: CompareData | null = null;
  if (series.length >= 2) {
    const p2 = series[series.length - 1].billing_month;
    const p1 = series[series.length - 2].billing_month;
    compare = await fetchCompare(p1, p2);
  }

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title="Cost Trend"
        description={`${series.length}-month cost time series and period-over-period comparison`}
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "16px", marginBottom: "32px" }}>
        <MetricCard
          label="Latest Month"
          value={summary.latest_month ?? "—"}
        />
        <MetricCard
          label="Latest Cost"
          value={`$${Math.round(summary.latest_cost).toLocaleString("en-US")}`}
        />
        <MetricCard
          label="MoM Change"
          value={summary.mom_change_pct != null ? `${summary.mom_change_pct > 0 ? "+" : ""}${summary.mom_change_pct.toFixed(1)}%` : "—"}
          valueColor={
            summary.mom_change_pct == null
              ? undefined
              : summary.mom_change_pct > 10
              ? "var(--status-critical)"
              : summary.mom_change_pct < -5
              ? "var(--status-healthy)"
              : undefined
          }
        />
        <MetricCard
          label="Avg Monthly"
          value={`$${Math.round(summary.avg_monthly_cost).toLocaleString("en-US")}`}
        />
      </div>

      {/* Trend bars */}
      <Card style={{ marginBottom: "24px" }}>
        <CardHeader>Monthly Cost Trend</CardHeader>
        {series.length === 0 ? (
          <EmptyState
            title="No trend data"
            description="Run the cost_trend asset in Dagster."
          />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {series.map((s) => (
              <TrendBar
                key={s.billing_month}
                month={s.billing_month}
                cost={s.total_cost}
                maxCost={maxCost}
              />
            ))}
          </div>
        )}
      </Card>

      {/* Time series table */}
      <Card style={{ marginBottom: "24px" }}>
        <CardHeader>Monthly Detail</CardHeader>
        {series.length === 0 ? null : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {SERIES_HEADERS.map((h, idx, arr) => (
                  <th
                    key={h}
                    style={{
                      textAlign: idx === 0 ? "left" : "right",
                      fontSize: "10px",
                      fontWeight: 600,
                      fontFamily: "Inter, sans-serif",
                      color: "var(--text-tertiary)",
                      letterSpacing: "0.07em",
                      textTransform: "uppercase",
                      padding:
                        idx === 0
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
              {[...series].reverse().map((s, i, arr) => (
                <tr
                  key={s.billing_month}
                  style={{ borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}
                >
                  <td style={{ padding: "10px 8px 10px 0", fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
                    {s.billing_month}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-primary)" }}>
                      <span className="currency-symbol">$</span>
                      {Math.round(s.total_cost).toLocaleString("en-US")}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right", fontSize: "13px", color: "var(--text-secondary)" }}>
                    {Number(s.resource_count).toLocaleString()}
                  </td>
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "right" }}>
                    {Number(s.anomaly_count) > 0 ? (
                      <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--status-warning)" }}>
                        {Number(s.anomaly_count).toLocaleString()}
                      </span>
                    ) : (
                      <span style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>0</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Period comparison */}
      {compare && compare.items.length > 0 && (
        <Card>
          <CardHeader>
            Period Comparison — {compare.period1} vs {compare.period2}
          </CardHeader>
          {/* Summary row */}
          <div style={{ display: "flex", gap: "24px", marginBottom: "20px", padding: "12px 16px", borderRadius: "var(--radius-button)", backgroundColor: "color-mix(in srgb, var(--border) 40%, transparent)" }}>
            <div>
              <span style={{ fontSize: "11px", color: "var(--text-tertiary)", textTransform: "uppercase", fontWeight: 600, letterSpacing: "0.07em" }}>
                {compare.period1}
              </span>
              <div className="font-mono" style={{ fontSize: "16px", fontWeight: 600, color: "var(--text-primary)", marginTop: "2px" }}>
                ${Math.round(compare.summary.total_period1).toLocaleString("en-US")}
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", fontSize: "20px", color: "var(--text-tertiary)" }}>→</div>
            <div>
              <span style={{ fontSize: "11px", color: "var(--text-tertiary)", textTransform: "uppercase", fontWeight: 600, letterSpacing: "0.07em" }}>
                {compare.period2}
              </span>
              <div className="font-mono" style={{ fontSize: "16px", fontWeight: 600, color: "var(--text-primary)", marginTop: "2px" }}>
                ${Math.round(compare.summary.total_period2).toLocaleString("en-US")}
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <MoMBadge pct={compare.summary.overall_change_pct} />
              <span className="font-mono" style={{ fontSize: "13px", color: compare.summary.total_change > 0 ? "var(--status-critical)" : "var(--status-healthy)" }}>
                {compare.summary.total_change > 0 ? "+" : ""}${Math.round(compare.summary.total_change).toLocaleString("en-US")}
              </span>
            </div>
          </div>

          {/* Breakdown table */}
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {COMPARE_HEADERS.map((h, idx, arr) => (
                  <th
                    key={h}
                    style={{
                      textAlign: idx < 3 ? "left" : "right",
                      fontSize: "10px",
                      fontWeight: 600,
                      fontFamily: "Inter, sans-serif",
                      color: "var(--text-tertiary)",
                      letterSpacing: "0.07em",
                      textTransform: "uppercase",
                      padding:
                        idx === 0
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
              {compare.items.slice(0, 20).map((item, i, arr) => (
                <tr
                  key={`${item.team}-${item.env}-${item.provider}`}
                  style={{ borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}
                >
                  <td style={{ padding: "10px 8px 10px 0", fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
                    {item.team}
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "13px", color: "var(--text-secondary)" }}>
                    {item.env}
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "13px", color: "var(--text-secondary)" }}>
                    {item.provider}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                      ${Math.round(item.period1_cost).toLocaleString("en-US")}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-primary)" }}>
                      ${Math.round(item.period2_cost).toLocaleString("en-US")}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span
                      className="font-mono"
                      style={{
                        fontSize: "13px",
                        color: item.change > 0 ? "var(--status-critical)" : item.change < 0 ? "var(--status-healthy)" : "var(--text-tertiary)",
                      }}
                    >
                      {item.change > 0 ? "+" : ""}${Math.round(item.change).toLocaleString("en-US")}
                    </span>
                  </td>
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "right" }}>
                    <MoMBadge pct={item.change_pct} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
