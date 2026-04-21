"use client";

import { Check, X, PencilSimple, CloudCheck, CloudX } from "@phosphor-icons/react";
import { useState } from "react";

import { Card, CardHeader, SectionLabel } from "@/components/primitives/Card";
import { API_BASE } from "@/lib/api";

type ProviderConfig = Record<string, { value: string; value_type: string; description: string }>;
type CloudData = Record<string, ProviderConfig>;

const PROVIDER_META: Record<string, { label: string; color: string; envVars: string[] }> = {
  aws: {
    label: "Amazon Web Services",
    color: "var(--provider-aws)",
    envVars: ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
  },
  gcp: {
    label: "Google Cloud Platform",
    color: "var(--provider-gcp)",
    envVars: ["GOOGLE_APPLICATION_CREDENTIALS"],
  },
  azure: {
    label: "Microsoft Azure",
    color: "var(--provider-azure)",
    envVars: ["AZURE_CLIENT_SECRET"],
  },
};

const inputStyle: React.CSSProperties = {
  fontFamily: '"JetBrains Mono", monospace',
  fontSize: "12px",
  padding: "4px 8px",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-button)",
  background: "var(--bg-warm)",
  color: "var(--text-primary)",
  outline: "none",
  width: "220px",
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

async function updateCloudKey(provider: string, key: string, value: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/cloud-config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, key, value }),
  });
  if (!res.ok) throw new Error(`Failed: ${res.statusText}`);
}

