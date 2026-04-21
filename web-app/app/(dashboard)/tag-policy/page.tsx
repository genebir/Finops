import { API_BASE } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState, EmptyState } from "@/components/primitives/States";
import { SeverityBadge, ProviderBadge } from "@/components/status/SeverityBadge";

export const dynamic = "force-dynamic";

interface Violation {
  id: number;
  resource_id: string;
  resource_type: string | null;
  service_category: string | null;
  provider: string;
  team: string;
  env: string;
  violation_type: string;
  missing_tag: string;
  severity: string;
  cost_30d: number | null;
  detected_at: string;
}

interface ViolationSummary {
  total: number;
  critical: number;
  warning: number;
}

interface TagPolicyData {
  violations: Violation[];
  summary: ViolationSummary;
}

async function fetchTagPolicy(): Promise<TagPolicyData> {
  const res = await fetch(`${API_BASE}/api/tag-policy?limit=200`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch tag-policy");
  return res.json();
}

const HEADERS = ["Resource", "Provider", "Team", "Env", "Missing Tag", "Severity", "30d Cost"];

const ENV_COLORS: Record<string, string> = {
  prod: "#D97757",
  staging: "#8E7BB5",
  dev: "#5B9BD5",
};

function envColor(env: string) {
  return ENV_COLORS[env] ?? "#9B9590";
}

export default async function TagPolicyPage() {
  let data: TagPolicyData;
  try {
    data = await fetchTagPolicy();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { violations, summary } = data;
  const totalCostAtRisk = violations.reduce((s, v) => s + (v.cost_30d ?? 0), 0);

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title="Tag Policy"
        description="Tag compliance violations — resources missing required tags"
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "16px", marginBottom: "32px" }}>
        <MetricCard
          label="Total Violations"
          value={String(summary.total)}
          valueColor={summary.total > 0 ? "var(--status-warning)" : undefined}
        />
        <MetricCard
          label="Critical"
          value={String(summary.critical)}
          valueColor={summary.critical > 0 ? "var(--status-critical)" : undefined}
        />
        <MetricCard
          label="Warning"
          value={String(summary.warning)}
          valueColor={summary.warning > 0 ? "var(--status-warning)" : undefined}
        />
        <MetricCard
          label="Cost at Risk (30d)"
          value={`$${Math.round(totalCostAtRisk).toLocaleString("en-US")}`}
          valueColor={totalCostAtRisk > 1000 ? "var(--status-warning)" : undefined}
        />
      </div>

      <Card>
        <CardHeader>Violations</CardHeader>
        {violations.length === 0 ? (
          <EmptyState
            title="No violations today"
            description="Run the tag_policy asset in Dagster to scan for violations."
          />
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {HEADERS.map((h, idx, arr) => (
                  <th
                    key={h}
                    style={{
                      textAlign:
                        h === "Provider" || h === "Severity"
                          ? "center"
                          : idx === arr.length - 1
                          ? "right"
                          : "left",
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
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {violations.map((v, i, arr) => (
                <tr
                  key={v.id}
                  style={{ borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}
                >
                  {/* Resource */}
                  <td style={{ padding: "10px 8px 10px 0" }}>
                    <div>
                      <code
                        className="font-mono"
                        style={{ fontSize: "11px", color: "var(--text-primary)" }}
                      >
                        {v.resource_id.length > 40
                          ? `…${v.resource_id.slice(-38)}`
                          : v.resource_id}
                      </code>
                      {v.service_category && (
                        <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "1px" }}>
                          {v.service_category}
                        </div>
                      )}
                    </div>
                  </td>
                  {/* Provider */}
                  <td style={{ padding: "10px 8px", textAlign: "center" }}>
                    <ProviderBadge provider={v.provider as "aws" | "gcp" | "azure"} />
                  </td>
                  {/* Team */}
                  <td style={{ padding: "10px 8px", fontSize: "13px", color: "var(--text-secondary)" }}>
                    {v.team}
                  </td>
                  {/* Env */}
                  <td style={{ padding: "10px 8px" }}>
                    <span
                      style={{
                        display: "inline-block",
                        padding: "2px 8px",
                        borderRadius: "var(--radius-full)",
                        fontSize: "10px",
                        fontWeight: 600,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        background: `color-mix(in srgb, ${envColor(v.env)} 15%, transparent)`,
                        color: envColor(v.env),
                      }}
                    >
                      {v.env}
                    </span>
                  </td>
                  {/* Missing Tag */}
                  <td style={{ padding: "10px 8px" }}>
                    <code
                      className="font-mono"
                      style={{
                        fontSize: "11px",
                        padding: "2px 6px",
                        borderRadius: "4px",
                        background: "color-mix(in srgb, var(--status-warning) 12%, transparent)",
                        color: "var(--status-warning)",
                      }}
                    >
                      {v.missing_tag}
                    </code>
                  </td>
                  {/* Severity */}
                  <td style={{ padding: "10px 8px", textAlign: "center" }}>
                    <SeverityBadge severity={v.severity as "critical" | "warning"} />
                  </td>
                  {/* Cost */}
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "right" }}>
                    {v.cost_30d != null ? (
                      <span
                        className="font-mono"
                        style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-primary)" }}
                      >
                        <span className="currency-symbol">$</span>
                        {Math.round(v.cost_30d).toLocaleString("en-US")}
                      </span>
                    ) : (
                      <span style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>—</span>
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
