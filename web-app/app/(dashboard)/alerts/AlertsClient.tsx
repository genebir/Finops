"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { AlertHistoryData, AlertHistoryItem } from "@/lib/types";

function AckBadge({ acknowledged }: { acknowledged: boolean }) {
  return (
    <SeverityBadge severity={acknowledged ? "success" : "critical"} />
  );
}

const FILTERS = ["all", "critical", "warning", "info"] as const;
type SevFilter = typeof FILTERS[number];

export default function AlertsClient() {
  const t = useT();
  const [data, setData] = useState<AlertHistoryData | null>(null);
  const [sevFilter, setSevFilter] = useState<SevFilter>("all");
  const [showUnack, setShowUnack] = useState(false);
  const [acking, setAcking] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const params: Record<string, string> = {};
      if (sevFilter !== "all") params.severity = sevFilter;
      if (showUnack) params.acknowledged = "false";
      const d = await api.alerts(params);
      setData(d);
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }, [sevFilter, showUnack]);

  useEffect(() => { load(); }, [load]);

  const handleAck = async (item: AlertHistoryItem) => {
    if (item.acknowledged) return;
    setAcking(item.id);
    try {
      await api.acknowledgeAlert(item.id);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setAcking(null);
    }
  };

  const summary = data?.summary;

  return (
    <div>
      {summary && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "16px", marginBottom: "32px" }}>
          <MetricCard
            label={t("label.critical")}
            value={String(summary.critical)}
            valueColor="var(--status-critical)"
          />
          <MetricCard
            label={t("label.warning")}
            value={String(summary.warning)}
            valueColor="var(--status-warning)"
          />
          <MetricCard
            label={t("label.info")}
            value={String(summary.info)}
          />
          <MetricCard
            label={t("label.open")}
            value={String(summary.unacknowledged)}
            valueColor={summary.unacknowledged > 0 ? "var(--status-critical)" : "var(--text-primary)"}
          />
        </div>
      )}

      {/* Filters */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px", alignItems: "center" }}>
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setSevFilter(f)}
            style={{
              padding: "6px 14px",
              borderRadius: "var(--radius-button)",
              border: "1px solid var(--border)",
              background: sevFilter === f ? "var(--accent)" : "var(--bg-warm-subtle)",
              color: sevFilter === f ? "#fff" : "var(--text-secondary)",
              fontSize: "12px",
              fontWeight: 600,
              fontFamily: "Inter, sans-serif",
              cursor: "pointer",
              textTransform: "capitalize",
            }}
          >
            {f === "all" ? t("action.all") : t(`label.${f}` as "label.critical" | "label.warning" | "label.info")}
          </button>
        ))}
        <button
          onClick={() => setShowUnack((v) => !v)}
          style={{
            padding: "6px 14px",
            borderRadius: "var(--radius-button)",
            border: "1px solid var(--border)",
            background: showUnack ? "rgba(217,119,87,0.1)" : "var(--bg-warm-subtle)",
            color: showUnack ? "var(--status-critical)" : "var(--text-secondary)",
            fontSize: "12px",
            fontWeight: 600,
            fontFamily: "Inter, sans-serif",
            cursor: "pointer",
            marginLeft: "8px",
          }}
        >
          {t("action.open_only")}
        </button>
        <span style={{ marginLeft: "auto", fontSize: "12px", color: "var(--text-tertiary)" }}>
          {data ? `${data.total} ${t("misc.alerts_count")}` : t("misc.loading")}
        </span>
      </div>

      {error && (
        <div style={{ color: "var(--status-critical)", marginBottom: "12px", fontSize: "13px" }}>{error}</div>
      )}

      <Card>
        <CardHeader>{t("section.alert_history")}</CardHeader>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {([
                { key: "th.severity", align: "center" },
                { key: "th.resource", align: "left" },
                { key: "th.type", align: "center" },
                { key: "th.actual", align: "right" },
                { key: "th.deviation", align: "right" },
                { key: "th.triggered", align: "center" },
                { key: "th.status", align: "center" },
                { label: "", align: "center" },
              ] as const).map((col, idx, arr) => (
                <th
                  key={idx}
                  style={{
                    textAlign: col.align as "left" | "right" | "center",
                    padding: idx === 0 ? "0 8px 12px 0" : idx === arr.length - 1 ? "0 0 12px 8px" : "0 8px 12px 8px",
                    fontWeight: 600,
                    color: "var(--text-tertiary)",
                  }}
                >
                  {"key" in col ? t(col.key as "th.severity") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data?.items.length === 0 && (
              <tr>
                <td colSpan={8} style={{ padding: "32px", textAlign: "center", color: "var(--text-tertiary)" }}>
                  {t("empty.no_alerts")}
                </td>
              </tr>
            )}
            {data?.items.map((item) => (
              <tr key={item.id} style={{ borderBottom: "1px solid rgba(0,0,0,0.04)" }}>
                <td style={{ padding: "10px 0", textAlign: "center" }}>
                  <SeverityBadge severity={item.severity} />
                </td>
                <td style={{ padding: "10px 8px", maxWidth: "200px" }}>
                  <div style={{ fontWeight: 600, color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {item.resource_id}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>{item.cost_unit_key}</div>
                </td>
                <td style={{ padding: "10px 8px", textAlign: "center", color: "var(--text-secondary)" }}>{item.alert_type}</td>
                <td style={{ padding: "10px 8px", textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                  {item.actual_cost != null ? `$${item.actual_cost.toFixed(2)}` : "--"}
                </td>
                <td style={{ padding: "10px 8px", textAlign: "right", fontFamily: "var(--font-mono)", color: (item.deviation_pct ?? 0) >= 0 ? "var(--status-critical)" : "var(--status-healthy)" }}>
                  {item.deviation_pct != null ? `${item.deviation_pct > 0 ? "+" : ""}${item.deviation_pct.toFixed(1)}%` : "--"}
                </td>
                <td style={{ padding: "10px 8px", textAlign: "center", color: "var(--text-tertiary)", fontSize: "12px", whiteSpace: "nowrap" }}>
                  {item.triggered_at.slice(0, 16).replace("T", " ")}
                </td>
                <td style={{ padding: "10px 8px", textAlign: "center" }}>
                  <AckBadge acknowledged={item.acknowledged} />
                </td>
                <td style={{ padding: "10px 0 10px 8px", textAlign: "center" }}>
                  {!item.acknowledged && (
                    <button
                      onClick={() => handleAck(item)}
                      disabled={acking === item.id}
                      style={{
                        padding: "4px 10px",
                        borderRadius: "var(--radius-button)",
                        border: "1px solid var(--border)",
                        background: "transparent",
                        color: "var(--text-secondary)",
                        fontSize: "11px",
                        fontFamily: "Inter, sans-serif",
                        cursor: acking === item.id ? "wait" : "pointer",
                      }}
                    >
                      {acking === item.id ? "..." : t("action.ack")}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
