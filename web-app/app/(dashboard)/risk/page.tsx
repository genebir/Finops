import { API_BASE } from "../../../lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState, EmptyState } from "@/components/primitives/States";
import { getT } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";
export const metadata = { title: "Cost Risk — FinOps" };

interface RiskItem {
  resource_id: string; team: string; env: string; provider: string;
  service_name: string; total_cost: number; anomaly_count: number; risk_score: number;
}
interface RiskData {
  billing_month: string;
  items: RiskItem[];
  summary: { total_resources: number; total_cost: number; total_anomalies: number; has_anomaly_data: boolean };
}

const PROV_COLOR: Record<string, string> = {
  aws:   "var(--provider-aws)",
  gcp:   "var(--provider-gcp)",
  azure: "var(--provider-azure)",
};

function RiskBar({ score }: { score: number }) {
  const pct = Math.min(score * 100, 100);
  const color = pct > 60
    ? "var(--status-critical)"
    : pct > 30
    ? "var(--status-warning)"
    : "var(--status-healthy)";
  return (
    <div style={{ height: "6px", background: "var(--border)", borderRadius: "3px", overflow: "hidden", minWidth: "80px" }}>
      <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: "3px" }} />
    </div>
  );
}

async function fetchRisk(): Promise<RiskData> {
  const res = await fetch(`${API_BASE}/api/cost-risk?min_anomaly_count=0&limit=50`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error("Failed to load risk data");
  return res.json();
}

export default async function RiskPage() {
  const t = getT();
  let data: RiskData;
  try {
    data = await fetchRisk();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { summary, items, billing_month } = data;
  const topRisk = items.filter((i) => i.risk_score > 0).slice(0, 3);

  const HEADERS = [
    { key: "th.resource", align: "left" },
    { key: "th.team", align: "left" },
    { key: "th.provider", align: "center" },
    { key: "th.service", align: "left" },
    { key: "th.cost", align: "right" },
    { key: "th.anomalies", align: "center" },
    { key: "th.risk_score", align: "left" },
  ] as const;

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={t("page.risk.title")}
        description={`${billing_month}`}
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: "16px", marginBottom: "32px" }}>
        <MetricCard label={t("label.resources")} value={String(summary.total_resources)} />
        <MetricCard
          label={t("label.total_cost")}
          value={`$${summary.total_cost.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
        />
        <MetricCard
          label={t("label.anomaly_events")}
          value={String(summary.total_anomalies)}
          valueColor={summary.total_anomalies > 0 ? "var(--status-critical)" : undefined}
        />
      </div>

      {topRisk.length > 0 && (
        <div style={{
          background: "color-mix(in srgb, var(--status-critical) 8%, transparent)",
          border: "1px solid color-mix(in srgb, var(--status-critical) 30%, transparent)",
          borderRadius: "var(--radius-card)",
          padding: "16px 20px",
          marginBottom: "20px",
        }}>
          <div style={{ fontSize: "10px", fontWeight: 600, fontFamily: "Inter, sans-serif", color: "var(--status-critical)", letterSpacing: "0.07em", textTransform: "uppercase", marginBottom: "8px" }}>
            {t("section.high_risk")}
          </div>
          <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
            {topRisk.map((item) => (
              <div key={item.resource_id} style={{ fontSize: "12px", color: "var(--text-primary)" }}>
                <span style={{ fontWeight: 600 }}>{item.resource_id}</span>
                <span style={{ color: "var(--text-secondary)", marginLeft: "6px" }}>
                  ${item.total_cost.toFixed(0)} · {item.anomaly_count} {t("th.anomalies").toLowerCase()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <Card>
        <CardHeader>{t("section.all_by_risk")}</CardHeader>
        {items.length === 0 ? (
          <EmptyState title={t("empty.no_risk")} description={t("empty.run_anomaly")} />
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {HEADERS.map((col, idx, arr) => (
                  <th key={col.key} style={{
                    textAlign: col.align,
                    fontSize: "10px",
                    fontWeight: 600,
                    fontFamily: "Inter, sans-serif",
                    color: "var(--text-tertiary)",
                    letterSpacing: "0.07em",
                    textTransform: "uppercase",
                    padding: idx === 0 ? "0 8px 12px 0" : idx === arr.length - 1 ? "0 0 12px 8px" : "0 8px 12px 8px",
                    borderBottom: "1px solid var(--border)",
                  }}>
                    {t(col.key)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item, idx, arr) => (
                <tr key={idx} style={{ borderBottom: idx < arr.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <td style={{ padding: "10px 0" }}>
                    <div style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: "12px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "200px" }}>
                      {item.resource_id}
                    </div>
                    <div style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>{item.env}</div>
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "13px", color: "var(--text-secondary)" }}>{item.team}</td>
                  <td style={{ padding: "10px 8px", textAlign: "center" }}>
                    <span style={{ fontSize: "11px", fontWeight: 700, color: PROV_COLOR[item.provider] ?? "var(--text-secondary)" }}>
                      {item.provider.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "12px", color: "var(--text-secondary)" }}>{item.service_name}</td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-primary)" }}>
                      ${item.total_cost.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center", color: item.anomaly_count > 0 ? "var(--status-critical)" : "var(--text-tertiary)", fontWeight: item.anomaly_count > 0 ? 700 : 400, fontSize: "13px" }}>
                    {item.anomaly_count}
                  </td>
                  <td style={{ padding: "10px 0 10px 8px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <RiskBar score={item.risk_score} />
                      <span className="font-mono" style={{ fontSize: "11px", color: "var(--text-tertiary)", minWidth: "36px" }}>
                        {(item.risk_score * 100).toFixed(0)}
                      </span>
                    </div>
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
