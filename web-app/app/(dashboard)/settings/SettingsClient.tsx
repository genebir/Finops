"use client";

import { PencilSimple, Check, X, Trash, Plus } from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";

import { Card, CardHeader, SectionLabel } from "@/components/primitives/Card";
import { EmptyState } from "@/components/primitives/States";
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
    "autoencoder.window_size",
    "autoencoder.threshold_warning",
    "autoencoder.threshold_critical",
    "autoencoder.min_samples",
    "autoencoder.max_iter",
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

const inputStyle: React.CSSProperties = {
  fontFamily: '"JetBrains Mono", monospace',
  fontSize: "12px",
  padding: "4px 8px",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-button)",
  background: "var(--bg-warm)",
  color: "var(--text-primary)",
  outline: "none",
  width: "140px",
  textAlign: "right",
  fontVariantNumeric: "tabular-nums",
};

const formInputStyle: React.CSSProperties = {
  ...inputStyle,
  width: "100%",
  textAlign: "left",
};

const iconBtn: React.CSSProperties = {
  padding: "4px",
  border: "none",
  background: "transparent",
  cursor: "pointer",
  color: "var(--text-tertiary)",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
};

const btnPrimary: React.CSSProperties = {
  padding: "6px 16px",
  border: "none",
  borderRadius: "var(--radius-button)",
  background: "var(--accent)",
  color: "#fff",
  fontSize: "12px",
  fontWeight: 600,
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
};

