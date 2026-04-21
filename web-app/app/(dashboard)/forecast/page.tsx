import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader, SectionLabel } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { EmptyState, ErrorState } from "@/components/primitives/States";
import { api } from "@/lib/api";
import { formatCurrency, formatPct } from "@/lib/formatters";
import type { ForecastItem } from "@/lib/types";

function VarianceText({ pct }: { pct: number | null }) {
  if (pct === null)
    return <span style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>—</span>;
  const color =
    pct > 20
      ? "var(--status-critical)"
      : pct < -20
      ? "var(--status-under)"
      : "var(--status-healthy)";
  return (
    <span className="font-mono" style={{ fontSize: "12px", fontWeight: 600, color }}>
      {pct > 0 ? "+" : ""}
      {pct.toFixed(1)}%
    </span>
  );
}

function SourceTag({ source }: { source: string }) {
  const map: Record<string, { color: string; bg: string }> = {
    infracost: { color: "var(--provider-aws)", bg: "rgba(217,119,87,0.1)" },
    prophet:   { color: "var(--provider-azure)", bg: "rgba(139,127,184,0.1)" },
  };
  const { color, bg } = map[source] ?? { color: "var(--text-tertiary)", bg: "rgba(168,159,148,0.1)" };
  return (
    <span
      style={{
        fontSize: "10px",
        fontWeight: 600,
        fontFamily: "Inter, sans-serif",
        letterSpacing: "0.05em",
        color,
        background: bg,
        border: `1px solid ${color}`,
        borderRadius: "var(--radius-full)",
        padding: "2px 8px",
        opacity: 0.9,
      }}
    >
      {source}
    </span>
  );
}

export default async function ForecastPage() {
  let data;
  try { data = await api.forecast(); }
  catch (e) { return <ErrorState message={String(e)} />; }

  const variance =
    data.total_forecast > 0
      ? ((data.total_actual - data.total_forecast) / data.total_forecast) * 100
      : 0;

  return (
    <div style={{ maxWidth: "1100px" }}>
      <PageHeader
        title="Forecast"
        description="Forecast vs. actual cost variance analysis"
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
          label="Total Forecast"
          value={formatCurrency(data.total_forecast, { compact: true })}
        />
        <MetricCard
          label="Actual Spend"
          value={formatCurrency(data.total_actual, { compact: true })}
        />
        <MetricCard
          label="Variance"
          value={`${variance > 0 ? "+" : ""}${variance.toFixed(1)}%`}
          valueColor={
            Math.abs(variance) >= 20
              ? variance > 0
                ? "var(--status-critical)"
                : "var(--status-under)"
              : "var(--status-healthy)"
          }
        />
      </div>

      <Card>
        <CardHeader>Forecast vs. Actual by Resource</CardHeader>
        {data.items.length === 0 ? (
          <EmptyState
            title="No forecast data"
            description="Run the infracost_forecast or prophet_forecast asset in Dagster."
          />
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Resource", "Source", "Forecast", "Actual", "Variance", "Range"].map((h, idx, arr) => (
                  <th
                    key={h}
                    style={{
                      textAlign: ["Forecast", "Actual", "Variance"].includes(h) ? "right" : h === "Source" ? "center" : "left",
                      fontSize: "10px",
                      fontWeight: 600,
                      fontFamily: "Inter, sans-serif",
                      color: "var(--text-tertiary)",
                      letterSpacing: "0.07em",
                      textTransform: "uppercase",
                      padding: idx === 0
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
              {data.items.map((item: ForecastItem, i: number) => (
                <tr
                  key={i}
                  style={{
                    borderBottom: i < data.items.length - 1 ? "1px solid var(--border)" : "none",
                  }}
                >
                  <td style={{ padding: "10px 0" }}>
                    <code className="font-mono" style={{ fontSize: "11px" }}>
                      {item.resource_id}
                    </code>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center" }}>
                    <SourceTag source={item.source} />
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "12px" }}>
                      <span className="currency-symbol">$</span>
                      {Math.round(item.monthly_forecast).toLocaleString("en-US")}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    {item.actual_cost != null ? (
                      <span className="font-mono" style={{ fontSize: "12px" }}>
                        <span className="currency-symbol">$</span>
                        {Math.round(item.actual_cost).toLocaleString("en-US")}
                      </span>
                    ) : (
                      <span style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>—</span>
                    )}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <VarianceText pct={item.variance_pct} />
                  </td>
                  <td style={{ padding: "10px 0 10px 8px", fontSize: "11px", color: "var(--text-tertiary)" }}>
                    <span className="font-mono">
                      <span className="currency-symbol">$</span>
                      {Math.round(item.lower_bound).toLocaleString("en-US")}
                      {" – "}
                      <span className="currency-symbol">$</span>
                      {Math.round(item.upper_bound).toLocaleString("en-US")}
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
