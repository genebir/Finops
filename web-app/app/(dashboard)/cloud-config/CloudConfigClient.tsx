"use client";

import { useState, useTransition } from "react";
import { Card } from "@/components/primitives/Card";
import { API_BASE } from "@/lib/api";

interface FieldMeta {
  value: string;
  value_type: string;
  description: string | null;
}

type ProviderConfig = Record<string, FieldMeta>;

interface StatusInfo {
  enabled: boolean;
  configured: boolean;
  missing_keys: string[];
}

interface Props {
  initialConfig: Record<string, ProviderConfig>;
  initialStatus: Record<string, StatusInfo>;
}

const PROVIDER_LABELS: Record<string, string> = {
  aws: "Amazon Web Services",
  gcp: "Google Cloud Platform",
  azure: "Microsoft Azure",
};

const PROVIDER_COLORS: Record<string, string> = {
  aws: "var(--provider-aws)",
  gcp: "var(--provider-gcp)",
  azure: "var(--provider-azure)",
};

async function updateCloudConfig(provider: string, key: string, value: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/cloud-config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, key, value }),
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
}

export default function CloudConfigClient({ initialConfig, initialStatus }: Props) {
  const [config, setConfig] = useState(initialConfig);
  const [status, setStatus] = useState(initialStatus);
  const [editingCell, setEditingCell] = useState<{ provider: string; key: string } | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  const startEdit = (provider: string, key: string, currentValue: string) => {
    setEditingCell({ provider, key });
    setEditValue(currentValue);
    setError(null);
  };

  const cancelEdit = () => {
    setEditingCell(null);
    setEditValue("");
    setError(null);
  };

  const saveEdit = async () => {
    if (!editingCell) return;
    setSaving(true);
    setError(null);
    try {
      await updateCloudConfig(editingCell.provider, editingCell.key, editValue);
      setConfig((prev) => ({
        ...prev,
        [editingCell.provider]: {
          ...prev[editingCell.provider],
          [editingCell.key]: {
            ...prev[editingCell.provider][editingCell.key],
            value: editValue,
          },
        },
      }));
      // Refresh status
      startTransition(() => {
        fetch(`${API_BASE}/api/cloud-config/status`)
          .then((r) => r.json())
          .then((d) => setStatus(d.providers ?? {}))
          .catch(() => null);
      });
      setEditingCell(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  const toggleEnabled = async (provider: string) => {
    const current = config[provider]?.enabled?.value ?? "false";
    const newVal = current === "true" ? "false" : "true";
    try {
      await updateCloudConfig(provider, "enabled", newVal);
      setConfig((prev) => ({
        ...prev,
        [provider]: {
          ...prev[provider],
          enabled: { ...prev[provider].enabled, value: newVal },
        },
      }));
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {error && (
        <div
          style={{
            padding: "12px 16px",
            backgroundColor: "color-mix(in srgb, var(--status-critical) 10%, transparent)",
            border: "1px solid color-mix(in srgb, var(--status-critical) 30%, transparent)",
            borderRadius: "var(--radius-sm)",
            fontSize: "13px",
            color: "var(--status-critical)",
          }}
        >
          {error}
        </div>
      )}

      {(["aws", "gcp", "azure"] as const).map((provider) => {
        const pConfig = config[provider] ?? {};
        const pStatus = status[provider];
        const isEnabled = pConfig.enabled?.value === "true";
        const fieldEntries = Object.entries(pConfig).filter(([k]) => k !== "enabled");

        return (
          <Card key={provider}>
            {/* Provider header */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "20px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <div
                  style={{
                    width: "10px",
                    height: "10px",
                    borderRadius: "50%",
                    backgroundColor: PROVIDER_COLORS[provider],
                  }}
                />
                <div>
                  <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--text-primary)" }}>
                    {PROVIDER_LABELS[provider]}
                  </div>
                  {pStatus && (
                    <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "2px" }}>
                      {pStatus.configured
                        ? "All required fields configured"
                        : `Missing: ${pStatus.missing_keys.join(", ")}`}
                    </div>
                  )}
                </div>
              </div>

              {/* Enable toggle */}
              <button
                onClick={() => toggleEnabled(provider)}
                style={{
                  padding: "6px 14px",
                  borderRadius: "var(--radius-full)",
                  border: "1px solid",
                  borderColor: isEnabled
                    ? "color-mix(in srgb, var(--status-healthy) 50%, transparent)"
                    : "var(--border)",
                  backgroundColor: isEnabled
                    ? "color-mix(in srgb, var(--status-healthy) 15%, transparent)"
                    : "transparent",
                  color: isEnabled ? "var(--status-healthy)" : "var(--text-tertiary)",
                  fontSize: "12px",
                  fontWeight: 600,
                  cursor: "pointer",
                  fontFamily: "Inter, sans-serif",
                }}
              >
                {isEnabled ? "Enabled" : "Disabled"}
              </button>
            </div>

            {/* Fields */}
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Field", "Description", "Value", ""].map((h, idx) => (
                    <th
                      key={h + idx}
                      style={{
                        textAlign: "left",
                        fontSize: "10px",
                        fontWeight: 600,
                        fontFamily: "Inter, sans-serif",
                        color: "var(--text-tertiary)",
                        letterSpacing: "0.07em",
                        textTransform: "uppercase",
                        padding:
                          idx === 0
                            ? "0 8px 12px 0"
                            : idx === 3
                            ? "0 0 12px 8px"
                            : "0 8px 12px 8px",
                        borderBottom: "1px solid var(--border)",
                        width: idx === 3 ? "80px" : undefined,
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {fieldEntries.map(([key, meta], i) => {
                  const isEditing =
                    editingCell?.provider === provider && editingCell?.key === key;
                  return (
                    <tr
                      key={key}
                      style={{
                        borderBottom:
                          i < fieldEntries.length - 1
                            ? "1px solid var(--border)"
                            : "none",
                      }}
                    >
                      <td style={{ padding: "10px 8px 10px 0" }}>
                        <code
                          className="font-mono"
                          style={{ fontSize: "11px", color: "var(--text-primary)" }}
                        >
                          {key}
                        </code>
                      </td>
                      <td style={{ padding: "10px 8px", fontSize: "12px", color: "var(--text-tertiary)" }}>
                        {meta.description ?? "—"}
                      </td>
                      <td style={{ padding: "10px 8px" }}>
                        {isEditing ? (
                          <input
                            autoFocus
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") saveEdit();
                              if (e.key === "Escape") cancelEdit();
                            }}
                            style={{
                              width: "100%",
                              fontSize: "12px",
                              fontFamily: "var(--font-code)",
                              color: "var(--text-primary)",
                              backgroundColor: "var(--bg-dark)",
                              border: "1px solid var(--border)",
                              borderRadius: "6px",
                              padding: "4px 8px",
                              outline: "none",
                            }}
                          />
                        ) : (
                          <span
                            className="font-mono"
                            style={{
                              fontSize: "12px",
                              color: meta.value ? "var(--text-secondary)" : "var(--text-tertiary)",
                              fontStyle: meta.value ? "normal" : "italic",
                            }}
                          >
                            {meta.value || "not set"}
                          </span>
                        )}
                      </td>
                      <td style={{ padding: "10px 0 10px 8px", textAlign: "right" }}>
                        {isEditing ? (
                          <div style={{ display: "flex", gap: "6px", justifyContent: "flex-end" }}>
                            <button
                              onClick={saveEdit}
                              disabled={saving}
                              style={{
                                fontSize: "11px",
                                fontWeight: 600,
                                fontFamily: "Inter, sans-serif",
                                color: "var(--status-healthy)",
                                background: "none",
                                border: "none",
                                cursor: saving ? "default" : "pointer",
                                opacity: saving ? 0.5 : 1,
                              }}
                            >
                              {saving ? "Saving…" : "Save"}
                            </button>
                            <button
                              onClick={cancelEdit}
                              disabled={saving}
                              style={{
                                fontSize: "11px",
                                fontWeight: 600,
                                fontFamily: "Inter, sans-serif",
                                color: "var(--text-tertiary)",
                                background: "none",
                                border: "none",
                                cursor: "pointer",
                              }}
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => startEdit(provider, key, meta.value)}
                            style={{
                              fontSize: "11px",
                              fontWeight: 500,
                              fontFamily: "Inter, sans-serif",
                              color: "var(--text-tertiary)",
                              background: "none",
                              border: "none",
                              cursor: "pointer",
                            }}
                          >
                            Edit
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
        );
      })}
    </div>
  );
}
