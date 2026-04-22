import { API_BASE } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader, SectionLabel } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState, EmptyState } from "@/components/primitives/States";
import { getT } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";

export const metadata = { title: "Showback — FinOps" };

interface TopItem {
  name: string;
  cost: number;
}

interface ShowbackTeam {
  team: string;
  total_cost: number;
  budget_amount: number | null;
  utilization_pct: number | null;
  anomaly_count: number;
  top_services: TopItem[];
  top_resources: TopItem[];
}

interface ShowbackData {
  billing_month: string;
  teams: ShowbackTeam[];
  total_cost: number;
  generated_at: string | null;
}

async function fetchShowback(): Promise<ShowbackData> {
  const res = await fetch(`${API_BASE}/api/showback`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch showback");
  return res.json();
}

function BudgetBar({ pct }: { pct: number }) {
  const color =
    pct >= 100
      ? "var(--status-critical)"
      : pct >= 80
      ? "var(--status-warning)"
      : "var(--status-healthy)";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <div
        style={{
          flex: 1,
          height: "6px",
          borderRadius: "3px",
          backgroundColor: "var(--border)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${Math.min(pct, 100)}%`,
            height: "100%",
            backgroundColor: color,
            borderRadius: "3px",
          }}
        />
      </div>
      <span
        className="font-mono"
        style={{ fontSize: "12px", color, width: "44px", textAlign: "right" }}
      >
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

const TEAM_HEADERS = [
  { key: "th.team", align: "left" },
  { key: "th.total_cost", align: "right" },
  { key: "th.budget", align: "right" },
  { key: "th.utilization", align: "right" },
  { key: "th.anomalies", align: "center" },
] as const;

export default async function ShowbackPage() {
  const t = getT();
  let data: ShowbackData;
  try {
    data = await fetchShowback();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { teams, billing_month, total_cost } = data;
  const totalAnomalies = teams.reduce((s, tm) => s + (tm.anomaly_count || 0), 0);
  const teamsOverBudget = teams.filter(
    (tm) => tm.utilization_pct !== null && tm.utilization_pct >= 100
  ).length;

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={t("page.showback.title")}
        description={`${billing_month} — ${t("page.showback.desc")}`}
        action={
          <a
            href={`${API_BASE}/api/showback/export?billing_month=${billing_month}`}
            style={{
              padding: "8px 16px",
              borderRadius: "var(--radius-button)",
              border: "1px solid var(--border)",
              fontSize: "13px",
              fontWeight: 600,
              color: "var(--text-secondary)",
              textDecoration: "none",
              background: "transparent",
            }}
          >
            {t("action.export_json")}
          </a>
        }
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "16px", marginBottom: "32px" }}>
        <MetricCard
          label={t("label.total_cost")}
          value={`$${Math.round(total_cost).toLocaleString("en-US")}`}
        />
        <MetricCard label={t("label.teams")} value={String(teams.length)} />
        <MetricCard
          label={t("label.over_budget")}
          value={String(teamsOverBudget)}
          valueColor={teamsOverBudget > 0 ? "var(--status-critical)" : undefined}
        />
        <MetricCard
          label={t("label.total_anomalies")}
          value={String(totalAnomalies)}
          valueColor={totalAnomalies > 0 ? "var(--status-warning)" : undefined}
        />
      </div>

      {teams.length === 0 ? (
        <EmptyState
          title={t("empty.no_showback")}
          description={t("empty.run_showback")}
        />
      ) : (
        <>
          {/* Summary table */}
          <Card style={{ marginBottom: "24px" }}>
            <CardHeader>{t("section.team_summary")}</CardHeader>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {TEAM_HEADERS.map((col, idx, arr) => (
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
                        padding:
                          idx === 0
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
                {teams.map((tm, i, arr) => (
                  <tr
                    key={tm.team}
                    style={{ borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}
                  >
                    <td style={{ padding: "10px 8px 10px 0", fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
                      {tm.team}
                    </td>
                    <td style={{ padding: "10px 8px", textAlign: "right" }}>
                      <span className="font-mono" style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-primary)" }}>
                        <span className="currency-symbol">$</span>
                        {Math.round(tm.total_cost).toLocaleString("en-US")}
                      </span>
                    </td>
                    <td style={{ padding: "10px 8px", textAlign: "right" }}>
                      {tm.budget_amount != null ? (
                        <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                          <span className="currency-symbol">$</span>
                          {Math.round(tm.budget_amount).toLocaleString("en-US")}
                        </span>
                      ) : (
                        <span style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>—</span>
                      )}
                    </td>
                    <td style={{ padding: "10px 8px", textAlign: "right", minWidth: "140px" }}>
                      {tm.utilization_pct != null ? (
                        <BudgetBar pct={tm.utilization_pct} />
                      ) : (
                        <span style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>—</span>
                      )}
                    </td>
                    <td style={{ padding: "10px 0 10px 8px", textAlign: "center" }}>
                      {tm.anomaly_count > 0 ? (
                        <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--status-warning)" }}>
                          {tm.anomaly_count}
                        </span>
                      ) : (
                        <span style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>0</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          {/* Per-team detail cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "16px" }}>
            {teams.map((tm) => (
              <Card key={tm.team}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
                  <div>
                    <div style={{ fontSize: "15px", fontWeight: 700, color: "var(--text-primary)", marginBottom: "2px" }}>
                      {tm.team}
                    </div>
                    <span className="font-mono" style={{ fontSize: "20px", fontWeight: 500, color: "var(--text-primary)" }}>
                      <span className="currency-symbol">$</span>
                      {Math.round(tm.total_cost).toLocaleString("en-US")}
                    </span>
                  </div>
                  {tm.anomaly_count > 0 && (
                    <span style={{
                      padding: "2px 8px",
                      borderRadius: "var(--radius-full)",
                      fontSize: "10px",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      color: "var(--status-warning)",
                      background: "color-mix(in srgb, var(--status-warning) 15%, transparent)",
                    }}>
                      {tm.anomaly_count} anomaly
                    </span>
                  )}
                </div>

                {tm.top_services.length > 0 && (
                  <div style={{ marginBottom: "12px" }}>
                    <SectionLabel>{t("section.top_services")}</SectionLabel>
                    {tm.top_services.slice(0, 3).map((svc) => (
                      <div key={svc.name} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: "12px" }}>
                        <span style={{ color: "var(--text-secondary)" }}>{svc.name}</span>
                        <span className="font-mono" style={{ color: "var(--text-primary)" }}>
                          ${Math.round(svc.cost).toLocaleString("en-US")}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {tm.top_resources.length > 0 && (
                  <div>
                    <SectionLabel>{t("section.top_resources")}</SectionLabel>
                    {tm.top_resources.slice(0, 3).map((res) => (
                      <div key={res.name} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: "12px" }}>
                        <code className="font-mono" style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                          {res.name}
                        </code>
                        <span className="font-mono" style={{ fontSize: "12px", color: "var(--text-primary)" }}>
                          ${Math.round(res.cost).toLocaleString("en-US")}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
