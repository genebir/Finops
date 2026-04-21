import Link from "next/link";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState } from "@/components/primitives/States";
import { SeverityBadge, ProviderBadge } from "@/components/status/SeverityBadge";
import { API_BASE } from "@/lib/api";
import { formatCurrency } from "@/lib/formatters";

export const dynamic = "force-dynamic";

interface MonthlyPoint { billing_month: string; total_cost: number; resource_count: number }
interface ServiceRow { service_name: string; cost: number; pct: number; resource_count: number }
interface EnvRow { env: string; cost: number; pct: number }
interface ProviderRow { provider: string; cost: number; pct: number }
interface ResourceRow { resource_id: string; resource_name: string | null; service_name: string | null; env: string; cost: number }
interface AnomalyRow { resource_id: string; charge_date: string; severity: string; detector_name: string; effective_cost: number; z_score: number }
interface Summary { curr_cost: number; prev_cost: number; mom_change_pct: number | null; resource_count: number; anomaly_count: number }
interface TeamDetailData {
  team: string;
  latest_month: string;
  monthly_trend: MonthlyPoint[];
  by_service: ServiceRow[];
  by_env: EnvRow[];
  by_provider: ProviderRow[];
  top_resources: ResourceRow[];
  anomalies: AnomalyRow[];
  summary: Summary;
}

async function fetchTeamDetail(team: string): Promise<TeamDetailData> {
  const res = await fetch(`${API_BASE}/api/teams/${encodeURIComponent(team)}?months=6`, {
    cache: "no-store",
  });
  if (!res.ok) {
    if (res.status === 404) throw new Error(`Team "${team}" not found`);
    throw new Error(`API ${res.status}`);
  }
  return res.json();
}

function TrendBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div style={{ width: "100%", height: "6px", backgroundColor: "var(--border)", borderRadius: "3px", overflow: "hidden" }}>
      <div
        style={{
          width: `${pct}%`,
          height: "100%",
          backgroundColor: "var(--provider-aws)",
          borderRadius: "3px",
        }}
      />
    </div>
  );
}

export default async function TeamDetailPage({ params }: { params: { team: string } }) {
  const teamName = decodeURIComponent(params.team);

  let data: TeamDetailData;
  try {
    data = await fetchTeamDetail(teamName);
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { summary, monthly_trend, by_service, by_env, by_provider, top_resources, anomalies, latest_month } = data;
  const maxTrend = Math.max(...monthly_trend.map((m) => m.total_cost), 1);
  const isUp = summary.mom_change_pct !== null && summary.mom_change_pct > 0;

  return (
    <div style={{ maxWidth: "1200px" }}>
      <div style={{ marginBottom: "8px" }}>
        <Link
          href="/leaderboard"
          style={{ fontSize: "12px", color: "var(--text-tertiary)", textDecoration: "none" }}
        >
          ← Leaderboard
        </Link>
      </div>

      <PageHeader
        title={teamName}
        description={`Team detail — ${latest_month}`}
      />

      {/* KPIs */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "16px",
          marginBottom: "32px",
        }}
      >
        <MetricCard
          label={`Cost (${latest_month})`}
          value={formatCurrency(summary.curr_cost, { compact: true })}
        />
        <MetricCard
          label="MoM Change"
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
          label="Resources"
          value={String(top_resources.length)}
          sub="this month"
        />
        <MetricCard
          label="Anomalies"
          value={String(summary.anomaly_count)}
          valueColor={summary.anomaly_count > 0 ? "var(--status-critical)" : "var(--status-healthy)"}
        />
      </div>

      {/* Row 1: Trend + breakdown */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: "20px", marginBottom: "20px" }}>
        {/* Monthly trend */}
        <Card>
          <CardHeader>6-Month Trend</CardHeader>
          {monthly_trend.length === 0 ? (
            <p style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>No trend data.</p>
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
                          backgroundColor: "var(--provider-aws)",
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
          <CardHeader>By Environment</CardHeader>
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
          <CardHeader>By Provider</CardHeader>
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

      {/* Row 2: Services + Resources */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: "20px" }}>
        {/* Top services */}
        <Card>
          <CardHeader>Top Services</CardHeader>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Service", "Cost", "%"].map((h, idx, arr) => (
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
              {by_service.map((s, i) => (
                <tr key={s.service_name} style={{ borderBottom: i < by_service.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <td style={{ padding: "10px 8px 10px 0", fontSize: "12px", color: "var(--text-secondary)" }}>
                    {s.service_name}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "12px", color: "var(--text-primary)" }}>
                      {formatCurrency(s.cost, { compact: true })}
                    </span>
                  </td>
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "right" }}>
                    <span style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>{s.pct.toFixed(1)}%</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        {/* Top resources */}
        <Card>
          <CardHeader>Top Resources</CardHeader>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Resource", "Env", "Cost"].map((h, idx, arr) => (
                  <th
                    key={h}
                    style={{
                      textAlign: h === "Cost" ? "right" : "left",
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
                  <td style={{ padding: "10px 8px", textAlign: "center" }}>
                    <span style={{
                      fontSize: "10px",
                      fontWeight: 600,
                      padding: "2px 6px",
                      borderRadius: "var(--radius-full)",
                      backgroundColor: "var(--border)",
                      color: "var(--text-secondary)",
                    }}>
                      {r.env}
                    </span>
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

      {/* Anomalies */}
      {anomalies.length > 0 && (
        <Card>
          <CardHeader>Recent Anomalies</CardHeader>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Resource", "Date", "Severity", "Detector", "Cost", "Z-score"].map((h, idx, arr) => (
                  <th
                    key={h}
                    style={{
                      textAlign: h === "Severity" ? "center" : h === "Cost" || h === "Z-score" ? "right" : "left",
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
              {anomalies.map((a, i) => (
                <tr key={`${a.resource_id}-${a.charge_date}`} style={{ borderBottom: i < anomalies.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <td style={{ padding: "10px 8px 10px 0" }}>
                    <Link
                      href={`/resources/${encodeURIComponent(a.resource_id)}`}
                      style={{ textDecoration: "none" }}
                    >
                      <code className="font-mono" style={{ fontSize: "11px", color: "var(--text-primary)" }}>
                        {a.resource_id}
                      </code>
                    </Link>
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "12px", color: "var(--text-secondary)" }}>
                    {a.charge_date}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center" }}>
                    <SeverityBadge severity={a.severity as "critical" | "warning"} />
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "11px", color: "var(--text-tertiary)" }}>
                    {a.detector_name}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "12px", color: "var(--text-primary)" }}>
                      {formatCurrency(a.effective_cost, { compact: true })}
                    </span>
                  </td>
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "12px", color: a.severity === "critical" ? "var(--status-critical)" : "var(--status-warning)" }}>
                      {a.z_score.toFixed(2)}σ
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
