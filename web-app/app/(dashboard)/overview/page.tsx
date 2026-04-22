import Link from "next/link";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState } from "@/components/primitives/States";
import { ProviderBadge } from "@/components/status/SeverityBadge";
import { api, API_BASE } from "@/lib/api";
import { formatCurrency } from "@/lib/formatters";
import { getT } from "@/lib/i18n/server";
import type { TopResource } from "@/lib/types";
import TeamCostBars from "./TeamCostBars";

export const dynamic = "force-dynamic";

export const metadata = { title: "Overview — FinOps" };

interface ProviderCost {
  provider: string;
  cost: number;
  pct: number;
}

interface TrendPoint {
  billing_month: string;
  total_cost: number;
}

async function fetchProviderCosts(): Promise<ProviderCost[]> {
  try {
    const res = await fetch(`${API_BASE}/api/cost-explorer`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    return data.by_provider ?? [];
  } catch {
    return [];
  }
}

async function fetchRecentTrend(): Promise<TrendPoint[]> {
  try {
    const res = await fetch(`${API_BASE}/api/cost-trend?months=6`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    return data.series ?? [];
  } catch {
    return [];
  }
}

const PROVIDER_COLORS: Record<string, string> = {
  aws: "var(--provider-aws)",
  gcp: "var(--provider-gcp)",
  azure: "var(--provider-azure)",
};

export default async function OverviewPage() {
  const t = getT();
  let data;
  try {
    data = await api.overview();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const [providerCosts, trendSeries] = await Promise.all([
    fetchProviderCosts(),
    fetchRecentTrend(),
  ]);

  const maxTrend = Math.max(...trendSeries.map((s) => s.total_cost), 1);

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={t("page.overview.title")}
        description={`${data.period_start} – ${data.period_end}`}
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
          label={t("label.total_cost_mtd")}
          value={formatCurrency(data.total_cost, { compact: true })}
          sub={`${data.active_days} days`}
        />
        <MetricCard
          label={t("label.resources")}
          value={String(data.resource_count)}
        />
        <MetricCard
          label={t("label.anomalies_detected")}
          value={String(data.anomaly_count)}
          valueColor={data.anomaly_count > 0 ? "var(--status-critical)" : "var(--status-healthy)"}
        />
        <MetricCard
          label={t("label.teams_with_spend")}
          value={String(data.cost_by_team.length)}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "20px", marginBottom: "20px" }}>
        <Card>
          <CardHeader>{t("section.cost_by_team")}</CardHeader>
          <TeamCostBars items={data.cost_by_team} />
        </Card>

        <Card>
          <CardHeader>{t("section.by_cloud_provider")}</CardHeader>
          {providerCosts.length === 0 ? (
            <p style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>
              {t("misc.no_provider_data")}
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {providerCosts.map((p) => (
                <div key={p.provider}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                    <ProviderBadge provider={p.provider as "aws" | "gcp" | "azure"} />
                    <div style={{ textAlign: "right" }}>
                      <span className="font-mono" style={{ fontSize: "14px", fontWeight: 600, color: "var(--text-primary)" }}>
                        <span className="currency-symbol">$</span>
                        {Math.round(p.cost).toLocaleString("en-US")}
                      </span>
                      <span style={{ fontSize: "11px", color: "var(--text-tertiary)", marginLeft: "6px" }}>
                        {p.pct.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <div style={{ height: "6px", backgroundColor: "var(--border)", borderRadius: "3px", overflow: "hidden" }}>
                    <div style={{
                      width: `${p.pct}%`,
                      height: "100%",
                      backgroundColor: PROVIDER_COLORS[p.provider] ?? "var(--text-tertiary)",
                      borderRadius: "3px",
                    }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "3fr 2fr", gap: "20px" }}>
        <Card>
          <CardHeader>{t("section.top_resources")}</CardHeader>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {([
                  { key: "th.resource", align: "left" },
                  { key: "th.service", align: "left" },
                  { key: "th.team", align: "center" },
                  { key: "th.cost", align: "right" },
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
              {data.top_resources.map((r: TopResource, i: number) => (
                <tr
                  key={r.resource_id}
                  style={{
                    borderBottom:
                      i < data.top_resources.length - 1
                        ? "1px solid var(--border)"
                        : "none",
                  }}
                >
                  <td style={{ padding: "10px 8px 10px 0" }}>
                    <Link
                      href={`/resources/${encodeURIComponent(r.resource_id)}`}
                      style={{ textDecoration: "none" }}
                    >
                      <code
                        className="font-mono"
                        style={{ fontSize: "11px", color: "var(--text-primary)" }}
                      >
                        {r.resource_name ?? r.resource_id}
                      </code>
                    </Link>
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "12px", color: "var(--text-secondary)" }}>
                    {r.service_name}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center", fontSize: "12px", color: "var(--text-secondary)" }}>
                    {r.team}
                  </td>
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "right" }}>
                    <span
                      className="font-mono"
                      style={{ fontSize: "12px", fontWeight: 500, color: "var(--text-primary)" }}
                    >
                      <span className="currency-symbol">$</span>
                      {Math.round(r.cost).toLocaleString("en-US")}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        <Card>
          <CardHeader>{t("section.recent_trend")}</CardHeader>
          {trendSeries.length === 0 ? (
            <p style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>
              {t("misc.run_asset_hint")}
            </p>
          ) : (
            <div>
              <div style={{ display: "flex", alignItems: "flex-end", gap: "6px", height: "80px", marginBottom: "8px" }}>
                {trendSeries.map((s) => {
                  const pct = (s.total_cost / maxTrend) * 100;
                  return (
                    <div key={s.billing_month} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "4px" }}>
                      <div style={{ width: "100%", height: "70px", display: "flex", alignItems: "flex-end" }}>
                        <div style={{
                          width: "100%",
                          height: `${pct}%`,
                          minHeight: "2px",
                          backgroundColor: "var(--provider-aws)",
                          borderRadius: "2px 2px 0 0",
                        }} />
                      </div>
                      <span style={{ fontSize: "9px", color: "var(--text-tertiary)", textAlign: "center" }}>
                        {s.billing_month.slice(5)}
                      </span>
                    </div>
                  );
                })}
              </div>
              <div style={{ borderTop: "1px solid var(--border)", paddingTop: "12px", marginTop: "4px" }}>
                {trendSeries.length >= 2 && (() => {
                  const last = trendSeries[trendSeries.length - 1];
                  const prev = trendSeries[trendSeries.length - 2];
                  const change = prev.total_cost > 0
                    ? ((last.total_cost - prev.total_cost) / prev.total_cost * 100)
                    : 0;
                  const isUp = change > 0;
                  return (
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                        Latest: <span className="font-mono" style={{ fontWeight: 600, color: "var(--text-primary)" }}>
                          ${Math.round(last.total_cost).toLocaleString("en-US")}
                        </span>
                      </span>
                      <span style={{
                        fontSize: "11px",
                        fontWeight: 600,
                        padding: "2px 8px",
                        borderRadius: "var(--radius-full)",
                        color: isUp ? "var(--status-critical)" : "var(--status-healthy)",
                        background: `color-mix(in srgb, ${isUp ? "var(--status-critical)" : "var(--status-healthy)"} 15%, transparent)`,
                      }}>
                        {isUp ? "+" : ""}{change.toFixed(1)}% MoM
                      </span>
                    </div>
                  );
                })()}
              </div>
              <div style={{ marginTop: "12px" }}>
                <Link
                  href="/cost-trend"
                  style={{
                    fontSize: "12px",
                    color: "var(--text-secondary)",
                    textDecoration: "none",
                    fontWeight: 500,
                  }}
                >
                  {t("action.view_full_trend")}
                </Link>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
