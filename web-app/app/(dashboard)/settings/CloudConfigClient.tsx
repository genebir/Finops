"use client";

import { Check, X, PencilSimple, CloudCheck, CloudX } from "@phosphor-icons/react";
import { useState } from "react";

import { Card, SectionLabel } from "@/components/primitives/Card";
import { API_BASE } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { TranslationKey } from "@/lib/i18n";

type ProviderConfig = Record<string, { value: string; value_type: string; description: string }>;
type CloudData = Record<string, ProviderConfig>;

const PROVIDER_META: Record<string, { label: string; color: string; envVars: { name: string; desc: string }[] }> = {
  aws: {
    label: "Amazon Web Services",
    color: "var(--provider-aws)",
    envVars: [
      { name: "AWS_ACCESS_KEY_ID", desc: "IAM access key" },
      { name: "AWS_SECRET_ACCESS_KEY", desc: "IAM secret key" },
      { name: "AWS_SESSION_TOKEN", desc: "Optional STS session token" },
    ],
  },
  gcp: {
    label: "Google Cloud Platform",
    color: "var(--provider-gcp)",
    envVars: [
      { name: "GOOGLE_APPLICATION_CREDENTIALS", desc: "Path to service account JSON key" },
    ],
  },
  azure: {
    label: "Microsoft Azure",
    color: "var(--provider-azure)",
    envVars: [
      { name: "AZURE_CLIENT_ID", desc: "App registration client ID" },
      { name: "AZURE_CLIENT_SECRET", desc: "App registration secret" },
      { name: "AZURE_TENANT_ID", desc: "Azure AD tenant (also stored above)" },
    ],
  },
};