export default function SettingsClient({ initial }: { initial: SettingItem[] }) {
  const [items, setItems] = useState<SettingItem[]>(initial);
  const [editKey, setEditKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [newType, setNewType] = useState("str");
  const [newDesc, setNewDesc] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await api.settings();
      setItems(data.items);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleSave(key: string) {
    if (!editValue.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await api.updateSetting(key, editValue.trim());
      setEditKey(null);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleCreate() {
    if (!newKey.trim() || !newValue.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await api.createSetting({
        key: newKey.trim(),
        value: newValue.trim(),
        value_type: newType,
        description: newDesc.trim() || undefined,
      });
      setShowAdd(false);
      setNewKey("");
      setNewValue("");
      setNewType("str");
      setNewDesc("");
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(key: string) {
    setSaving(true);
    setError(null);
    try {
      await api.deleteSetting(key);
      setDeleteConfirm(null);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  if (items.length === 0 && !showAdd) {
    return (
      <Card>
        <EmptyState
          title="No settings data"
          description="Run a pipeline in Dagster to initialize the platform_settings table."
        />
      </Card>
    );
  }

  const grouped = items.reduce<Record<string, SettingItem[]>>((acc, item) => {
    const g = settingGroup(item.key);
    (acc[g] ??= []).push(item);
    return acc;
  }, {});

  const groupOrder = [...Object.keys(SETTING_GROUPS), "Other"];
  const sortedGroups = groupOrder.filter((g) => g in grouped);

  return (
    <>
      {error && (
        <p
          style={{
            fontSize: "12px",
            color: "var(--status-critical)",
            marginBottom: "16px",
          }}
        >
          {error}
        </p>
      )}

      <div style={{ marginBottom: "20px", display: "flex", justifyContent: "flex-end" }}>
        <button
          type="button"
          style={btnPrimary}
          onClick={() => setShowAdd(!showAdd)}
        >
          <Plus size={14} weight="bold" />
          Add Setting
        </button>
      </div>

      {showAdd && (
        <Card style={{ marginBottom: "20px" }}>
          <CardHeader>New Setting</CardHeader>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "12px" }}>
            <div>
              <label style={{ fontSize: "10px", fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.07em", display: "block", marginBottom: "4px" }}>
                Key
              </label>
              <input
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                placeholder="e.g. custom.threshold"
                style={formInputStyle}
                onKeyDown={(e) => { if (e.key === "Escape") setShowAdd(false); }}
              />
            </div>
            <div>
              <label style={{ fontSize: "10px", fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.07em", display: "block", marginBottom: "4px" }}>
                Value
              </label>
              <input
                value={newValue}
                onChange={(e) => setNewValue(e.target.value)}
                placeholder="e.g. 2.5"
                style={formInputStyle}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCreate();
                  if (e.key === "Escape") setShowAdd(false);
                }}
              />
            </div>
            <div>
              <label style={{ fontSize: "10px", fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.07em", display: "block", marginBottom: "4px" }}>
                Type
              </label>
              <select
                value={newType}
                onChange={(e) => setNewType(e.target.value)}
                style={{ ...formInputStyle, cursor: "pointer" }}
              >
                <option value="str">str</option>
                <option value="float">float</option>
                <option value="int">int</option>
                <option value="bool">bool</option>
              </select>
            </div>
            <div>
              <label style={{ fontSize: "10px", fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.07em", display: "block", marginBottom: "4px" }}>
                Description (optional)
              </label>
              <input
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="Short description"
                style={formInputStyle}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCreate();
                  if (e.key === "Escape") setShowAdd(false);
                }}
              />
            </div>
          </div>
          <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
            <button
              type="button"
              style={{ ...btnPrimary, background: "transparent", color: "var(--text-secondary)", border: "1px solid var(--border)" }}
              onClick={() => setShowAdd(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              style={btnPrimary}
              onClick={handleCreate}
              disabled={saving || !newKey.trim() || !newValue.trim()}
            >
              Create
            </button>
          </div>
        </Card>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
        {sortedGroups.map((group) => (
          <Card key={group}>
            <CardHeader>{group}</CardHeader>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Key", "Type", "Value", ""].map((h, idx, arr) => (
                    <th
                      key={h || `action-${idx}`}
                      style={{
                        textAlign: h === "Value" ? "right" : "left",
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
                        width: h === "Type" ? "60px" : h === "" ? "80px" : undefined,
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {grouped[group].map((item, i) => {
                  const isEditing = editKey === item.key;
                  const isDeleting = deleteConfirm === item.key;
                  return (
                    <tr
                      key={item.key}
                      style={{
                        borderBottom:
                          i < grouped[group].length - 1 ? "1px solid var(--border)" : "none",
                      }}
                    >
                      <td style={{ padding: "10px 0" }}>
                        <code
                          className="font-mono"
                          style={{ fontSize: "11px", color: "var(--text-secondary)" }}
                          title={item.description ?? undefined}
                        >
                          {item.key}
                        </code>
                      </td>
                      <td style={{ padding: "10px 8px" }}>
                        <span style={{ fontSize: "10px", color: "var(--text-tertiary)", fontFamily: '"JetBrains Mono", monospace' }}>
                          {item.value_type}
                        </span>
                      </td>
                      <td style={{ padding: "10px 8px", textAlign: "right" }}>
                        {isEditing ? (
                          <input
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleSave(item.key);
                              if (e.key === "Escape") setEditKey(null);
                            }}
                            style={inputStyle}
                            autoFocus
                          />
                        ) : (
                          <span
                            className="font-mono"
                            style={{ fontSize: "12px", fontWeight: 500, color: "var(--text-primary)" }}
                          >
                            {item.value}
                          </span>
                        )}
                      </td>
                      <td style={{ padding: "10px 0 10px 8px", width: "80px", textAlign: "right", whiteSpace: "nowrap" }}>
                        {isDeleting ? (
                          <>
                            <button
                              type="button"
                              style={{ ...iconBtn, color: "var(--status-critical)" }}
                              onClick={() => handleDelete(item.key)}
                              disabled={saving}
                              title="Confirm delete"
                            >
                              <Check size={16} weight="bold" />
                            </button>
                            <button
                              type="button"
                              style={iconBtn}
                              onClick={() => setDeleteConfirm(null)}
                              title="Cancel"
                            >
                              <X size={16} weight="bold" />
                            </button>
                          </>
                        ) : isEditing ? (
                          <>
                            <button
                              type="button"
                              style={{ ...iconBtn, color: "var(--status-healthy)" }}
                              onClick={() => handleSave(item.key)}
                              disabled={saving}
                              title="Save"
                            >
                              <Check size={16} weight="bold" />
                            </button>
                            <button
                              type="button"
                              style={iconBtn}
                              onClick={() => setEditKey(null)}
                              title="Cancel"
                            >
                              <X size={16} weight="bold" />
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              type="button"
                              style={iconBtn}
                              onClick={() => {
                                setEditKey(item.key);
                                setEditValue(item.value);
                              }}
                              title="Edit"
                            >
                              <PencilSimple size={14} />
                            </button>
                            <button
                              type="button"
                              style={{ ...iconBtn, color: "var(--text-tertiary)" }}
                              onClick={() => setDeleteConfirm(item.key)}
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
            <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid var(--border)" }}>
              <SectionLabel>
                Settings are stored in PostgreSQL platform_settings. Changes take effect on next Dagster asset run.
              </SectionLabel>
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}
