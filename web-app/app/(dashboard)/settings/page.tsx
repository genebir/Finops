import PageHeader from "@/components/layout/PageHeader";
import { ErrorState } from "@/components/primitives/States";
import { API_BASE, api } from "@/lib/api";

import SettingsClient from "./SettingsClient";
import CloudConfigClient from "./CloudConfigClient";

async function fetchCloudConfig() {
  const res = await fetch(`${API_BASE}/api/cloud-config`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load cloud config");
  return res.json();
}

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  let settingsData;
  let cloudData;
  try {
    settingsData = await api.settings();
    cloudData = await fetchCloudConfig();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  return (
    <div style={{ maxWidth: "960px" }}>
      <PageHeader
        title="Settings"
        description="Runtime configuration — changes take effect on next Dagster asset run"
      />

      {/* Tab label */}
      <div style={{ marginBottom: "24px", borderBottom: "1px solid var(--border)", display: "flex", gap: "0" }}>
        {["Platform Settings", "Cloud Connections"].map((tab, i) => (
          <div
            key={tab}
            id={`tab-${i}`}
            style={{
              padding: "10px 20px",
              fontSize: "13px",
              fontWeight: 600,
              color: i === 0 ? "var(--text-primary)" : "var(--text-secondary)",
              borderBottom: i === 0 ? "2px solid var(--text-primary)" : "2px solid transparent",
              cursor: "default",
            }}
          >
            {tab}
          </div>
        ))}
      </div>

      {/* Note: tabs are visually shown but rendered as two stacked sections for SSR simplicity */}
      <SettingsClient initial={settingsData.items} />

      <div style={{ marginTop: "48px", paddingTop: "32px", borderTop: "2px solid var(--border)" }}>
        <div style={{ marginBottom: "24px" }}>
          <h2
            className="font-display"
            style={{ fontSize: "20px", color: "var(--text-primary)", marginBottom: "4px" }}
          >
            Cloud Connections
          </h2>
          <p style={{ fontSize: "14px", color: "var(--text-secondary)" }}>
            Configure cloud provider integration — credentials go to environment variables, non-sensitive config stored here.
          </p>
        </div>
        <CloudConfigClient initial={cloudData} />
      </div>
    </div>
  );
}
