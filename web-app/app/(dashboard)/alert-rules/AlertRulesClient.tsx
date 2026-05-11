"use client";

import { useState } from "react";
import { Check, X, PencilSimple, Trash } from "@phosphor-icons/react";
import { Card } from "@/components/primitives/Card";
import { API_BASE } from "@/lib/api";

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

interface Props {
  initialRules: AlertRule[];
}

const METRICS = ["cost_spike", "anomaly_count", "budget_pct"] as const;
const SEVERITIES = ["warning", "critical"] as const;

const inputStyle: React.CSSProperties = {
  fontFamily: '"JetBrains Mono", monospace',
  fontSize: "12px",
  padding: "5px 8px",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-button)",
  background: "var(--bg-warm)",
  color: "var(--text-primary)",
  outline: "none",
};

const iconBtn: React.CSSProperties = {
  padding: "4px",
  border: "none",
  background: "transparent",
  cursor: "pointer",
  color: "var(--text-tertiary)",
  display: "inline-flex",
  alignItems: "center",
};

function SeverityBadge({ severity }: { severity: string }) {
  const isCritical = severity === "critical";
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        fontSize: "10px",
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        borderRadius: "var(--radius-button)",
        color: isCritical ? "var(--status-critical)" : "var(--status-warning)",
        backgroundColor: isCritical
          ? "color-mix(in srgb, var(--status-critical) 12%, transparent)"
          : "color-mix(in srgb, var(--status-warning) 14%, transparent)",
      }}
    >
      {severity}
    </span>
  );
}

function MetricPill({ metric }: { metric: string }) {
  return (
    <code
      className="font-mono"
      style={{
        fontSize: "11px",
        padding: "2px 6px",
        borderRadius: "var(--radius-button)",
        background: "color-mix(in srgb, var(--border) 30%, transparent)",
        color: "var(--text-secondary)",
      }}
    >
      {metric}
    </code>
  );
}

