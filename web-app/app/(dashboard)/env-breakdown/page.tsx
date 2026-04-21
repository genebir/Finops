import { API_BASE } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState } from "@/components/primitives/States";

interface EnvRow {
  env: string;
  cost: number;
  pct: number;
  resource_count: number;
  team_count: number;
}

interface CrossTabRow {
  env: string;
  by_team: Record<string, number>;
}

interface EnvBreakdownData {
  billing_month: string;
  grand_total: number;
  envs: EnvRow[];
  cross_tab: CrossTabRow[];
}

async function fetchEnvBreakdown(): Promise<EnvBreakdownData> {
  const res = await fetch(`${API_BASE}/api/env-breakdown`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error("Failed to fetch env-breakdown");
  return res.json();
}

function PctBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <div style={{ flex: 1, height: "6px", borderRadius: "3px", backgroundColor: "var(--border)", overflow: "hidden" }}>
        <div style={{ width: `${Math.min(pct, 100)}%`, height: "100%", backgroundColor: color, borderRadius: "3px" }} />
      </div>
      <span style={{ fontSize: "12px", color: "var(--text-secondary)", width: "38px", textAlign: "right" }}>
        {pct.toFixed(1)}%
      </span>
    </div>
  );
}

const ENV_COLORS: Record<string, string> = {
  prod:    "#D97757",
  staging: "#8E7BB5",
  dev:     "#5B9BD5",
  test:    "#6BAD8A",
};

function envColor(env: string) {
  return ENV_COLORS[env] ?? "#9B9590";
}

const envTableHeaders = ["Environment", "Cost", "Resources", "Teams", "Share"];

export default async function EnvBreakdownPage() {
  let data: EnvBreakdownData;
  try {
    data = await fetchEnvBreakdown();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const allTeams = Array.from(
    new Set(data.cross_tab.flatMap((r) => Object.keys(r.by_team)))
  ).sort();

  const crossTabMap = Object.fromEntries(
    data.cross_tab.map((r) => [r.env, r.by_team])
  );

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title="Env Breakdown"
        description={`${data.billing_month} — environment × team cost matrix`}
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "16px", marginBottom: "32px" }}>
        <MetricCard
          label="Total Cost"
          value={`$${data.grand_total.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
        />
        <MetricCard label="Environments" value={String(data.envs.length)} />
        <MetricCard
          label="Total Resources"
          value={data.envs.reduce((s, e) => s + e.resource_count, 0).toLocaleString()}
        />
        <MetricCard label="Teams Represented" value={String(allTeams.length)} />
      </div>

      <Card style={{ marginBottom: "24px" }}>
        <CardHeader>Cost by Environment</CardHeader>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {envTableHeaders.map((h, idx, arr) => (
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
            {data.envs.map((env, i, arr) => (
              <tr key={env.env} style={{ borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}>
                <td style={{ padding: "10px 0" }}>
                  <span style={{
                    display: "inline-block", padding: "2px 8px", borderRadius: "4px",
                    fontSize: "12px", fontWeight: 600,
                    backgroundColor: `${envColor(env.env)}22`,
                    color: envColor(env.env),
                  }}>
                    {env.env}
                  </span>
                </td>
                <td style={{ padding: "10px 8px" }}>
                  <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-primary)" }}>
                    ${env.cost.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                  </span>
                </td>
                <td style={{ padding: "10px 8px", fontSize: "13px", color: "var(--text-secondary)" }}>
                  {env.resource_count.toLocaleString()}
                </td>
                <td style={{ padding: "10px 8px", fontSize: "13px", color: "var(--text-secondary)" }}>
                  {env.team_count}
                </td>
                <td style={{ padding: "10px 0 10px 8px", minWidth: "160px" }}>
                  <PctBar pct={env.pct} color={envColor(env.env)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card style={{ overflowX: "auto" }}>
        <CardHeader>Cost Matrix — Environment × Team</CardHeader>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: "600px" }}>
          <thead>
            <tr>
              <th style={{
                textAlign: "left", fontSize: "10px", fontWeight: 600, fontFamily: "Inter, sans-serif",
                color: "var(--text-tertiary)", letterSpacing: "0.07em", textTransform: "uppercase",
                padding: "0 8px 12px 0", borderBottom: "1px solid var(--border)",
              }}>
                Env
              </th>
              {allTeams.map((t, idx, arr) => (
                <th key={t} style={{
                  textAlign: "right", fontSize: "10px", fontWeight: 600, fontFamily: "Inter, sans-serif",
                  color: "var(--text-tertiary)", letterSpacing: "0.07em", textTransform: "uppercase",
                  padding: idx === arr.length - 1 ? "0 0 12px 8px" : "0 8px 12px 8px",
                  borderBottom: "1px solid var(--border)",
                }}>
                  {t}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.envs.map((env, i, envArr) => (
              <tr key={env.env} style={{ borderBottom: i < envArr.length - 1 ? "1px solid var(--border)" : "none" }}>
                <td style={{ padding: "10px 8px 10px 0" }}>
                  <span style={{
                    display: "inline-block", padding: "2px 8px", borderRadius: "4px",
                    fontSize: "12px", fontWeight: 600,
                    backgroundColor: `${envColor(env.env)}22`,
                    color: envColor(env.env),
                  }}>
                    {env.env}
                  </span>
                </td>
                {allTeams.map((t, tidx, tArr) => {
                  const cost = crossTabMap[env.env]?.[t];
                  return (
                    <td key={t} style={{
                      padding: tidx === tArr.length - 1 ? "10px 0 10px 8px" : "10px 8px",
                      textAlign: "right", fontSize: "13px",
                      color: cost ? "var(--text-primary)" : "var(--text-tertiary)",
                    }}>
                      <span className="font-mono">
                        {cost ? `$${cost.toLocaleString("en-US", { maximumFractionDigits: 0 })}` : "—"}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
