import Link from "next/link";
import { API_BASE } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState, EmptyState } from "@/components/primitives/States";
import { ProviderBadge } from "@/components/status/SeverityBadge";
import { getT } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";

export const metadata = { title: "Inventory — FinOps" };

interface InventoryItem {
  resource_id: string;
  resource_name: string | null;
  resource_type: string | null;
  service_name: string | null;
  provider: string;
  team: string;
  env: string;
  total_cost_30d: number;
  tags_complete: boolean;
  missing_tags: string | null;
}

interface InventorySummary {
  total: number;
  complete: number;
  incomplete: number;
  completeness_pct: number;
}

interface InventoryData {
  items: InventoryItem[];
  summary: InventorySummary;
}

async function fetchInventory(): Promise<InventoryData> {
  const res = await fetch(`${API_BASE}/api/inventory?limit=200`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch inventory");
  return res.json();
}

const ENV_COLORS: Record<string, string> = {
  prod: "#D97757",
  staging: "#8E7BB5",
  dev: "#5B9BD5",
};

function envColor(env: string) {
  return ENV_COLORS[env] ?? "#9B9590";
}

export default async function InventoryPage() {
  const t = getT();
  let data: InventoryData;
  try {
    data = await fetchInventory();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { summary, items } = data;

  const HEADERS = [
    { key: "th.resource", align: "left" },
    { key: "th.service", align: "left" },
    { key: "th.provider", align: "center" },
    { key: "th.team", align: "center" },
    { key: "th.env", align: "center" },
    { key: "th.cost_30d", align: "right" },
    { key: "th.tags", align: "center" },
  ] as const;

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={t("page.inventory.title")}
        description={`${summary.total.toLocaleString()} ${t("label.resources").toLowerCase()}`}
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "16px", marginBottom: "32px" }}>
        <MetricCard label={t("label.total_resources")} value={summary.total.toLocaleString()} />
        <MetricCard
          label={t("label.tag_complete")}
          value={summary.complete.toLocaleString()}
          valueColor="var(--status-healthy)"
        />
        <MetricCard
          label={t("label.incomplete")}
          value={summary.incomplete.toLocaleString()}
          valueColor={summary.incomplete > 0 ? "var(--status-warning)" : undefined}
        />
        <MetricCard
          label={t("label.completeness")}
          value={`${summary.completeness_pct.toFixed(1)}%`}
          valueColor={
            summary.completeness_pct >= 90
              ? "var(--status-healthy)"
              : summary.completeness_pct >= 70
              ? "var(--status-warning)"
              : "var(--status-critical)"
          }
        />
      </div>

      <Card>
        <CardHeader>{t("section.all_resources")}</CardHeader>
        {items.length === 0 ? (
          <EmptyState
            title={t("empty.no_inventory")}
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
              {items.map((item, i, arr) => (
                <tr
                  key={item.resource_id}
                  style={{ borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}
                >
                  <td style={{ padding: "10px 8px 10px 0" }}>
                    <div>
                      <Link
                        href={`/resources/${encodeURIComponent(item.resource_id)}`}
                        style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-primary)", textDecoration: "none" }}
                      >
                        {item.resource_name || item.resource_id.split("/").pop() || item.resource_id}
                      </Link>
                      <code
                        className="font-mono"
                        style={{ display: "block", fontSize: "11px", color: "var(--text-tertiary)" }}
                      >
                        {item.resource_type || "—"}
                      </code>
                    </div>
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "13px", color: "var(--text-secondary)" }}>
                    {item.service_name || "—"}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center" }}>
                    <ProviderBadge provider={item.provider as "aws" | "gcp" | "azure"} />
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center", fontSize: "13px", color: "var(--text-secondary)" }}>
                    {item.team}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center" }}>
                    <span
                      style={{
                        display: "inline-block",
                        padding: "2px 8px",
                        borderRadius: "var(--radius-full)",
                        fontSize: "10px",
                        fontWeight: 600,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        background: `color-mix(in srgb, ${envColor(item.env)} 15%, transparent)`,
                        color: envColor(item.env),
                      }}
                    >
                      {item.env}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span
                      className="font-mono"
                      style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-primary)" }}
                    >
                      <span className="currency-symbol">$</span>
                      {Math.round(item.total_cost_30d).toLocaleString("en-US")}
                    </span>
                  </td>
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "center" }}>
                    {item.tags_complete ? (
                      <span
                        style={{
                          display: "inline-block",
                          padding: "2px 8px",
                          borderRadius: "var(--radius-full)",
                          fontSize: "10px",
                          fontWeight: 600,
                          textTransform: "uppercase",
                          letterSpacing: "0.05em",
                          color: "var(--status-healthy)",
                          background:
                            "color-mix(in srgb, var(--status-healthy) 15%, transparent)",
                        }}
                      >
                        {t("status.ok")}
                      </span>
                    ) : (
                      <span
                        title={item.missing_tags ? `Missing: ${item.missing_tags}` : undefined}
                        style={{
                          display: "inline-block",
                          padding: "2px 8px",
                          borderRadius: "var(--radius-full)",
                          fontSize: "10px",
                          fontWeight: 600,
                          textTransform: "uppercase",
                          letterSpacing: "0.05em",
                          color: "var(--status-warning)",
                          background:
                            "color-mix(in srgb, var(--status-warning) 15%, transparent)",
                          cursor: item.missing_tags ? "help" : "default",
                        }}
                      >
                        {item.missing_tags
                          ? `${t("status.missing")} ${item.missing_tags}`
                          : t("status.incomplete")}
                      </span>
                    )}
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
