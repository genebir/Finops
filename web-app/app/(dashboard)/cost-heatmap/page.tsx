import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState } from "@/components/primitives/States";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/formatters";
import type { CostHeatmapData } from "@/lib/types";

export const dynamic = "force-dynamic";

function heatColor(value: number, max: number): string {
  if (max === 0) return "transparent";
  const intensity = Math.min(value / max, 1);
  if (intensity === 0) return "var(--border)";
  // interpolate from #3B2E22 (low) to #D97757 (high)
  const r = Math.round(59 + (217 - 59) * intensity);
  const g = Math.round(46 + (119 - 46) * intensity);
  const b = Math.round(34 + (87 - 34) * intensity);
  return `rgb(${r},${g},${b})`;
}

function formatDay(dateStr: string): string {
  return dateStr.slice(8); // "2024-01-15" → "15"
}

export default async function CostHeatmapPage() {
  let data: CostHeatmapData;
  try {
    data = await api.costHeatmap();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { billing_month, dates, matrix, max_cost } = data;

  const totalCost = matrix.reduce(
    (sum, row) => sum + row.values.reduce((s, v) => s + v, 0),
    0,
  );
  const teamCount = matrix.length;
  const dayCount = dates.length;
  const avgPerTeam = teamCount > 0 ? totalCost / teamCount : 0;

  // Find peak day (sum across teams)
  const dayTotals = dates.map((_, di) =>
    matrix.reduce((sum, row) => sum + (row.values[di] ?? 0), 0),
  );
  const peakDayIdx = dayTotals.indexOf(Math.max(...dayTotals, 0));
  const peakDay = dates[peakDayIdx] ?? "—";

  return (
    <div style={{ maxWidth: "1400px" }}>
      <PageHeader
        title="Cost Heatmap"
        description={`Daily team cost matrix — ${billing_month}`}
      />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "16px",
          marginBottom: "32px",
        }}
      >
        <MetricCard
          label="Total Cost"
          value={formatCurrency(totalCost, { compact: true })}
          sub={billing_month}
        />
        <MetricCard
          label="Teams"
          value={String(teamCount)}
          sub="active this month"
        />
        <MetricCard
          label="Days"
          value={String(dayCount)}
          sub="with data"
        />
        <MetricCard
          label="Avg / Team"
          value={formatCurrency(avgPerTeam, { compact: true })}
          sub="this month"
        />
      </div>

      {matrix.length === 0 ? (
        <Card>
          <p style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>
            No heatmap data available. Materialize the cost pipeline in Dagster first.
          </p>
        </Card>
      ) : (
        <Card>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
            <CardHeader>Daily Cost by Team</CardHeader>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>Low</span>
              <div style={{ display: "flex", gap: "2px" }}>
                {[0.1, 0.3, 0.5, 0.7, 0.9, 1.0].map((v) => (
                  <div
                    key={v}
                    style={{
                      width: "16px",
                      height: "16px",
                      borderRadius: "3px",
                      backgroundColor: heatColor(v * max_cost, max_cost),
                    }}
                  />
                ))}
              </div>
              <span style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>
                High ({formatCurrency(max_cost, { compact: true })})
              </span>
            </div>
          </div>

          {/* Date header row */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: `120px repeat(${dates.length}, 1fr)`,
              gap: "2px",
              marginBottom: "2px",
            }}
          >
            <div />
            {dates.map((d, di) => (
              <div
                key={d}
                style={{
                  fontSize: "9px",
                  color: di === peakDayIdx ? "var(--text-primary)" : "var(--text-tertiary)",
                  fontWeight: di === peakDayIdx ? 700 : 400,
                  textAlign: "center",
                  padding: "2px 0",
                }}
              >
                {formatDay(d)}
              </div>
            ))}
          </div>

          {/* Heatmap rows */}
          {matrix.map((row) => (
            <div
              key={row.team}
              style={{
                display: "grid",
                gridTemplateColumns: `120px repeat(${dates.length}, 1fr)`,
                gap: "2px",
                marginBottom: "2px",
              }}
            >
              <div
                style={{
                  fontSize: "12px",
                  color: "var(--text-secondary)",
                  fontWeight: 500,
                  display: "flex",
                  alignItems: "center",
                  paddingRight: "8px",
                  overflow: "hidden",
                  whiteSpace: "nowrap",
                  textOverflow: "ellipsis",
                }}
              >
                {row.team}
              </div>
              {row.values.map((val, di) => (
                <div
                  key={dates[di]}
                  title={`${row.team} · ${dates[di]}: ${formatCurrency(val)}`}
                  style={{
                    height: "24px",
                    borderRadius: "3px",
                    backgroundColor: heatColor(val, max_cost),
                    cursor: val > 0 ? "pointer" : "default",
                    transition: "opacity 0.1s ease",
                  }}
                />
              ))}
            </div>
          ))}

          {/* Day totals row */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: `120px repeat(${dates.length}, 1fr)`,
              gap: "2px",
              marginTop: "8px",
              borderTop: "1px solid var(--border)",
              paddingTop: "8px",
            }}
          >
            <div style={{ fontSize: "10px", color: "var(--text-tertiary)", fontWeight: 600, display: "flex", alignItems: "center" }}>
              TOTAL
            </div>
            {dayTotals.map((total, di) => (
              <div
                key={dates[di]}
                style={{
                  fontSize: "8px",
                  color: di === peakDayIdx ? "var(--text-primary)" : "var(--text-tertiary)",
                  fontWeight: di === peakDayIdx ? 700 : 400,
                  textAlign: "center",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {total > 0 ? formatCurrency(total, { compact: true }) : ""}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Peak day callout */}
      {peakDay && dayTotals[peakDayIdx] > 0 && (
        <div style={{ marginTop: "20px" }}>
          <Card>
            <CardHeader>Peak Day</CardHeader>
            <div style={{ display: "flex", gap: "32px", flexWrap: "wrap" }}>
              <div>
                <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginBottom: "4px" }}>Date</div>
                <div className="font-mono" style={{ fontSize: "15px", fontWeight: 600, color: "var(--text-primary)" }}>
                  {peakDay}
                </div>
              </div>
              <div>
                <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginBottom: "4px" }}>Total Cost</div>
                <div className="font-mono" style={{ fontSize: "15px", fontWeight: 600, color: "var(--text-primary)" }}>
                  {formatCurrency(dayTotals[peakDayIdx] ?? 0)}
                </div>
              </div>
              <div>
                <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginBottom: "4px" }}>vs Monthly Avg/Day</div>
                <div
                  className="font-mono"
                  style={{
                    fontSize: "15px",
                    fontWeight: 600,
                    color: dayCount > 0 && (dayTotals[peakDayIdx] ?? 0) > totalCost / dayCount
                      ? "var(--status-critical)"
                      : "var(--status-healthy)",
                  }}
                >
                  {dayCount > 0
                    ? `+${(((dayTotals[peakDayIdx] ?? 0) - totalCost / dayCount) / (totalCost / dayCount) * 100).toFixed(1)}%`
                    : "—"}
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
