import { API_BASE } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState, EmptyState } from "@/components/primitives/States";
import type { BurnRateData, BurnRateSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

async function fetchBurnRate(): Promise<BurnRateData> {
  const res = await fetch(`${API_BASE}/api/burn-rate`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch burn-rate");
  return res.json();
}

const STATUS_COLOR: Record<string, string> = {
  critical: "var(--status-critical)",
  warning: "var(--status-warning)",
  on_track: "var(--status-healthy)",
  no_budget: "var(--text-tertiary)",
};

function fmt(n: number | null | undefined): string {
  if (n == null) return "—";
  return `$${Math.round(n).toLocaleString("en-US")}`;
}

function BurnBar({ pct }: { pct: number | null }) {
  if (pct == null) {
    return <span style={{ color: "var(--text-tertiary)", fontSize: "12px" }}>no budget</span>;
  }
  const color =
    pct >= 100
      ? "var(--status-critical)"
      : pct >= 80
      ? "var(--status-warning)"
      : "var(--status-healthy)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <div
        style={{
          flex: 1,
          height: "6px",
          backgroundColor: "var(--border)",
          borderRadius: "3px",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${Math.min(pct, 100)}%`,
            backgroundColor: color,
            borderRadius: "3px",
          }}
        />
      </div>
      <span
        className="font-mono"
        style={{ fontSize: "12px", color, minWidth: "42px", textAlign: "right" }}
      >
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

const EMPTY_SUMMARY: BurnRateSummary = {
  total_mtd: 0,
  total_projected_eom: 0,
  critical_count: 0,
  warning_count: 0,
  on_track_count: 0,
};

const HEADERS = ["Team", "Env", "MTD Cost", "Daily Avg", "Projected EOM", "Budget", "Progress", "Status"];

export default async function BurnRatePage() {
  let data: BurnRateData;
  try {
    data = await fetchBurnRate();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { items, billing_month } = data;
  const summary: BurnRateSummary = data.summary ?? EMPTY_SUMMARY;

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title="Burn Rate"
        description={`${billing_month} — MTD spend velocity and projected end-of-month cost`}
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "16px", marginBottom: "32px" }}>
        <MetricCard
          label="MTD Total"
          value={fmt(summary.total_mtd)}
          sub="month-to-date"
        />
        <MetricCard
          label="Projected EOM"
          value={fmt(summary.total_projected_eom)}
          sub="end-of-month estimate"
        />
        <MetricCard
          label="Critical"
          value={String(summary.critical_count ?? 0)}
          sub="over budget trajectory"
          valueColor={(summary.critical_count ?? 0) > 0 ? "var(--status-critical)" : undefined}
        />
        <MetricCard
          label="Warning"
          value={String(summary.warning_count ?? 0)}
          sub="approaching budget"
          valueColor={(summary.warning_count ?? 0) > 0 ? "var(--status-warning)" : undefined}
        />
      </div>

      <Card>
        <CardHeader>Team / Environment Burn Rate</CardHeader>
        {items.length === 0 ? (
          <EmptyState
            title="No burn rate data"
            description="Run the burn_rate asset in Dagster."
          />
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {HEADERS.map((h, idx, arr) => (
                  <th
                    key={h}
                    style={{
                      textAlign:
                        h === "Status"
                          ? "center"
                          : idx >= 2 && idx <= 5
                          ? "right"
                          : "left",
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
              {items.map((r, i, arr) => (
                <tr
                  key={`${r.team}-${r.env}`}
                  style={{ borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}
                >
                  <td style={{ padding: "10px 8px 10px 0", fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
                    {r.team}
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "13px", color: "var(--text-secondary)" }}>
                    {r.env}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-primary)" }}>
                      {fmt(r.mtd_cost)}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                      {fmt(r.daily_avg)}/d
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span
                      className="font-mono"
                      style={{
                        fontSize: "13px",
                        fontWeight: 600,
                        color: STATUS_COLOR[r.status] ?? "var(--text-primary)",
                      }}
                    >
                      {fmt(r.projected_eom)}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>
                      {fmt(r.budget_amount)}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", minWidth: "140px" }}>
                    <BurnBar pct={r.projected_utilization} />
                  </td>
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "center" }}>
                    <span
                      style={{
                        display: "inline-block",
                        padding: "2px 8px",
                        borderRadius: "var(--radius-full)",
                        fontSize: "10px",
                        fontWeight: 600,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        color: STATUS_COLOR[r.status] ?? "var(--text-tertiary)",
                        background: `color-mix(in srgb, ${STATUS_COLOR[r.status] ?? "var(--text-tertiary)"} 15%, transparent)`,
                      }}
                    >
                      {r.status.replace("_", " ")}
                    </span>
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
