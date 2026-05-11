import { API_BASE } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState } from "@/components/primitives/States";
import AlertRulesClient from "./AlertRulesClient";

export const dynamic = "force-dynamic";

export const metadata = { title: "Alert Rules — FinOps" };

interface AlertRule {
  id: number;
  rule_name: string;
  team: string | null;
  resource_id: string | null;
  metric: string;
  threshold: number;
  severity: string;
  enabled: boolean;
  created_at: string | null;
}

interface AlertRulesData {
  items: AlertRule[];
  total: number;
  summary: { total: number; enabled: number; disabled: number };
}

async function fetchRules(): Promise<AlertRulesData> {
  const res = await fetch(`${API_BASE}/api/alert-rules`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch alert rules — ${res.status}`);
  return res.json();
}

export default async function AlertRulesPage() {
  let data: AlertRulesData;
  try {
    data = await fetchRules();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const criticalCount = data.items.filter((r) => r.severity === "critical").length;

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title="Alert Rules"
        description="Custom alert thresholds — define per-team or per-resource rules for cost spikes, anomalies, and budget usage"
      />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4,1fr)",
          gap: "16px",
          marginBottom: "32px",
        }}
      >
        <MetricCard label="Total Rules" value={String(data.summary.total)} />
        <MetricCard
          label="Enabled"
          value={String(data.summary.enabled)}
          valueColor="var(--status-healthy)"
        />
        <MetricCard
          label="Disabled"
          value={String(data.summary.disabled)}
          valueColor="var(--text-tertiary)"
        />
        <MetricCard
          label="Critical Severity"
          value={String(criticalCount)}
          valueColor={criticalCount > 0 ? "var(--status-critical)" : undefined}
        />
      </div>

      <AlertRulesClient initialRules={data.items} />
    </div>
  );
}
