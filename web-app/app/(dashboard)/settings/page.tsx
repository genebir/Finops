import PageHeader from "@/components/layout/PageHeader";
import { ErrorState } from "@/components/primitives/States";
import { api } from "@/lib/api";

import SettingsClient from "./SettingsClient";

export default async function SettingsPage() {
  let data;
  try { data = await api.settings(); }
  catch (e) { return <ErrorState message={String(e)} />; }

  return (
    <div style={{ maxWidth: "900px" }}>
      <PageHeader
        title="Settings"
        description="platform_settings — Runtime thresholds (editable inline, no Dagster restart needed)"
      />
      <SettingsClient initial={data.items} />
    </div>
  );
}
