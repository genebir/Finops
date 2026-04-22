import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { EmptyState, ErrorState } from "@/components/primitives/States";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { api } from "@/lib/api";
import { getT } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";

export const metadata = { title: "Anomalies — FinOps" };

export default async function AnomaliesPage() {
  const t = getT();
  let data;
  try { data = await api.anomalies(); }
  catch (e) { return <ErrorState message={String(e)} />; }

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={t("page.anomalies.title")}
        description={t("page.anomalies.desc")}
      />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "16px",
          marginBottom: "32px",
        }}
      >
        <MetricCard label={t("label.total_anomalies")} value={String(data.total)} />
        <MetricCard
          label={t("label.critical")}
          value={String(data.critical)}
          valueColor={data.critical > 0 ? "var(--status-critical)" : "var(--text-primary)"}
        />
        <MetricCard
          label={t("label.warning")}
          value={String(data.warning)}
          valueColor={data.warning > 0 ? "var(--status-warning)" : "var(--text-primary)"}
        />
      </div>

      <Card>
        <CardHeader>{t("section.anomaly_events")}</CardHeader>
        {data.items.length === 0 ? (
          <EmptyState
            title={t("empty.no_anomaly")}
            description={t("empty.run_anomaly")}
          />
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {([
                  { key: "th.resource", align: "left" },
                  { key: "th.team", align: "left" },
                  { key: "th.env", align: "center" },
                  { key: "th.date", align: "center" },
                  { key: "th.cost", align: "right" },
                  { key: "th.z_score", align: "right" },
                  { key: "th.severity", align: "center" },
                  { key: "th.detector", align: "center" },
                ] as const).map((col, idx, arr) => (
                  <th
                    key={col.key}
                    style={{
                      textAlign: col.align,
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
                    {t(col.key)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.items.map((item, i) => (
                <tr
                  key={i}
                  style={{
                    borderBottom: i < data.items.length - 1 ? "1px solid var(--border)" : "none",
                  }}
                >
                  <td style={{ padding: "10px 0" }}>
                    <code
                      className="font-mono"
                      style={{ fontSize: "11px", color: "var(--text-primary)" }}
                    >
                      {item.resource_id}
                    </code>
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "12px", color: "var(--text-secondary)" }}>
                    {item.team}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center" }}>
                    <SeverityBadge severity={item.env} />
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center", fontSize: "12px", color: "var(--text-secondary)" }}>
                    {item.charge_date}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "12px" }}>
                      <span className="currency-symbol">$</span>
                      {item.effective_cost.toFixed(2)}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                      {item.z_score.toFixed(2)}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center" }}>
                    <SeverityBadge severity={item.severity} />
                  </td>
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "center", fontSize: "11px", color: "var(--text-tertiary)" }}>
                    {item.detector_name}
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
