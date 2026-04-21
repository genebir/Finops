import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState } from "@/components/primitives/States";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/formatters";
import type { TopResource } from "@/lib/types";
import TeamCostBars from "./TeamCostBars";

export default async function OverviewPage() {
  let data;
  try { data = await api.overview(); }
  catch (e) { return <ErrorState message={String(e)} />; }

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title="Overview"
        description={`${data.period_start} – ${data.period_end}`}
      />

      {/* KPI cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "16px",
          marginBottom: "32px",
        }}
      >
        <MetricCard
          label="Total Cost (MTD)"
          value={formatCurrency(data.total_cost, { compact: true })}
          sub={`${data.active_days} days`}
        />
        <MetricCard
          label="Resources"
          value={String(data.resource_count)}
          sub="active this period"
        />
        <MetricCard
          label="Anomalies Detected"
          value={String(data.anomaly_count)}
          valueColor={data.anomaly_count > 0 ? "var(--status-critical)" : "var(--status-healthy)"}
        />
        <MetricCard
          label="Teams with Spend"
          value={String(data.cost_by_team.length)}
        />
      </div>

      {/* 2-column */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 3fr", gap: "20px" }}>
        {/* Team breakdown */}
        <Card>
          <CardHeader>Cost by Team</CardHeader>
          <TeamCostBars items={data.cost_by_team} />
        </Card>

        {/* Top resources */}
        <Card>
          <CardHeader>Top Resources</CardHeader>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Resource", "Service", "Team", "Env", "Cost"].map((h) => (
                  <th
                    key={h}
                    style={{
                      textAlign: h === "Cost" ? "right" : "left",
                      fontSize: "10px",
                      fontWeight: 600,
                      fontFamily: "Inter, sans-serif",
                      color: "var(--text-tertiary)",
                      letterSpacing: "0.07em",
                      textTransform: "uppercase",
                      paddingBottom: "12px",
                      borderBottom: "1px solid var(--border)",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.top_resources.map((r: TopResource, i: number) => (
                <tr
                  key={r.resource_id}
                  style={{
                    borderBottom:
                      i < data.top_resources.length - 1
                        ? "1px solid var(--border)"
                        : "none",
                  }}
                >
                  <td style={{ padding: "10px 0" }}>
                    <code
                      className="font-mono"
                      style={{ fontSize: "11px", color: "var(--text-primary)" }}
                    >
                      {r.resource_name ?? r.resource_id}
                    </code>
                  </td>
                  <td
                    style={{
                      padding: "10px 8px",
                      fontSize: "12px",
                      color: "var(--text-secondary)",
                    }}
                  >
                    {r.service_name}
                  </td>
                  <td
                    style={{
                      padding: "10px 8px",
                      fontSize: "12px",
                      color: "var(--text-secondary)",
                    }}
                  >
                    {r.team}
                  </td>
                  <td style={{ padding: "10px 8px" }}>
                    <SeverityBadge severity={r.env} />
                  </td>
                  <td style={{ padding: "10px 0", textAlign: "right" }}>
                    <span
                      className="font-mono"
                      style={{ fontSize: "12px", fontWeight: 500, color: "var(--text-primary)" }}
                    >
                      <span className="currency-symbol">$</span>
                      {Math.round(r.cost).toLocaleString("en-US")}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  );
}