const FIELD_DESC_MAP: Record<string, TranslationKey> = {
  "aws.region": "cloud.desc.aws.region",
  "aws.cur_s3_bucket": "cloud.desc.aws.cur_s3_bucket",
  "aws.cur_s3_prefix": "cloud.desc.aws.cur_s3_prefix",
  "aws.account_id": "cloud.desc.aws.account_id",
  "gcp.project_id": "cloud.desc.gcp.project_id",
  "gcp.billing_dataset": "cloud.desc.gcp.billing_dataset",
  "gcp.billing_table": "cloud.desc.gcp.billing_table",
  "azure.subscription_id": "cloud.desc.azure.subscription_id",
  "azure.tenant_id": "cloud.desc.azure.tenant_id",
  "azure.storage_account": "cloud.desc.azure.storage_account",
  "azure.storage_container": "cloud.desc.azure.storage_container",
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
  width: "240px",
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

function ProviderCard({ provider, config }: { provider: string; config: ProviderConfig }) {
  const t = useT();
  const meta = PROVIDER_META[provider];
  const [editing, setEditing] = useState<string | null>(null);
  const [editVal, setEditVal] = useState("");
  const [localConfig, setLocalConfig] = useState<ProviderConfig>(config);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const enabled = localConfig["enabled"]?.value === "true";
  const fields = Object.entries(localConfig).filter(([k]) => k !== "enabled");
  const configuredCount = fields.filter(([, v]) => v.value !== "").length;
  const totalRequired = fields.length;

  async function saveEdit(key: string) {
    setSaving(true);
    setError(null);
    try {
      await updateCloudKey(provider, key, editVal);
      setLocalConfig((prev) => ({ ...prev, [key]: { ...prev[key], value: editVal } }));
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
      setLocalConfig((prev) => ({ ...prev, enabled: { ...prev["enabled"], value: newVal } }));
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  const isReady = configuredCount >= totalRequired && enabled;

  return (
    <Card style={{ marginBottom: "16px" }}>
      {/* Header */}
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
          <div>
            <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
              {meta.label}
            </span>
            <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "1px" }}>
              {configuredCount}/{totalRequired} fields configured
            </div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px" }}>
            {isReady
              ? <CloudCheck size={16} style={{ color: "var(--status-healthy)" }} />
              : <CloudX size={16} style={{ color: "var(--text-tertiary)" }} />
            }
            <span style={{ color: isReady ? "var(--status-healthy)" : enabled ? "var(--status-warning)" : "var(--text-tertiary)", fontWeight: 500 }}>
              {enabled ? (isReady ? t("cloud.ready") : t("cloud.incomplete")) : t("cloud.disabled")}
            </span>
          </div>
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
              transition: "all 0.12s ease",
            }}
          >
            {enabled ? t("cloud.enabled") : t("cloud.disabled")}
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
            {[
              { label: t("cloud.th.setting"), align: "left" as const, w: undefined },
              { label: t("cloud.th.value"), align: "left" as const, w: undefined },
              { label: "", align: "right" as const, w: "48px" },
            ].map((h, idx, arr) => (
              <th key={h.label || `a-${idx}`} style={{
                textAlign: h.align,
                fontSize: "10px", fontWeight: 600, fontFamily: "Inter, sans-serif",
                color: "var(--text-tertiary)", letterSpacing: "0.07em", textTransform: "uppercase",
                padding: idx === 0 ? "0 8px 10px 0" : idx === arr.length - 1 ? "0 0 10px 8px" : "0 8px 10px 8px",
                borderBottom: "1px solid var(--border)",
                width: h.w,
              }}>
                {h.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {fields.map(([key, field], i) => {
            const isEdit = editing === key;
            const descKey = FIELD_DESC_MAP[`${provider}.${key}`];
            const desc = descKey ? t(descKey) : field.description || null;
            return (
              <tr key={key} style={{ borderBottom: i < fields.length - 1 ? "1px solid var(--border)" : "none" }}>
                <td style={{ padding: "10px 8px 10px 0" }}>
                  <code className="font-mono" style={{ fontSize: "11px", color: "var(--text-primary)" }}>
                    {key}
                  </code>
                  {desc && (
                    <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "2px" }}>
                      {desc}
                    </div>
                  )}
                </td>
                <td style={{ padding: "10px 8px" }}>
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
                      placeholder={desc ?? key}
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
                <td style={{ padding: "10px 0 10px 8px", textAlign: "right", whiteSpace: "nowrap" }}>
                  {isEdit ? (
                    <>
                      <button type="button" style={{ ...iconBtn, color: "var(--status-healthy)" }} onClick={() => saveEdit(key)} disabled={saving} title="Save">
                        <Check size={15} weight="bold" />
                      </button>
                      <button type="button" style={iconBtn} onClick={() => setEditing(null)} title="Cancel">
                        <X size={15} weight="bold" />
                      </button>
                    </>
                  ) : (
                    <button type="button" style={iconBtn} onClick={() => { setEditing(key); setEditVal(field.value); }} title="Edit">
                      <PencilSimple size={14} />
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Env var section */}
      {meta.envVars.length > 0 && (
        <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid var(--border)" }}>
          <SectionLabel>{t("cloud.secrets_hint")}</SectionLabel>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "6px" }}>
            {meta.envVars.map((v) => (
              <div key={v.name} style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <code className="font-mono" style={{
                  fontSize: "11px", padding: "2px 8px",
                  background: "color-mix(in srgb, var(--text-tertiary) 10%, transparent)",
                  borderRadius: "4px", color: "var(--text-secondary)",
                }}>
                  {v.name}
                </code>
                <span style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>
                  {v.desc}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

export default function CloudConfigClient({ initial }: { initial: CloudData }) {
  const t = useT();
  return (
    <div>
      {Object.entries(initial).map(([provider, config]) => (
        <ProviderCard key={provider} provider={provider} config={config} />
      ))}
      <p style={{ fontSize: "12px", color: "var(--text-tertiary)", marginTop: "8px" }}>
        {t("cloud.credentials_note")}
      </p>
    </div>
  );
}
