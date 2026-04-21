import { API_BASE } from "../../../lib/api";
import type { SavingsData } from "../../../lib/types";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState, EmptyState } from "@/components/primitives/States";

export const metadata = { title: "Savings — FinOps" };

const STATUS_COLOR: Record<string, string> = {
  realized:       "var(--status-healthy)",
  partial:        "var(--status-warning)",
  pending:        "var(--text-secondary)",
  cost_increased: "var(--status-critical)",
};

async function fetchSavings(): Promise<SavingsData> {
  const res = await fetch(`${API_BASE}/api/savings`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error("Failed to load savings data");
  return res.json();
}

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLOR[status] ?? "var(--text-secondary)";
  const label = status.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 8px",
      borderRadius: "6px",
      fontSize: "11px",
      fontWeight: 600,
      background: `color-mix(in srgb, ${color} 15%, transparent)`,
      color,
    }}>
      {label}
    </span>
  );
}

const headers = ["Resource", "Team", "Type", "Estimated", "Realized", "Prev Cost", "Curr Cost", "Status"];

export default async function SavingsPage() {
  let data: SavingsData;
  try {
    data = await fetchSavings();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { summary, items, billing_month } = data;
  const realizationPct = summary.total_estimated > 0
    ? Math.round(summary.total_realized / summary.total_estimated * 100)
    : 0;

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title="Savings Tracker"
        description={`${billing_month} — recommendation realization tracking`}
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "16px", marginBottom: "32px" }}>
        <MetricCard
          label="Estimated"
          value={`$${summary.total_estimated.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
        />
        <MetricCard
          label="Realized"
          value={`$${summary.total_realized.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
          valueColor="var(--status-healthy)"
        />
        <MetricCard
          label="Realization"
          value={`${realizationPct}%`}
          valueColor={realizationPct >= 80 ? "var(--status-healthy)" : realizationPct >= 40 ? "var(--status-warning)" : "var(--status-critical)"}
        />
        <MetricCard
          label="Recommendations"
          value={String(items.length)}
        />
      </div>

      {/* Status summary pills */}
      <div style={{ display: "flex", gap: "16px", marginBottom: "24px" }}>
        {[
          { label: "Realized",       count: summary.realized_count,       color: "var(--status-healthy)" },
          { label: "Partial",        count: summary.partial_count,        color: "var(--status-warning)" },
          { label: "Pending",        count: summary.pending_count,        color: "var(--text-secondary)" },
          { label: "Cost Increased", count: summary.cost_increased_count, color: "var(--status-critical)" },
        ].map(({ label, count, color }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: color, display: "inline-block" }} />
            <span style={{ color: "var(--text-secondary)" }}>{label}:</span>
            <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>{count}</span>
          </div>
        ))}
      </div>

      <Card>
        <CardHeader>Savings by Recommendation</CardHeader>
        {items.length === 0 ? (
          <EmptyState title="No savings data" description="Materialize cost_recommendations and savings_tracker assets first." />
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {headers.map((h, idx, arr) => (
                  <th key={h} style={{
                    textAlign: "left",
                    fontSize: "10px",
                    fontWeight: 600,
                    fontFamily: "Inter, sans-serif",
                    color: "var(--text-tertiary)",
                    letterSpacing: "0.07em",
                    textTransform: "uppercase",
                    padding: idx === 0 ? "0 8px 12px 0" : idx === arr.length - 1 ? "0 0 12px 8px" : "0 8px 12px 8px",
                    borderBottom: "1px solid var(--border)",
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item, idx, arr) => (
                <tr key={idx} style={{ borderBottom: idx < arr.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <td style={{ padding: "10px 0", maxWidth: "180px" }}>
                    <div style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: "13px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {item.resource_id}
                    </div>
                    <div style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>{item.provider}</div>
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "13px", color: "var(--text-secondary)" }}>
                    {item.team}<br />
                    <span style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>{item.env}</span>
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "13px", color: "var(--text-secondary)" }}>{item.recommendation_type}</td>
                  <td style={{ padding: "10px 8px" }}>
                    <span className="font-mono" style={{ fontSize: "13px", color: "var(--status-healthy)" }}>
                      ${item.estimated_savings.toFixed(0)}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px" }}>
                    <span className="font-mono" style={{ fontSize: "13px", color: item.realized_savings != null ? (item.realized_savings >= 0 ? "var(--status-healthy)" : "var(--status-critical)") : "var(--text-tertiary)" }}>
                      {item.realized_savings != null ? `$${item.realized_savings.toFixed(0)}` : "—"}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px" }}>
                    <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                      {item.prev_month_cost != null ? `$${item.prev_month_cost.toFixed(0)}` : "—"}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px" }}>
                    <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                      {item.curr_month_cost != null ? `$${item.curr_month_cost.toFixed(0)}` : "—"}
                    </span>
                  </td>
                  <td style={{ padding: "10px 0 10px 8px" }}>
                    <StatusBadge status={item.status} />
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