export default function AlertRulesClient({ initialRules }: Props) {
  const [rules, setRules] = useState<AlertRule[]>(initialRules);
  const [error, setError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editThreshold, setEditThreshold] = useState("");
  const [editSeverity, setEditSeverity] = useState<string>("warning");

  const [deletingId, setDeletingId] = useState<number | null>(null);

  const [showAdd, setShowAdd] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [newTeam, setNewTeam] = useState("");
  const [newResourceId, setNewResourceId] = useState("");
  const [newMetric, setNewMetric] = useState<string>("cost_spike");
  const [newThreshold, setNewThreshold] = useState("100");
  const [newSeverity, setNewSeverity] = useState<string>("warning");

  function startEdit(rule: AlertRule) {
    setEditingId(rule.id);
    setEditThreshold(String(rule.threshold));
    setEditSeverity(rule.severity);
    setError(null);
  }

  async function saveEdit(id: number) {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/alert-rules/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          threshold: parseFloat(editThreshold),
          severity: editSeverity,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const updated: AlertRule = await res.json();
      setRules((prev) => prev.map((r) => (r.id === id ? updated : r)));
      setEditingId(null);
    } catch (e) {
      setError(String(e));
    }
  }

  async function toggleEnabled(rule: AlertRule) {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/alert-rules/${rule.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !rule.enabled }),
      });
      if (!res.ok) throw new Error(await res.text());
      const updated: AlertRule = await res.json();
      setRules((prev) => prev.map((r) => (r.id === rule.id ? updated : r)));
    } catch (e) {
      setError(String(e));
    }
  }

  async function deleteRule(id: number) {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/alert-rules/${id}`, { method: "DELETE" });
      if (!res.ok && res.status !== 204) throw new Error(await res.text());
      setRules((prev) => prev.filter((r) => r.id !== id));
      setDeletingId(null);
    } catch (e) {
      setError(String(e));
    }
  }

  async function addRule() {
    setError(null);
    setAdding(true);
    try {
      const body = {
        rule_name: newName,
        team: newTeam || null,
        resource_id: newResourceId || null,
        metric: newMetric,
        threshold: parseFloat(newThreshold),
        severity: newSeverity,
        enabled: true,
      };
      const res = await fetch(`${API_BASE}/api/alert-rules`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const text = await res.text();
        if (res.status === 409) throw new Error(`Rule name '${newName}' already exists`);
        throw new Error(text || `${res.status}`);
      }
      const created: AlertRule = await res.json();
      setRules((prev) => [...prev, created]);
      setNewName("");
      setNewTeam("");
      setNewResourceId("");
      setNewMetric("cost_spike");
      setNewThreshold("100");
      setNewSeverity("warning");
      setShowAdd(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setAdding(false);
    }
  }

  const headers = [
    { label: "Name", align: "left" },
    { label: "Scope", align: "left" },
    { label: "Metric", align: "left" },
    { label: "Threshold", align: "right" },
    { label: "Severity", align: "center" },
    { label: "Enabled", align: "center" },
    { label: "", align: "right" },
  ];

  return (
    <div>
      {error && (
        <p style={{ fontSize: "12px", color: "var(--status-critical)", marginBottom: "12px" }}>
          {error}
        </p>
      )}

      <Card>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "20px",
          }}
        >
          <p
            style={{
              fontFamily: "Inter, sans-serif",
              fontSize: "13px",
              fontWeight: 600,
              color: "var(--text-primary)",
              margin: 0,
            }}
          >
            Rules
          </p>
          <button
            onClick={() => setShowAdd(!showAdd)}
            style={{
              padding: "6px 14px",
              borderRadius: "var(--radius-button)",
              border: "1px solid var(--border)",
              background: "transparent",
              fontSize: "12px",
              fontWeight: 600,
              color: "var(--text-secondary)",
              cursor: "pointer",
            }}
          >
            {showAdd ? "Cancel" : "+ Add Rule"}
          </button>
        </div>

        {showAdd && (
          <div
            style={{
              marginBottom: "16px",
              padding: "12px 16px",
              borderRadius: "var(--radius-button)",
              border: "1px solid var(--border)",
              background: "color-mix(in srgb, var(--border) 20%, transparent)",
              display: "grid",
              gridTemplateColumns: "1.4fr 1fr 1fr 1.2fr 90px 110px auto",
              gap: "8px",
              alignItems: "center",
            }}
          >
            <input
              placeholder="rule_name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              style={{ ...inputStyle, width: "100%" }}
            />
            <input
              placeholder="team (optional)"
              value={newTeam}
              onChange={(e) => setNewTeam(e.target.value)}
              style={{ ...inputStyle, width: "100%" }}
            />
            <input
              placeholder="resource_id (optional)"
              value={newResourceId}
              onChange={(e) => setNewResourceId(e.target.value)}
              style={{ ...inputStyle, width: "100%" }}
            />
            <select
              value={newMetric}
              onChange={(e) => setNewMetric(e.target.value)}
              style={{ ...inputStyle, width: "100%" }}
            >
              {METRICS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
            <input
              type="number"
              min={0}
              step="any"
              placeholder="threshold"
              value={newThreshold}
              onChange={(e) => setNewThreshold(e.target.value)}
              style={{ ...inputStyle, width: "100%", textAlign: "right" }}
            />
            <select
              value={newSeverity}
              onChange={(e) => setNewSeverity(e.target.value)}
              style={{ ...inputStyle, width: "100%" }}
            >
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <button
              onClick={addRule}
              disabled={
                adding ||
                !newName.trim() ||
                !newThreshold ||
                Number.isNaN(parseFloat(newThreshold))
              }
              style={{
                ...iconBtn,
                color: "var(--status-healthy)",
                padding: "6px 12px",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-button)",
                fontSize: "12px",
                fontWeight: 600,
              }}
            >
              {adding ? "…" : "Save"}
            </button>
          </div>
        )}

        {rules.length === 0 ? (
          <p style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>
            No alert rules. Add one above to start monitoring custom thresholds.
          </p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {headers.map((h, idx, arr) => (
                  <th
                    key={h.label || idx}
                    style={{
                      textAlign: h.align as "left" | "right" | "center",
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
                    {h.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rules.map((rule, i, arr) => {
                const isEdit = editingId === rule.id;
                const isDelete = deletingId === rule.id;
                const scope =
                  rule.team && rule.resource_id
                    ? `${rule.team} · ${rule.resource_id}`
                    : rule.team
                      ? rule.team
                      : rule.resource_id
                        ? rule.resource_id
                        : "*";
                return (
                  <tr
                    key={rule.id}
                    style={{
                      borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none",
                    }}
                  >
                    <td style={{ padding: "10px 8px 10px 0" }}>
                      <span
                        style={{
                          fontSize: "13px",
                          fontWeight: 600,
                          color: "var(--text-primary)",
                        }}
                      >
                        {rule.rule_name}
                      </span>
                    </td>
                    <td style={{ padding: "10px 8px" }}>
                      <code
                        className="font-mono"
                        style={{ fontSize: "11px", color: "var(--text-tertiary)" }}
                      >
                        {scope}
                      </code>
                    </td>
                    <td style={{ padding: "10px 8px" }}>
                      <MetricPill metric={rule.metric} />
                    </td>
                    <td style={{ padding: "10px 8px", textAlign: "right" }}>
                      {isEdit ? (
                        <input
                          type="number"
                          min={0}
                          step="any"
                          value={editThreshold}
                          onChange={(e) => setEditThreshold(e.target.value)}
                          style={{ ...inputStyle, width: "80px", textAlign: "right" }}
                        />
                      ) : (
                        <span
                          className="font-mono"
                          style={{
                            fontSize: "13px",
                            color: "var(--text-primary)",
                          }}
                        >
                          {rule.threshold}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: "10px 8px", textAlign: "center" }}>
                      {isEdit ? (
                        <select
                          value={editSeverity}
                          onChange={(e) => setEditSeverity(e.target.value)}
                          style={{ ...inputStyle, width: "100px" }}
                        >
                          {SEVERITIES.map((s) => (
                            <option key={s} value={s}>
                              {s}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <SeverityBadge severity={rule.severity} />
                      )}
                    </td>
                    <td style={{ padding: "10px 8px", textAlign: "center" }}>
                      <button
                        type="button"
                        onClick={() => toggleEnabled(rule)}
                        style={{
                          padding: "3px 10px",
                          borderRadius: "var(--radius-button)",
                          border: "1px solid var(--border)",
                          fontSize: "11px",
                          fontWeight: 600,
                          background: rule.enabled
                            ? "color-mix(in srgb, var(--status-healthy) 14%, transparent)"
                            : "transparent",
                          color: rule.enabled
                            ? "var(--status-healthy)"
                            : "var(--text-tertiary)",
                          cursor: "pointer",
                        }}
                      >
                        {rule.enabled ? "ON" : "OFF"}
                      </button>
                    </td>
                    <td
                      style={{
                        padding: "10px 0 10px 8px",
                        textAlign: "right",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {isEdit ? (
                        <>
                          <button
                            type="button"
                            style={{ ...iconBtn, color: "var(--status-healthy)" }}
                            onClick={() => saveEdit(rule.id)}
                            title="Save"
                          >
                            <Check size={15} weight="bold" />
                          </button>
                          <button
                            type="button"
                            style={iconBtn}
                            onClick={() => setEditingId(null)}
                            title="Cancel"
                          >
                            <X size={15} weight="bold" />
                          </button>
                        </>
                      ) : isDelete ? (
                        <>
                          <button
                            type="button"
                            style={{ ...iconBtn, color: "var(--status-critical)" }}
                            onClick={() => deleteRule(rule.id)}
                            title="Confirm delete"
                          >
                            <Check size={15} weight="bold" />
                          </button>
                          <button
                            type="button"
                            style={iconBtn}
                            onClick={() => setDeletingId(null)}
                            title="Cancel"
                          >
                            <X size={15} weight="bold" />
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            style={iconBtn}
                            onClick={() => startEdit(rule)}
                            title="Edit"
                          >
                            <PencilSimple size={14} />
                          </button>
                          <button
                            type="button"
                            style={{ ...iconBtn, color: "var(--status-critical)" }}
                            onClick={() => setDeletingId(rule.id)}
                            title="Delete"
                          >
                            <Trash size={14} />
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