function ProviderCard({
  provider,
  config,
}: {
  provider: string;
  config: ProviderConfig;
}) {
  const meta = PROVIDER_META[provider];
  const [editing, setEditing] = useState<string | null>(null);
  const [editVal, setEditVal] = useState("");
  const [localConfig, setLocalConfig] = useState<ProviderConfig>(config);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const enabled = localConfig["enabled"]?.value === "true";
  const configuredCount = Object.entries(localConfig).filter(
    ([k, v]) => k !== "enabled" && v.value !== ""
  ).length;
  const totalRequired = Object.keys(localConfig).filter((k) => k !== "enabled").length;

  async function saveEdit(key: string) {
    setSaving(true);
    setError(null);
    try {
      await updateCloudKey(provider, key, editVal);
      setLocalConfig((prev) => ({
        ...prev,
        [key]: { ...prev[key], value: editVal },
      }));
      setEditing(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  async function toggleEnabled() {
    const newVal = enabled ? "false" : "true";
    setSaving(true);
    try {
      await updateCloudKey(provider, "enabled", newVal);
      setLocalConfig((prev) => ({
        ...prev,
        enabled: { ...prev["enabled"], value: newVal },
      }));
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  const isConfigured = configuredCount >= totalRequired;

  return (
    <Card style={{ marginBottom: "16px" }}>
      {/* Provider header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{
            display: "inline-block", padding: "3px 10px", borderRadius: "var(--radius-full)",
            fontSize: "11px", fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase",
            background: `color-mix(in srgb, ${meta.color} 15%, transparent)`,
            color: meta.color, border: `1px solid color-mix(in srgb, ${meta.color} 30%, transparent)`,
          }}>
            {provider.toUpperCase()}
          </span>
          <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
            {meta.label}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {/* Status indicator */}
          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px" }}>
            {isConfigured && enabled
              ? <CloudCheck size={16} style={{ color: "var(--status-healthy)" }} />
              : <CloudX size={16} style={{ color: "var(--text-tertiary)" }} />
            }
            <span style={{ color: isConfigured && enabled ? "var(--status-healthy)" : "var(--text-tertiary)" }}>
              {enabled ? (isConfigured ? "Ready" : "Incomplete") : "Disabled"}
            </span>
          </div>
          {/* Enable toggle */}
          <button
            type="button"
            onClick={toggleEnabled}
            disabled={saving}
            style={{
              padding: "5px 14px",
              borderRadius: "var(--radius-button)",
              border: "1px solid var(--border)",
              background: enabled ? `color-mix(in srgb, ${meta.color} 15%, transparent)` : "transparent",
              color: enabled ? meta.color : "var(--text-secondary)",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {enabled ? "Enabled" : "Disabled"}
          </button>
        </div>
      </div>

      {error && (
        <p style={{ fontSize: "12px", color: "var(--status-critical)", marginBottom: "12px" }}>{error}</p>
      )}

      {/* Settings table */}
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            {["Setting", "Value", ""].map((h, idx, arr) => (
              <th key={h || idx} style={{
                textAlign: "left",
                fontSize: "10px", fontWeight: 600, fontFamily: "Inter, sans-serif",
                color: "var(--text-tertiary)", letterSpacing: "0.07em", textTransform: "uppercase",
                padding: idx === 0 ? "0 8px 10px 0" : idx === arr.length - 1 ? "0 0 10px 8px" : "0 8px 10px 8px",
                borderBottom: "1px solid var(--border)",
                width: h === "" ? "64px" : undefined,
              }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Object.entries(localConfig)
            .filter(([k]) => k !== "enabled")
            .map(([key, field], i, arr) => {
              const isEdit = editing === key;
              return (
                <tr key={key} style={{ borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <td style={{ padding: "8px 0" }}>
                    <div>
                      <code className="font-mono" style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                        {key}
                      </code>
                      {field.description && (
                        <p style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "1px" }}>
                          {field.description}
                        </p>
                      )}
                    </div>
                  </td>
                  <td style={{ padding: "8px 8px" }}>
                    {isEdit ? (
                      <input
                        value={editVal}
                        onChange={(e) => setEditVal(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") saveEdit(key);
                          if (e.key === "Escape") setEditing(null);
                        }}
                        style={inputStyle}
                        autoFocus
                        type={key.includes("secret") || key.includes("password") ? "password" : "text"}
                        placeholder={field.description || key}
                      />
                    ) : (
                      <span className="font-mono" style={{
                        fontSize: "12px",
                        color: field.value ? "var(--text-primary)" : "var(--text-tertiary)",
                      }}>
                        {field.value || "—"}
                      </span>
                    )}
                  </td>
                  <td style={{ padding: "8px 0 8px 8px", textAlign: "right", whiteSpace: "nowrap" }}>
                    {isEdit ? (
                      <>
                        <button type="button" style={{ ...iconBtn, color: "var(--status-healthy)" }}
                          onClick={() => saveEdit(key)} disabled={saving} title="Save">
                          <Check size={15} weight="bold" />
                        </button>
                        <button type="button" style={iconBtn} onClick={() => setEditing(null)} title="Cancel">
                          <X size={15} weight="bold" />
                        </button>
                      </>
                    ) : (
                      <button type="button" style={iconBtn}
                        onClick={() => { setEditing(key); setEditVal(field.value); }} title="Edit">
                        <PencilSimple size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
        </tbody>
      </table>

      {/* Env var hint */}
      {meta.envVars.length > 0 && (
        <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid var(--border)" }}>
          <SectionLabel>Secrets (environment variables only — not stored in DB)</SectionLabel>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginTop: "4px" }}>
            {meta.envVars.map((v) => (
              <code key={v} className="font-mono" style={{
                fontSize: "11px", padding: "2px 8px",
                background: "color-mix(in srgb, var(--text-tertiary) 10%, transparent)",
                borderRadius: "4px", color: "var(--text-secondary)",
              }}>
                {v}
              </code>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

export default function CloudConfigClient({ initial }: { initial: CloudData }) {
  return (
    <div>
      {Object.entries(initial).map(([provider, config]) => (
        <ProviderCard key={provider} provider={provider} config={config} />
      ))}
      <p style={{ fontSize: "12px", color: "var(--text-tertiary)", marginTop: "8px" }}>
        💡 Connection credentials (API keys, secrets) must be set via environment variables or a secrets manager — never stored in the database.
      </p>
    </div>
  );
}
