import { API_BASE } from "../../../lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState } from "@/components/primitives/States";
import { getT } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";
export const metadata = { title: "Cloud Compare — FinOps" };

interface ProviderStat {
  provider: string; total_cost: number; resource_count: number; pct: number;
}
interface SvcEntry { service: string; cost: number }
interface TrendEntry { month: string; cost: number }
interface TeamEntry { team: string; by_provider: Record<string, number>; total: number }

interface CloudCompareData {
  billing_month: string;
  grand_total: number;
  providers: ProviderStat[];
  top_services_by_provider: Record<string, SvcEntry[]>;
  trend_by_provider: Record<string, TrendEntry[]>;
  teams: TeamEntry[];
}

const PROVIDER_COLOR: Record<string, string> = {
  aws:   "var(--provider-aws)",
  gcp:   "var(--provider-gcp)",
  azure: "var(--provider-azure)",
};

const PROVIDER_COLOR_HEX: Record<string, string> = {
  aws:   "#d97757",
  gcp:   "#6b8cae",
  azure: "#8b7fb8",
};

async function fetchData(): Promise<CloudCompareData> {
  const res = await fetch(`${API_BASE}/api/cloud-compare`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error("Failed to load cloud comparison data");
  return res.json();
}

function Bar({ pct, color }: { pct: number; color: string }) {
  return (
    <div style={{ height: "8px", background: "var(--border)", borderRadius: "4px", overflow: "hidden" }}>
      <div
        style={{ height: "100%", width: `${Math.min(pct, 100)}%`, background: color, borderRadius: "4px", transition: "width 0.3s" }}
      />
    </div>
  );
}

export default async function CloudComparePage() {
  const t = getT();
  let data: CloudCompareData;
  try {
    data = await fetchData();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const providerList = ["aws", "gcp", "azure"];
  const crossTabHeaders = [t("th.team"), ...providerList.map((p) => p.toUpperCase()), t("th.total")];

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={t("page.cloud_compare.title")}
        description={`${data.billing_month} — ${t("page.cloud_compare.desc")}`}
      />

      {/* Provider KPI cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: "16px", marginBottom: "32px" }}>
        {data.providers.map((p) => {
          const cssColor = PROVIDER_COLOR[p.provider] ?? "var(--text-secondary)";
          const hexColor = PROVIDER_COLOR_HEX[p.provider] ?? "#9B9590";
          return (
            <Card key={p.provider} style={{ borderColor: `${hexColor}44` }}>
              <div style={{ fontSize: "10px", fontFamily: "Inter, sans-serif", fontWeight: 600, color: cssColor, letterSpacing: "0.07em", textTransform: "uppercase", marginBottom: "8px" }}>
                {p.provider.toUpperCase()}
              </div>
              <p className="font-mono" style={{ fontSize: "28px", fontWeight: 500, color: "var(--text-primary)", letterSpacing: "-0.02em", lineHeight: 1.1, marginBottom: "12px" }}>
                ${p.total_cost.toLocaleString("en-US", { maximumFractionDigits: 0 })}
              </p>
              <Bar pct={p.pct} color={cssColor} />
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: "6px", fontSize: "12px" }}>
                <span style={{ color: "var(--text-secondary)" }}>{p.pct.toFixed(1)}% of total</span>
                <span style={{ color: "var(--text-secondary)" }}>{p.resource_count} resources</span>
              </div>
            </Card>
          );
        })}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
        {/* Top services per provider */}
        <Card>
          <CardHeader>{t("section.top_services_by_provider")}</CardHeader>
          {providerList.map((prov) => {
            const svcs = data.top_services_by_provider[prov] ?? [];
            const cssColor = PROVIDER_COLOR[prov] ?? "var(--text-secondary)";
            return (
              <div key={prov} style={{ marginBottom: "16px" }}>
                <div style={{ fontSize: "10px", fontWeight: 600, fontFamily: "Inter, sans-serif", color: cssColor, letterSpacing: "0.07em", textTransform: "uppercase", marginBottom: "6px" }}>
                  {prov}
                </div>
                {svcs.length === 0 ? (
                  <div style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>No data</div>
                ) : (
                  svcs.map((s, i) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", padding: "4px 0", borderBottom: "1px solid var(--border)" }}>
                      <span style={{ color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "160px" }}>{s.service}</span>
                      <span className="font-mono" style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                        ${s.cost.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                      </span>
                    </div>
                  ))
                )}
              </div>
            );
          })}
        </Card>

        {/* Team breakdown */}
        <Card>
          <CardHeader>{t("section.top_team_breakdown")}</CardHeader>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {crossTabHeaders.map((h, idx, arr) => {
                  const isProvider = idx > 0 && idx < arr.length - 1;
                  const provKey = isProvider ? providerList[idx - 1] : null;
                  return (
                    <th key={h} style={{
                      textAlign: idx === 0 ? "left" : "right",
                      fontSize: "10px",
                      fontWeight: 600,
                      fontFamily: "Inter, sans-serif",
                      color: isProvider && provKey ? (PROVIDER_COLOR[provKey] ?? "var(--text-tertiary)") : "var(--text-tertiary)",
                      letterSpacing: "0.07em",
                      textTransform: "uppercase",
                      padding: idx === 0 ? "0 8px 12px 0" : idx === arr.length - 1 ? "0 0 12px 8px" : "0 8px 12px 8px",
                      borderBottom: "1px solid var(--border)",
                    }}>
                      {h}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {data.teams.slice(0, 8).map((t, i, arr) => (
                <tr key={t.team} style={{ borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <td style={{ padding: "10px 0", color: "var(--text-primary)", fontWeight: 500, fontSize: "13px" }}>{t.team}</td>
                  {providerList.map((p) => (
                    <td key={p} style={{ padding: "10px 8px", textAlign: "right", fontSize: "13px", color: "var(--text-secondary)" }}>
                      <span className="font-mono">
                        {t.by_provider[p] ? `$${t.by_provider[p].toLocaleString("en-US", { maximumFractionDigits: 0 })}` : "—"}
                      </span>
                    </td>
                  ))}
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "right", fontWeight: 600, color: "var(--text-primary)", fontSize: "13px" }}>
                    <span className="font-mono">
                      ${t.total.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      {/* Monthly trend */}
      <Card>
        <CardHeader>{t("section.monthly_trend_chart")}</CardHeader>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: "16px" }}>
          {providerList.map((prov) => {
            const trend = data.trend_by_provider[prov] ?? [];
            const cssColor = PROVIDER_COLOR[prov] ?? "var(--text-secondary)";
            const maxCost = Math.max(...trend.map((t) => t.cost), 1);
            return (
              <div key={prov}>
                <div style={{ fontSize: "10px", fontWeight: 600, fontFamily: "Inter, sans-serif", color: cssColor, letterSpacing: "0.07em", textTransform: "uppercase", marginBottom: "8px" }}>
                  {prov}
                </div>
                <div style={{ display: "flex", alignItems: "flex-end", gap: "3px", height: "60px" }}>
                  {trend.map((entry) => (
                    <div
                      key={entry.month}
                      title={`${entry.month}: $${entry.cost.toFixed(0)}`}
                      style={{ flex: 1, minWidth: "4px", borderRadius: "2px 2px 0 0", background: cssColor, opacity: 0.8, height: `${Math.round((entry.cost / maxCost) * 100)}%` }}
                    />
                  ))}
                  {trend.length === 0 && (
                    <span style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>No trend data</span>
                  )}
                </div>
                {trend.length > 0 && (
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: "4px", fontSize: "10px", color: "var(--text-tertiary)" }}>
                    <span>{trend[0].month}</span>
                    <span>{trend[trend.length - 1].month}</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
