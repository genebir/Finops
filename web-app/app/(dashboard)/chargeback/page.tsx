import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState } from "@/components/primitives/States";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/formatters";
import type { ChargebackItem } from "@/lib/types";

const TEAM_COLORS = [
  "var(--provider-aws)",
  "var(--provider-gcp)",
  "var(--provider-azure)",
  "var(--status-healthy)",
  "var(--status-warning)",
  "#5C8A7A",
  "#A89F94",
];

export default async function ChargebackPage() {
  let data;
  try { data = await api.chargeback(); }
  catch (e) { return <ErrorState message={String(e)} />; }

  return (
    <div style={{ maxWidth: "1100px" }}>
      <PageHeader
        title="Chargeback"
        description={`${data.billing_month} — Cost allocation report by team`}
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
          label="Total Cost"
          value={formatCurrency(data.total_cost, { compact: true })}
        />
        <MetricCard
          label="Teams"
          value={String(data.by_team.length)}
        />
        <MetricCard
          label="Cost Units"
          value={String(data.items.length)}
        />
      </div>

      {/* 2-column: Team summary + item breakdown */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 3fr", gap: "20px" }}>
        <Card>
          <CardHeader>Cost by Team</CardHeader>
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            {data.by_team.map((t, idx) => (
              <div key={t.team} style={{ display: "flex", alignItems: "center", gap: "10px" }}>
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
                  {t.team}
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
                      width: `${t.pct}%`,
                      height: "100%",
                      background: TEAM_COLORS[idx % TEAM_COLORS.length],
                      borderRadius: "var(--radius-full)",
                      transition: "width 0.4s ease",
                    }}
                  />
                </div>
                <span
                  className="font-mono"
                  style={{ fontSize: "12px", color: "var(--text-secondary)", width: "64px", textAlign: "right" }}
                >
                  <span className="currency-symbol">$</span>
                  {(t.cost / 1000).toFixed(1)}k
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
                  {t.pct}%
                </span>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader>Cost Unit Breakdown</CardHeader>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Team", "Product", "Env", "Cost", "Share"].map((h) => (
                  <th
                    key={h}
                    style={{
                      textAlign: ["Cost", "Share"].includes(h) ? "right" : "left",
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
              {data.items.map((item: ChargebackItem, i: number) => (
                <tr
                  key={i}
                  style={{
                    borderBottom: i < data.items.length - 1 ? "1px solid var(--border)" : "none",
                  }}
                >
                  <td style={{ padding: "10px 0", fontSize: "13px", fontWeight: 500, color: "var(--text-primary)", fontFamily: "Inter, sans-serif" }}>
                    {item.team}
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "12px", color: "var(--text-secondary)", fontFamily: "Inter, sans-serif" }}>
                    {item.product}
                  </td>
                  <td style={{ padding: "10px 8px" }}>
                    <SeverityBadge severity={item.env} />
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "12px", fontWeight: 500, color: "var(--text-primary)" }}>
                      <span className="currency-symbol">$</span>
                      {Math.round(item.cost).toLocaleString("en-US")}
                    </span>
                  </td>
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "right" }}>
                    <span style={{ fontSize: "12px", color: "var(--text-tertiary)", fontFamily: "Inter, sans-serif" }}>
                      {item.pct}%
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
