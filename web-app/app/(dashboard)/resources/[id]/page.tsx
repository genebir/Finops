import { API_BASE } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState, EmptyState } from "@/components/primitives/States";
import { ProviderBadge } from "@/components/status/SeverityBadge";
import Link from "next/link";

interface MonthlyPoint {
  billing_month: string;
  cost: number;
  provider: string;
  service_name: string;
  team: string;
  env: string;
}

interface DailyPoint {
  date: string;
  cost: number;
}

interface AnomalyPoint {
  charge_date: string;
  effective_cost: number;
  z_score: number;
  severity: string;
  detector_name: string;
}

interface ResourceSummary {
  total_cost: number;
  avg_monthly_cost: number;
  latest_month_cost: number;
  anomaly_count: number;
  months_tracked: number;
}

interface ResourceDetailData {
  resource_id: string;
  provider: string;
  service_name: string;
  team: string;
  env: string;
  monthly_history: MonthlyPoint[];
  daily_last30: DailyPoint[];
  anomaly_history: AnomalyPoint[];
  summary: ResourceSummary;
}

async function fetchResource(id: string): Promise<ResourceDetailData> {
  const res = await fetch(
    `${API_BASE}/api/resources/${encodeURIComponent(id)}?months=12`,
    { cache: "no-store" }
  );
  if (!res.ok) throw new Error(`Resource not found: ${id}`);
  return res.json();
}

function DailyBar({ cost, maxCost, date }: { cost: number; maxCost: number; date: string }) {
  const pct = maxCost > 0 ? (cost / maxCost) * 100 : 0;
  const day = date.slice(-2);
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "3px", flex: 1 }}>
      <div style={{ width: "100%", height: "60px", display: "flex", alignItems: "flex-end" }}>
        <div
          style={{
            width: "100%",
            height: `${pct}%`,
            minHeight: "2px",
            backgroundColor: "var(--provider-aws)",
            borderRadius: "2px 2px 0 0",
          }}
        />
      </div>
      <span style={{ fontSize: "9px", color: "var(--text-tertiary)" }}>{day}</span>
    </div>
  );
}

const MONTHLY_HEADERS = ["Month", "Cost", "Team", "Env"];
const ANOMALY_HEADERS = ["Date", "Cost", "Z-Score", "Severity", "Detector"];

const SEVERITY_COLOR: Record<string, string> = {
  critical: "var(--status-critical)",
  warning: "var(--status-warning)",
};

