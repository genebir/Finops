import { API_BASE } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState, EmptyState } from "@/components/primitives/States";

interface SeriesPoint {
  date: string;
  total: number;
  critical: number;
  warning: number;
  total_cost: number;
}

interface TopTeam {
  team: string;
  anomaly_count: number;
  total_cost: number;
}

interface Summary {
  total_anomalies: number;
  peak_date: string | null;
  peak_count: number;
  avg_daily: number;
}

interface TimelineData {
  months: number;
  series: SeriesPoint[];
  top_teams: TopTeam[];
  summary: Summary;
}

async function fetchTimeline(months: number = 6): Promise<TimelineData> {
  const res = await fetch(`${API_BASE}/api/anomaly-timeline?months=${months}`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error("Failed to fetch anomaly-timeline");
  return res.json();
}

function Sparkbar({ value, max, critical, warning }: { value: number; max: number; critical: number; warning: number }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  const critPct = value > 0 ? (critical / value) * 100 : 0;
  const warnPct = value > 0 ? (warning / value) * 100 : 0;

  return (
    <div style={{ width: "100%", height: "28px", backgroundColor: "var(--border)", borderRadius: "3px", overflow: "hidden", display: "flex" }}>
      <div style={{ width: `${pct}%`, display: "flex" }}>
        <div style={{ width: `${critPct}%`, height: "100%", backgroundColor: "var(--status-critical)" }} />
        <div style={{ width: `${warnPct}%`, height: "100%", backgroundColor: "var(--status-warning)" }} />
      </div>
    </div>
  );
}

const topTeamHeaders = ["Team", "Anomalies", "Total Anomalous Cost"];

export default async function AnomalyTimelinePage() {
  let data: TimelineData;
  try {
    data = await fetchTimeline(6);
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { series, top_teams, summary } = data;
  const maxCount = series.length > 0 ? Math.max(...series.map((s) => s.total)) : 1;

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title="Anomaly Timeline"
        description="Daily anomaly counts over the past 6 months — critical / warning breakdown"
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "16px", marginBottom: "32px" }}>
        <MetricCard
          label="Total Anomalies"
          value={summary.total_anomalies.toLocaleString()}
        />
        <MetricCard
          label="Peak Day"
          value={summary.peak_date ?? "—"}
          valueColor="var(--status-critical)"
        />
        <MetricCard
          label="Peak Count"
          value={summary.peak_count.toLocaleString()}
          valueColor="var(--status-critical)"
        />
        <MetricCard
          label="Avg / Day"
          value={summary.avg_daily.toFixed(1)}
        />
      </div>

      <Card style={{ marginBottom: "24px" }}>
        <CardHeader>Daily Anomaly Count</CardHeader>
        {series.length === 0 ? (
          <EmptyState title="No anomaly data" description="No anomalies found for this period." />
        ) : (
          <div style={{ overflowX: "auto" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "2px", minWidth: "600px" }}>
              {series.map((pt) => (
                <div key={pt.date} style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <span style={{ fontSize: "11px", color: "var(--text-tertiary)", width: "80px", flexShrink: 0 }}>
                    {pt.date}
                  </span>
                  <div style={{ flex: 1 }}>
                    <Sparkbar value={pt.total} max={maxCount} critical={pt.critical} warning={pt.warning} />
                  </div>
                  <span className="font-mono" style={{ fontSize: "12px", color: "var(--text-secondary)", width: "32px", textAlign: "right" }}>
                    {pt.total}
                  </span>
                  <span className="font-mono" style={{ fontSize: "11px", color: "var(--text-tertiary)", width: "80px", textAlign: "right" }}>
                    ${pt.total_cost.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                  </span>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: "16px", marginTop: "16px" }}>
              {[["var(--status-critical)", "Critical"], ["var(--status-warning)", "Warning"]].map(([color, label]) => (
                <div key={label} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <div style={{ width: "10px", height: "10px", borderRadius: "2px", backgroundColor: color }} />
                  <span style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>{label}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      {top_teams.length > 0 && (
        <Card>
          <CardHeader>Top Impacted Teams</CardHeader>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {topTeamHeaders.map((h, idx, arr) => (
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
              {top_teams.map((t, i, arr) => (
                <tr key={t.team} style={{ borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <td style={{ padding: "10px 0", fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
                    <span style={{ marginRight: "8px", color: "var(--text-tertiary)", fontSize: "12px" }}>#{i + 1}</span>
                    {t.team}
                  </td>
                  <td style={{ padding: "10px 8px" }}>
                    <span className="font-mono" style={{ fontSize: "13px", color: "var(--status-critical)" }}>
                      {t.anomaly_count.toLocaleString()}
                    </span>
                  </td>
                  <td style={{ padding: "10px 0 10px 8px" }}>
                    <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-primary)" }}>
                      ${t.total_cost.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                    </span>
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
