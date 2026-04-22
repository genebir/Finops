import Link from "next/link";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState } from "@/components/primitives/States";
import { ProviderBadge } from "@/components/status/SeverityBadge";
import { API_BASE } from "@/lib/api";
import { formatCurrency } from "@/lib/formatters";
import { getT } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";

interface MonthlyPoint { billing_month: string; total_cost: number; resource_count: number }
interface TeamRow { team: string; cost: number; pct: number; resource_count: number }
interface ProviderRow { provider: string; cost: number; pct: number }
interface EnvRow { env: string; cost: number; pct: number }
interface ResourceRow { resource_id: string; resource_name: string | null; team: string; env: string; cost: number }
interface Summary { curr_cost: number; prev_cost: number; mom_change_pct: number | null; resource_count: number; team_count: number }
interface ServiceDetailData {
  service_name: string;
  latest_month: string;
  monthly_trend: MonthlyPoint[];
  by_team: TeamRow[];
  by_provider: ProviderRow[];
  by_env: EnvRow[];
  top_resources: ResourceRow[];
  summary: Summary;
}

async function fetchServiceDetail(service: string): Promise<ServiceDetailData> {
  const res = await fetch(`${API_BASE}/api/services/${encodeURIComponent(service)}?months=6`, {
    cache: "no-store",
  });
  if (!res.ok) {
    if (res.status === 404) throw new Error(`Service "${service}" not found`);
    throw new Error(`API ${res.status}`);
  }
  return res.json();
}

function TrendBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div style={{ width: "100%", height: "6px", backgroundColor: "var(--border)", borderRadius: "3px", overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, height: "100%", backgroundColor: "var(--provider-gcp)", borderRadius: "3px" }} />
    </div>
  );
}

