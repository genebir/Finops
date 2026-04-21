"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { AlertHistoryData, AlertHistoryItem } from "../../../lib/types";

const SEV_COLOR: Record<string, string> = {
  critical: "#D97757",
  warning:  "#E6A817",
  info:     "#6B6560",
};

function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: "6px",
        fontSize: "11px",
        fontWeight: 600,
        letterSpacing: "0.04em",
        textTransform: "uppercase",
        backgroundColor: `${SEV_COLOR[severity] ?? "#6B6560"}22`,
        color: SEV_COLOR[severity] ?? "#6B6560",
      }}
    >
      {severity}
    </span>
  );
}

function AckBadge({ acknowledged }: { acknowledged: boolean }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: "6px",
        fontSize: "11px",
        fontWeight: 600,
        backgroundColor: acknowledged ? "#22543D22" : "#D9777722",
        color: acknowledged ? "#38A169" : "#D97757",
      }}
    >
      {acknowledged ? "ACK" : "OPEN"}
    </span>
  );
}

const FILTERS = ["all", "critical", "warning", "info"] as const;
type SevFilter = typeof FILTERS[number];

export default function AlertsClient() {
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
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "22px", fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
          Alert History
        </h1>
        <p style={{ color: "var(--text-muted)", fontSize: "13px", marginTop: "4px" }}>
          Dispatched alerts with acknowledge workflow
        </p>
      </div>

      {/* KPI row */}
      {summary && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "12px", marginBottom: "24px" }}>
          {[
            { label: "Critical", val: summary.critical, color: "#D97757" },
            { label: "Warning",  val: summary.warning,  color: "#E6A817" },
            { label: "Info",     val: summary.info,     color: "#6B6560" },
            { label: "Open",     val: summary.unacknowledged, color: "#D97757" },
          ].map(({ label, val, color }) => (
            <div
              key={label}
              style={{
                background: "var(--bg-card)",
                border: "1px solid var(--border)",
                borderRadius: "12px",
                padding: "16px 20px",
              }}
            >
              <div style={{ fontSize: "11px", color: "var(--text-muted)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
                {label}
              </div>
              <div style={{ fontSize: "28px", fontWeight: 700, color, marginTop: "4px" }}>{val}</div>
            </div>
          ))}
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
              borderRadius: "8px",
              border: "1px solid var(--border)",
              background: sevFilter === f ? "var(--accent)" : "var(--bg-card)",
              color: sevFilter === f ? "#fff" : "var(--text-muted)",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
              textTransform: "capitalize",
            }}
          >
            {f}
          </button>
        ))}
        <button
          onClick={() => setShowUnack((v) => !v)}
          style={{
            padding: "6px 14px",
            borderRadius: "8px",
            border: "1px solid var(--border)",
            background: showUnack ? "#D9777722" : "var(--bg-card)",
            color: showUnack ? "#D97757" : "var(--text-muted)",
            fontSize: "12px",
            fontWeight: 600,
            cursor: "pointer",
            marginLeft: "8px",
          }}
        >
          Open only
        </button>
        <span style={{ marginLeft: "auto", fontSize: "12px", color: "var(--text-muted)" }}>
          {data ? `${data.total} alerts` : "loading…"}
        </span>
      </div>

      {error && (
        <div style={{ color: "#D97757", marginBottom: "12px", fontSize: "13px" }}>{error}</div>
      )}

      {/* Table */}
      <div
        style={{
          background: "var(--bg-card)",
          border: "1px solid var(--border)",
          borderRadius: "12px",
          overflow: "hidden",
        }}
      >
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Severity","Resource","Type","Actual","Deviation","Triggered","Status",""].map((h, i) => (
                <th
                  key={i}
                  style={{
                    padding: i === 0 ? "0 8px 12px 0" : i === 7 ? "0 0 12px 8px" : "0 8px 12px",
                    textAlign: i === 0 || i === 7 ? "left" : "left",
                    color: "var(--text-muted)",
                    fontWeight: 600,
                    fontSize: "11px",
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data?.items.length === 0 && (
              <tr>
                <td colSpan={8} style={{ padding: "32px", textAlign: "center", color: "var(--text-muted)" }}>
                  No alerts found
                </td>
              </tr>
            )}
            {data?.items.map((item) => (
              <tr key={item.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: "10px 0", textAlign: "center" }}>
                  <SeverityBadge severity={item.severity} />
                </td>
                <td style={{ padding: "10px 8px", maxWidth: "200px" }}>
                  <div style={{ fontWeight: 600, color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {item.resource_id}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>{item.cost_unit_key}</div>
                </td>
                <td style={{ padding: "10px 8px", color: "var(--text-muted)" }}>{item.alert_type}</td>
                <td style={{ padding: "10px 8px", fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                  {item.actual_cost != null ? `$${item.actual_cost.toFixed(2)}` : "—"}
                </td>
                <td style={{ padding: "10px 8px", fontFamily: "var(--font-mono)", color: (item.deviation_pct ?? 0) >= 0 ? "#D97757" : "#38A169" }}>
                  {item.deviation_pct != null ? `${item.deviation_pct > 0 ? "+" : ""}${item.deviation_pct.toFixed(1)}%` : "—"}
                </td>
                <td style={{ padding: "10px 8px", color: "var(--text-muted)", fontSize: "12px", whiteSpace: "nowrap" }}>
                  {item.triggered_at.slice(0, 16).replace("T", " ")}
                </td>
                <td style={{ padding: "10px 8px", textAlign: "center" }}>
                  <AckBadge acknowledged={item.acknowledged} />
                </td>
                <td style={{ padding: "10px 0 10px 8px" }}>
                  {!item.acknowledged && (
                    <button
                      onClick={() => handleAck(item)}
                      disabled={acking === item.id}
                      style={{
                        padding: "4px 10px",
                        borderRadius: "6px",
                        border: "1px solid var(--border)",
                        background: "transparent",
                        color: "var(--text-muted)",
                        fontSize: "11px",
                        cursor: acking === item.id ? "wait" : "pointer",
                      }}
                    >
                      {acking === item.id ? "…" : "Ack"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
