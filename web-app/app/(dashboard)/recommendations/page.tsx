import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { EmptyState, ErrorState } from "@/components/primitives/States";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/formatters";
import type { RecommendationItem } from "@/lib/types";

const RULE_META: Record<string, { label: string; color: string; bg: string }> = {
  idle:               { label: "Idle Resource",     color: "var(--provider-gcp)",      bg: "rgba(107,140,174,0.08)" },
  high_growth:        { label: "High Growth",        color: "var(--status-warning)",    bg: "rgba(232,160,74,0.08)"  },
  persistent_anomaly: { label: "Persistent Anomaly", color: "var(--status-critical)",   bg: "rgba(200,85,61,0.08)"   },
};

export default async function RecommendationsPage() {
  let data;
  try { data = await api.recommendations(); }
  catch (e) { return <ErrorState message={String(e)} />; }

  const byRule = data.items.reduce<Record<string, RecommendationItem[]>>((acc, item) => {
    (acc[item.rule_type] ??= []).push(item);
    return acc;
  }, {});

  return (
    <div style={{ maxWidth: "1000px" }}>
      <PageHeader
        title="Recommendations"
        description="Cost optimization recommendations — run the cost_recommendations asset in Dagster to populate data."
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
          label="Total Recommendations"
          value={String(data.items.length)}
        />
        <MetricCard
          label="Potential Savings"
          value={data.total_potential_savings > 0 ? formatCurrency(data.total_potential_savings, { compact: true }) : "—"}
          valueColor="var(--status-healthy)"
        />
        <MetricCard
          label="Rule Types"
          value={String(Object.keys(byRule).length)}
        />
      </div>

      {data.items.length === 0 ? (
        <Card>
          <EmptyState
            title="No recommendations"
            description="Run the cost_recommendations asset in Dagster."
          />
        </Card>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          {Object.entries(byRule).map(([rule, items]) => {
            const meta = RULE_META[rule] ?? { label: rule, color: "var(--text-tertiary)", bg: "rgba(168,159,148,0.08)" };
            return (
              <Card key={rule}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "20px" }}>
                  <span
                    style={{
                      fontSize: "10px",
                      fontWeight: 600,
                      fontFamily: "Inter, sans-serif",
                      letterSpacing: "0.07em",
                      textTransform: "uppercase",
                      color: meta.color,
                      background: meta.bg,
                      border: `1px solid ${meta.color}`,
                      borderRadius: "var(--radius-full)",
                      padding: "3px 10px",
                    }}
                  >
                    {meta.label}
                  </span>
                  <span style={{ fontSize: "12px", color: "var(--text-tertiary)", fontFamily: "Inter, sans-serif" }}>
                    {items.length} item{items.length !== 1 ? "s" : ""}
                  </span>
                </div>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      {["Resource", "Team", "Env", "Description", "Savings", "Severity"].map((h) => (
                        <th
                          key={h}
                          style={{
                            textAlign: h === "Savings" ? "right" : "left",
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
                    {items.map((item: RecommendationItem, i: number) => (
                      <tr
                        key={i}
                        style={{ borderBottom: i < items.length - 1 ? "1px solid var(--border)" : "none" }}
                      >
                        <td style={{ padding: "10px 0" }}>
                          <code className="font-mono" style={{ fontSize: "11px", color: "var(--text-primary)" }}>
                            {item.resource_id}
                          </code>
                        </td>
                        <td style={{ padding: "10px 8px", fontSize: "12px", color: "var(--text-secondary)" }}>
                          {item.team}
                        </td>
                        <td style={{ padding: "10px 8px" }}>
                          <SeverityBadge severity={item.env} />
                        </td>
                        <td style={{ padding: "10px 8px", fontSize: "12px", color: "var(--text-secondary)", maxWidth: "260px" }}>
                          {item.description}
                        </td>
                        <td style={{ padding: "10px 8px", textAlign: "right" }}>
                          {item.potential_savings > 0 ? (
                            <span className="font-mono" style={{ fontSize: "12px", color: "var(--status-healthy)" }}>
                              <span className="currency-symbol">$</span>
                              {Math.round(item.potential_savings).toLocaleString("en-US")}
                            </span>
                          ) : (
                            <span style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>—</span>
                          )}
                        </td>
                        <td style={{ padding: "10px 0 10px 8px" }}>
                          <SeverityBadge severity={item.severity} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
