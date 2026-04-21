import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader, SectionLabel } from "@/components/primitives/Card";
import { EmptyState, ErrorState } from "@/components/primitives/States";
import { api } from "@/lib/api";
import type { SettingItem } from "@/lib/types";

const SETTING_GROUPS: Record<string, string[]> = {
  "Anomaly Detection": [
    "anomaly.zscore.warning",
    "anomaly.zscore.critical",
    "anomaly.active_detectors",
    "isolation_forest.contamination",
    "isolation_forest.n_estimators",
    "isolation_forest.random_state",
    "isolation_forest.score_critical",
    "isolation_forest.score_warning",
    "moving_average.window_days",
    "moving_average.multiplier_warning",
    "moving_average.multiplier_critical",
    "moving_average.min_window",
    "arima.order_p",
    "arima.order_d",
    "arima.order_q",
    "arima.threshold_warning",
    "arima.threshold_critical",
    "arima.min_samples",
  ],
  "Variance & Alerts": [
    "variance.threshold.over_pct",
    "variance.threshold.under_pct",
    "alert.critical_deviation_pct",
    "alert.slack_timeout_sec",
  ],
  "Budget": [
    "budget.alert_threshold_pct",
    "budget.over_threshold_pct",
  ],
  "Reporting": [
    "reporting.lookback_days",
    "reporting.top_resources_limit",
    "reporting.top_cost_units_limit",
    "infracost.subprocess_timeout_sec",
  ],
};

function settingGroup(key: string): string {
  for (const [group, keys] of Object.entries(SETTING_GROUPS)) {
    if (keys.includes(key)) return group;
  }
  return "Other";
}

export default async function SettingsPage() {
  let data;
  try { data = await api.settings(); }
  catch (e) { return <ErrorState message={String(e)} />; }

  if (data.items.length === 0) {
    return (
      <div style={{ maxWidth: "900px" }}>
        <PageHeader
          title="Settings"
          description="platform_settings table — Dagster pipeline threshold configuration"
        />
        <Card>
          <EmptyState
            title="No settings data"
            description="Run a pipeline in Dagster to initialize the platform_settings table."
          />
        </Card>
      </div>
    );
  }

  const grouped = data.items.reduce<Record<string, SettingItem[]>>((acc, item) => {
    const g = settingGroup(item.key);
    (acc[g] ??= []).push(item);
    return acc;
  }, {});

  // Sort: known groups first, then "Other"
  const groupOrder = [...Object.keys(SETTING_GROUPS), "Other"];
  const sortedGroups = groupOrder.filter((g) => g in grouped);

  return (
    <div style={{ maxWidth: "900px" }}>
      <PageHeader
        title="Settings"
        description="platform_settings — Runtime thresholds (editable via SQL, no Dagster restart needed)"
      />

      <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
        {sortedGroups.map((group) => (
          <Card key={group}>
            <CardHeader>{group}</CardHeader>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Key", "Value"].map((h) => (
                    <th
                      key={h}
                      style={{
                        textAlign: h === "Value" ? "right" : "left",
                        fontSize: "10px",
                        fontWeight: 600,
                        fontFamily: "Inter, sans-serif",
                        color: "var(--text-tertiary)",
                        letterSpacing: "0.07em",
                        textTransform: "uppercase",
                        paddingBottom: "12px",
                        borderBottom: "1px solid var(--border)",
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {grouped[group].map((item: SettingItem, i: number) => (
                  <tr
                    key={item.key}
                    style={{
                      borderBottom: i < grouped[group].length - 1 ? "1px solid var(--border)" : "none",
                    }}
                  >
                    <td style={{ padding: "10px 0" }}>
                      <code
                        className="font-mono"
                        style={{ fontSize: "11px", color: "var(--text-secondary)" }}
                      >
                        {item.key}
                      </code>
                    </td>
                    <td style={{ padding: "10px 0", textAlign: "right" }}>
                      <span
                        className="font-mono"
                        style={{ fontSize: "12px", fontWeight: 500, color: "var(--text-primary)" }}
                      >
                        {item.value}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid var(--border)" }}>
              <SectionLabel>
                To update: UPDATE platform_settings SET value = &apos;...&apos; WHERE key = &apos;...&apos;
              </SectionLabel>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
