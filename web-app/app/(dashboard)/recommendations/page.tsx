import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { EmptyState, ErrorState } from "@/components/primitives/States";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/formatters";
import { getT } from "@/lib/i18n/server";
import type { RecommendationItem } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "Recommendations — FinOps" };

const RULE_META: Record<string, { labelKey: "misc.idle_resource" | "misc.high_growth" | "misc.persistent_anomaly"; color: string; bg: string }> = {
  idle:               { labelKey: "misc.idle_resource",     color: "var(--provider-gcp)",      bg: "rgba(107,140,174,0.08)" },
  high_growth:        { labelKey: "misc.high_growth",        color: "var(--status-warning)",    bg: "rgba(232,160,74,0.08)"  },
  persistent_anomaly: { labelKey: "misc.persistent_anomaly", color: "var(--status-critical)",   bg: "rgba(200,85,61,0.08)"   },
};

export default async function RecommendationsPage() {
  const t = getT();
  let data;
  try { data = await api.recommendations(); }
  catch (e) { return <ErrorState message={String(e)} />; }

  const byRule = data.items.reduce<Record<string, RecommendationItem[]>>((acc, item) => {
    (acc[item.rule_type] ??= []).push(item);
    return acc;
  }, {});

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={t("page.recommendations.title")}
        description={t("page.recommendations.desc")}
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
          label={t("label.total_recommendations")}
          value={String(data.items.length)}
        />
        <MetricCard
          label={t("label.potential_savings")}
          value={data.total_potential_savings > 0 ? formatCurrency(data.total_potential_savings, { compact: true }) : "—"}
          valueColor="var(--status-healthy)"
        />
        <MetricCard
          label={t("label.rule_types")}
          value={String(Object.keys(byRule).length)}
        />
      </div>

      {data.items.length === 0 ? (
        <Card>
          <EmptyState
            title={t("empty.no_recommendations")}
            description={t("empty.run_anomaly")}
          />
        </Card>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          {Object.entries(byRule).map(([rule, items]) => {
            const meta = RULE_META[rule];
            const label = meta ? t(meta.labelKey) : rule;
            const color = meta?.color ?? "var(--text-tertiary)";
            const bg = meta?.bg ?? "rgba(168,159,148,0.08)";
            return (
              <Card key={rule}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "20px" }}>
                  <span
                    style={{
                      fontSize: "10px",
                      fontWeight: 600,
                      fontFamily: "Inter, sans-serif",
                      letterSpacing: "0.07em",
                      textTransform: "uppercase",
                      color,
                      background: bg,
                      border: `1px solid ${color}`,
                      borderRadius: "var(--radius-full)",
                      padding: "3px 10px",
                    }}
                  >
                    {label}
                  </span>
                  <span style={{ fontSize: "12px", color: "var(--text-tertiary)", fontFamily: "Inter, sans-serif" }}>
                    {items.length} {items.length !== 1 ? t("misc.items") : t("misc.item")}
                  </span>
                </div>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      {([
                        { key: "th.resource", align: "left" },
                        { key: "th.team", align: "left" },
                        { key: "th.env", align: "center" },
                        { key: "th.description", align: "left" },
                        { key: "th.savings", align: "right" },
                        { key: "th.severity", align: "center" },
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
                    {items.map((item: RecommendationItem, i: number) => (
                      <tr
                        key={i}
                        style={{ borderBottom: i < items.length - 1 ? "1px solid var(--border)" : "none" }}
                      >
                        <td style={{ padding: "10px 0" }}>
                          <code className="font-mono" style={{ fontSize: "11px", color: "var(--text-primary)" }}>
                            {item.resource_id}
                          </code>
                        </td>
                        <td style={{ padding: "10px 8px", fontSize: "12px", color: "var(--text-secondary)" }}>
                          {item.team}
                        </td>
                        <td style={{ padding: "10px 8px", textAlign: "center" }}>
                          <SeverityBadge severity={item.env} />
                        </td>
                        <td style={{ padding: "10px 8px", fontSize: "12px", color: "var(--text-secondary)", maxWidth: "260px" }}>
                          {item.description}
                        </td>
                        <td style={{ padding: "10px 8px", textAlign: "right" }}>
                          {item.potential_savings > 0 ? (
                            <span className="font-mono" style={{ fontSize: "12px", color: "var(--status-healthy)" }}>
                              <span className="currency-symbol">$</span>
                              {Math.round(item.potential_savings).toLocaleString("en-US")}
                            </span>
                          ) : (
                            <span style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>—</span>
                          )}
                        </td>
                        <td style={{ padding: "10px 0 10px 8px", textAlign: "center" }}>
                          <SeverityBadge severity={item.severity} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