export default async function ResourceDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const resourceId = decodeURIComponent(params.id);

  let data: ResourceDetailData;
  try {
    data = await fetchResource(resourceId);
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { summary, monthly_history, daily_last30, anomaly_history } = data;
  const maxDaily = Math.max(...daily_last30.map((d) => d.cost), 1);

  const ENV_COLORS: Record<string, string> = {
    prod: "#D97757",
    staging: "#8E7BB5",
    dev: "#5B9BD5",
  };
  const envColor = (env: string) => ENV_COLORS[env] ?? "#9B9590";

  return (
    <div style={{ maxWidth: "1100px" }}>
      {/* Back link */}
      <Link
        href="/inventory"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "4px",
          fontSize: "13px",
          color: "var(--text-secondary)",
          textDecoration: "none",
          marginBottom: "16px",
        }}
      >
        ← Inventory
      </Link>

      <PageHeader
        title={resourceId}
        description={`${data.service_name} · ${data.provider} · ${data.team}/${data.env}`}
        action={<ProviderBadge provider={data.provider as "aws" | "gcp" | "azure"} />}
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "16px", marginBottom: "32px" }}>
        <MetricCard
          label="Total Cost"
          value={`$${Math.round(summary.total_cost).toLocaleString("en-US")}`}
          sub={`${summary.months_tracked} months`}
        />
        <MetricCard
          label="Avg Monthly"
          value={`$${Math.round(summary.avg_monthly_cost).toLocaleString("en-US")}`}
        />
        <MetricCard
          label="Latest Month"
          value={`$${Math.round(summary.latest_month_cost).toLocaleString("en-US")}`}
        />
        <MetricCard
          label="Anomalies"
          value={String(summary.anomaly_count)}
          valueColor={summary.anomaly_count > 0 ? "var(--status-warning)" : undefined}
        />
      </div>

      {/* Daily cost chart */}
      {daily_last30.length > 0 && (
        <Card style={{ marginBottom: "24px" }}>
          <CardHeader>Daily Cost — Last 30 Days</CardHeader>
          <div
            style={{
              display: "flex",
              alignItems: "flex-end",
              gap: "3px",
              height: "80px",
            }}
          >
            {daily_last30.map((d) => (
              <DailyBar key={d.date} cost={d.cost} maxCost={maxDaily} date={d.date} />
            ))}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: "6px" }}>
            <span style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>
              {daily_last30[0]?.date}
            </span>
            <span style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>
              {daily_last30[daily_last30.length - 1]?.date}
            </span>
          </div>
        </Card>
      )}

      {/* Monthly history */}
      <Card style={{ marginBottom: "24px" }}>
        <CardHeader>Monthly History</CardHeader>
        {monthly_history.length === 0 ? (
          <EmptyState title="No monthly history" description="No cost data available." />
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {MONTHLY_HEADERS.map((h, idx, arr) => (
                  <th
                    key={h}
                    style={{
                      textAlign: idx === 1 ? "right" : "left",
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
              {[...monthly_history].reverse().map((m, i, arr) => (
                <tr
                  key={m.billing_month}
                  style={{ borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}
                >
                  <td style={{ padding: "10px 8px 10px 0", fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
                    {m.billing_month}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-primary)" }}>
                      <span className="currency-symbol">$</span>
                      {Math.round(m.cost).toLocaleString("en-US")}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "13px", color: "var(--text-secondary)" }}>
                    {m.team}
                  </td>
                  <td style={{ padding: "10px 0 10px 8px" }}>
                    <span
                      style={{
                        display: "inline-block",
                        padding: "2px 8px",
                        borderRadius: "var(--radius-full)",
                        fontSize: "10px",
                        fontWeight: 600,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        background: `color-mix(in srgb, ${envColor(m.env)} 15%, transparent)`,
                        color: envColor(m.env),
                      }}
                    >
                      {m.env}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Anomaly history */}
      <Card>
        <CardHeader>Anomaly History</CardHeader>
        {anomaly_history.length === 0 ? (
          <EmptyState title="No anomalies detected" description="No anomalies recorded for this resource." />
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {ANOMALY_HEADERS.map((h, idx, arr) => (
                  <th
                    key={h}
                    style={{
                      textAlign: h === "Severity" ? "center" : idx >= 1 && idx <= 2 ? "right" : "left",
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
              {anomaly_history.slice(0, 20).map((a, i, arr) => (
                <tr
                  key={`${a.charge_date}-${a.detector_name}`}
                  style={{ borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}
                >
                  <td style={{ padding: "10px 8px 10px 0", fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
                    {a.charge_date}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-primary)" }}>
                      <span className="currency-symbol">$</span>
                      {a.effective_cost.toLocaleString("en-US", { maximumFractionDigits: 2 })}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", color: SEVERITY_COLOR[a.severity] ?? "var(--text-secondary)" }}>
                      {a.z_score.toFixed(2)}σ
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center" }}>
                    <span
                      style={{
                        display: "inline-block",
                        padding: "2px 8px",
                        borderRadius: "var(--radius-full)",
                        fontSize: "10px",
                        fontWeight: 600,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        color: SEVERITY_COLOR[a.severity] ?? "var(--text-tertiary)",
                        background: `color-mix(in srgb, ${SEVERITY_COLOR[a.severity] ?? "var(--text-tertiary)"} 15%, transparent)`,
                      }}
                    >
                      {a.severity}
                    </span>
                  </td>
                  <td style={{ padding: "10px 0 10px 8px" }}>
                    <code className="font-mono" style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                      {a.detector_name}
                    </code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
