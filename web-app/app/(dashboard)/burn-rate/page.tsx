import { API_BASE } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState, EmptyState } from "@/components/primitives/States";
import { getT } from "@/lib/i18n/server";
import type { BurnRateData, BurnRateSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "Burn Rate — FinOps" };

async function fetchBurnRate(): Promise<BurnRateData> {
  const res = await fetch(`${API_BASE}/api/burn-rate`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch burn-rate");
  return res.json();
}

const STATUS_COLOR: Record<string, string> = {
  critical: "var(--status-critical)",
  warning: "var(--status-warning)",
  on_track: "var(--status-healthy)",
  no_budget: "var(--text-tertiary)",
};

function fmt(n: number | null | undefined): string {
  if (n == null) return "—";
  return `$${Math.round(n).toLocaleString("en-US")}`;
}

function BurnBar({ pct }: { pct: number | null }) {
  if (pct == null) {
    return <span style={{ color: "var(--text-tertiary)", fontSize: "12px" }}>—</span>;
  }
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
          backgroundColor: "var(--border)",
          borderRadius: "3px",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${Math.min(pct, 100)}%`,
            backgroundColor: color,
            borderRadius: "3px",
          }}
        />
      </div>
      <span
        className="font-mono"
        style={{ fontSize: "12px", color, minWidth: "42px", textAlign: "right" }}
      >
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

const EMPTY_SUMMARY: BurnRateSummary = {
  total_mtd: 0,
  total_projected_eom: 0,
  critical_count: 0,
  warning_count: 0,
  on_track_count: 0,
};

export default async function BurnRatePage() {
  const t = getT();
  let data: BurnRateData;
  try {
    data = await fetchBurnRate();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { items, billing_month } = data;
  const summary: BurnRateSummary = data.summary ?? EMPTY_SUMMARY;

  const HEADERS = [
    { key: "th.team", align: "left" },
    { key: "th.env", align: "center" },
    { key: "th.mtd_cost", align: "right" },
    { key: "th.daily_avg", align: "right" },
    { key: "th.projected_eom", align: "right" },
    { key: "th.budget", align: "right" },
    { key: "th.progress", align: "left" },
    { key: "th.status", align: "center" },
  ] as const;

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={t("page.burn_rate.title")}
        description={`${billing_month} — ${t("misc.month_to_date")}`}
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "16px", marginBottom: "32px" }}>
        <MetricCard
          label={t("label.mtd_total")}
          value={fmt(summary.total_mtd)}
          sub={t("misc.month_to_date")}
        />
        <MetricCard
          label={t("label.projected_eom")}
          value={fmt(summary.total_projected_eom)}
          sub={t("misc.eom_estimate")}
        />
        <MetricCard
          label={t("label.critical")}
          value={String(summary.critical_count ?? 0)}
          sub={t("misc.over_budget_trajectory")}
          valueColor={(summary.critical_count ?? 0) > 0 ? "var(--status-critical)" : undefined}
        />
        <MetricCard
          label={t("label.warning")}
          value={String(summary.warning_count ?? 0)}
          sub={t("misc.approaching_budget")}
          valueColor={(summary.warning_count ?? 0) > 0 ? "var(--status-warning)" : undefined}
        />
      </div>

      <Card>
        <CardHeader>{t("section.team_env_burn_rate")}</CardHeader>
        {items.length === 0 ? (
          <EmptyState
            title={t("empty.no_burn_rate")}
            description={t("empty.run_anomaly")}
          />
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {HEADERS.map((col, idx, arr) => (
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
              {items.map((r, i, arr) => (
                <tr
                  key={`${r.team}-${r.env}`}
                  style={{ borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}
                >
                  <td style={{ padding: "10px 8px 10px 0", fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
                    {r.team}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center", fontSize: "13px", color: "var(--text-secondary)" }}>
                    {r.env}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-primary)" }}>
                      {fmt(r.mtd_cost)}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                      {fmt(r.daily_avg)}/d
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span
                      className="font-mono"
                      style={{
                        fontSize: "13px",
                        fontWeight: 600,
                        color: STATUS_COLOR[r.status] ?? "var(--text-primary)",
                      }}
                    >
                      {fmt(r.projected_eom)}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>
                      {fmt(r.budget_amount)}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", minWidth: "140px" }}>
                    <BurnBar pct={r.projected_utilization} />
                  </td>
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "center" }}>
                    <span
                      style={{
                        display: "inline-block",
                        padding: "2px 8px",
                        borderRadius: "var(--radius-full)",
                        fontSize: "10px",
                        fontWeight: 600,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        color: STATUS_COLOR[r.status] ?? "var(--text-tertiary)",
                        background: `color-mix(in srgb, ${STATUS_COLOR[r.status] ?? "var(--text-tertiary)"} 15%, transparent)`,
                      }}
                    >
                      {r.status.replace("_", " ")}
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
