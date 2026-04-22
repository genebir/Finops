import PageHeader from "@/components/layout/PageHeader";
import { ErrorState } from "@/components/primitives/States";
import { API_BASE, api } from "@/lib/api";
import { getT } from "@/lib/i18n/server";

import SettingsTabs from "./SettingsTabs";

async function fetchCloudConfig() {
  const res = await fetch(`${API_BASE}/api/cloud-config`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load cloud config");
  return res.json();
}

export const dynamic = "force-dynamic";

export const metadata = { title: "Settings — FinOps" };

export default async function SettingsPage() {
  const t = getT();
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
        title={t("page.settings.title")}
        description={t("page.settings.desc")}
      />
      <SettingsTabs settingsItems={settingsData.items} cloudData={cloudData} />
    </div>
  );
}
