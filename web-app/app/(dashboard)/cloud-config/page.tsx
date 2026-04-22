import PageHeader from "@/components/layout/PageHeader";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState } from "@/components/primitives/States";
import { API_BASE } from "@/lib/api";
import CloudConfigClient from "./CloudConfigClient";

export const dynamic = "force-dynamic";

export const metadata = { title: "Cloud Config — FinOps" };

interface ProviderStatus {
  enabled: boolean;
  configured: boolean;
  missing_keys: string[];
}

async function fetchConfig(): Promise<Record<string, Record<string, { value: string; value_type: string; description: string | null }>>> {
  const res = await fetch(`${API_BASE}/api/cloud-config`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

async function fetchStatus(): Promise<Record<string, ProviderStatus>> {
  const res = await fetch(`${API_BASE}/api/cloud-config/status`, { cache: "no-store" });
  if (!res.ok) return {};
  const data = await res.json();
  return data.providers ?? {};
}

export default async function CloudConfigPage() {
  let config: Record<string, Record<string, { value: string; value_type: string; description: string | null }>>;
  let status: Record<string, ProviderStatus>;

  try {
    [config, status] = await Promise.all([fetchConfig(), fetchStatus()]);
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const enabledCount = Object.values(status).filter((s) => s.enabled).length;
  const configuredCount = Object.values(status).filter((s) => s.configured && s.enabled).length;
  const missingTotal = Object.values(status).reduce((sum, s) => sum + s.missing_keys.length, 0);

  return (
    <div style={{ maxWidth: "960px" }}>
      <PageHeader
        title="Cloud Config"
        description="Cloud provider connection settings — AWS, GCP, Azure"
      />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "16px",
          marginBottom: "32px",
        }}
      >
        <MetricCard
          label="Providers Enabled"
          value={`${enabledCount} / 3`}
          sub="active connections"
        />
        <MetricCard
          label="Fully Configured"
          value={String(configuredCount)}
          sub="ready to connect"
        />
        <MetricCard
          label="Missing Fields"
          value={String(missingTotal)}
          valueColor={missingTotal > 0 ? "var(--status-warning)" : "var(--status-healthy)"}
          sub="required values"
        />
      </div>

      <CloudConfigClient initialConfig={config} initialStatus={status} />
    </div>
  );
}