export default async function ServiceDetailPage({ params }: { params: { service: string } }) {
  const serviceName = decodeURIComponent(params.service);
  const t = getT();

  let data: ServiceDetailData;
  try {
    data = await fetchServiceDetail(serviceName);
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { summary, monthly_trend, by_team, by_env, by_provider, top_resources, latest_month } = data;
  const maxTrend = Math.max(...monthly_trend.map((m) => m.total_cost), 1);
  const isUp = summary.mom_change_pct !== null && summary.mom_change_pct > 0;

  return (
    <div style={{ maxWidth: "1200px" }}>
      <div style={{ marginBottom: "8px" }}>
        <Link
          href="/services"
          style={{ fontSize: "12px", color: "var(--text-tertiary)", textDecoration: "none" }}
        >
          {t("action.back_to")} {t("nav.services")}
        </Link>
      </div>

      <PageHeader
        title={serviceName}
        description={`${t("page.service_detail.desc")} — ${latest_month}`}
      />

      {/* KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "16px", marginBottom: "32px" }}>
        <MetricCard
          label={`${t("th.cost")} (${latest_month})`}
          value={formatCurrency(summary.curr_cost, { compact: true })}
        />
        <MetricCard
          label={t("label.mom_change")}
          value={
            summary.mom_change_pct !== null
              ? `${isUp ? "+" : ""}${summary.mom_change_pct.toFixed(1)}%`
              : "—"
          }
          valueColor={
            summary.mom_change_pct === null
              ? "var(--text-secondary)"
              : isUp
              ? "var(--status-critical)"
              : "var(--status-healthy)"
          }
        />
        <MetricCard
          label={t("label.resources")}
          value={String(summary.resource_count)}
          sub={t("misc.this_month")}
        />
        <MetricCard
          label={t("label.team_count")}
          value={String(summary.team_count)}
        />
      </div>

      {/* Row 1: Trend + breakdown */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: "20px", marginBottom: "20px" }}>
        {/* Monthly trend */}
        <Card>
          <CardHeader>{t("section.recent_trend")}</CardHeader>
          {monthly_trend.length === 0 ? (
            <p style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>{t("misc.no_trend_data")}</p>
          ) : (
            <div>
              <div style={{ display: "flex", alignItems: "flex-end", gap: "6px", height: "80px", marginBottom: "8px" }}>
                {monthly_trend.map((m) => {
                  const pct = (m.total_cost / maxTrend) * 100;
                  return (
                    <div key={m.billing_month} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "4px" }}>
                      <div style={{ width: "100%", height: "70px", display: "flex", alignItems: "flex-end" }}>
                        <div style={{
                          width: "100%",
                          height: `${pct}%`,
                          minHeight: "2px",
                          backgroundColor: "var(--provider-gcp)",
                          borderRadius: "2px 2px 0 0",
                        }} />
                      </div>
                      <span style={{ fontSize: "9px", color: "var(--text-tertiary)" }}>
                        {m.billing_month.slice(5)}
                      </span>
                    </div>
                  );
                })}
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
                Latest: <span className="font-mono" style={{ fontWeight: 600, color: "var(--text-primary)" }}>
                  {formatCurrency(summary.curr_cost)}
                </span>
              </div>
            </div>
          )}
        </Card>

        {/* By env */}
        <Card>
          <CardHeader>{t("section.by_env")}</CardHeader>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {by_env.map((e) => (
              <div key={e.env}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                  <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: 500 }}>{e.env}</span>
                  <span className="font-mono" style={{ fontSize: "12px", color: "var(--text-primary)" }}>
                    {e.pct.toFixed(1)}%
                  </span>
                </div>
                <TrendBar value={e.cost} max={by_env[0]?.cost ?? 1} />
              </div>
            ))}
          </div>
        </Card>

        {/* By provider */}
        <Card>
          <CardHeader>{t("section.by_provider")}</CardHeader>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {by_provider.map((p) => (
              <div key={p.provider}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <ProviderBadge provider={p.provider as "aws" | "gcp" | "azure"} />
                  <span className="font-mono" style={{ fontSize: "12px", color: "var(--text-primary)" }}>
                    {p.pct.toFixed(1)}%
                  </span>
                </div>
                <TrendBar value={p.cost} max={by_provider[0]?.cost ?? 1} />
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Row 2: Teams + Resources */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: "20px" }}>
        {/* By team */}
        <Card>
          <CardHeader>{t("section.by_team")}</CardHeader>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {[t("th.team"), t("th.cost"), t("th.share")].map((h, idx, arr) => (
                  <th
                    key={h}
                    style={{
                      textAlign: idx > 0 ? "right" : "left",
                      fontSize: "10px",
                      fontWeight: 600,
                      fontFamily: "Inter, sans-serif",
                      color: "var(--text-tertiary)",
                      letterSpacing: "0.07em",
                      textTransform: "uppercase",
                      padding: idx === 0 ? "0 8px 12px 0" : idx === arr.length - 1 ? "0 0 12px 8px" : "0 8px 12px 8px",
                      borderBottom: "1px solid var(--border)",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {by_team.map((row, i) => (
                <tr key={row.team} style={{ borderBottom: i < by_team.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <td style={{ padding: "10px 8px 10px 0", fontSize: "12px" }}>
                    <Link href={`/teams/${encodeURIComponent(row.team)}`} style={{ textDecoration: "none", color: "var(--text-primary)", fontWeight: 600 }}>
                      {row.team}
                    </Link>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "12px", color: "var(--text-primary)" }}>
                      {formatCurrency(row.cost, { compact: true })}
                    </span>
                  </td>
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "right" }}>
                    <span style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>{row.pct.toFixed(1)}%</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        {/* Top resources */}
        <Card>
          <CardHeader>{t("section.top_resources")}</CardHeader>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {[t("th.resource"), t("th.team"), t("th.cost")].map((h, idx, arr) => (
                  <th
                    key={h}
                    style={{
                      textAlign: h === t("th.cost") ? "right" : "left",
                      fontSize: "10px",
                      fontWeight: 600,
                      fontFamily: "Inter, sans-serif",
                      color: "var(--text-tertiary)",
                      letterSpacing: "0.07em",
                      textTransform: "uppercase",
                      padding: idx === 0 ? "0 8px 12px 0" : idx === arr.length - 1 ? "0 0 12px 8px" : "0 8px 12px 8px",
                      borderBottom: "1px solid var(--border)",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {top_resources.map((r, i) => (
                <tr key={r.resource_id} style={{ borderBottom: i < top_resources.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <td style={{ padding: "10px 8px 10px 0" }}>
                    <Link
                      href={`/resources/${encodeURIComponent(r.resource_id)}`}
                      style={{ textDecoration: "none" }}
                    >
                      <code className="font-mono" style={{ fontSize: "11px", color: "var(--text-primary)" }}>
                        {r.resource_name ?? r.resource_id}
                      </code>
                    </Link>
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "12px", color: "var(--text-secondary)" }}>
                    {r.team}
                  </td>
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "12px", color: "var(--text-primary)" }}>
                      {formatCurrency(r.cost, { compact: true })}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  );
}
