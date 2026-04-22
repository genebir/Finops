import PageHeader from "@/components/layout/PageHeader";
import { API_BASE } from "@/lib/api";
import type { AssetInfo, AssetListResponse, PipelinePreset } from "@/lib/types";
import { ErrorState } from "@/components/primitives/States";
import { getT } from "@/lib/i18n/server";
import PipelineClient from "./PipelineClient";

export const dynamic = "force-dynamic";

export const metadata = { title: "Pipeline — FinOps" };

async function fetchAssets(): Promise<AssetInfo[]> {
  const res = await fetch(`${API_BASE}/api/pipeline/assets`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status}`);
  const data: AssetListResponse = await res.json();
  return data.assets;
}

async function fetchPresets(): Promise<PipelinePreset[]> {
  const res = await fetch(`${API_BASE}/api/pipeline/presets`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export default async function PipelinePage() {
  const t = getT();
  let assets: AssetInfo[];
  let presets: PipelinePreset[];
  try {
    [assets, presets] = await Promise.all([fetchAssets(), fetchPresets()]);
  } catch (e) {
    return (
      <div style={{ maxWidth: "1200px" }}>
        <PageHeader
          title={t("page.pipeline.title")}
          description={t("page.pipeline.desc")}
        />
        <ErrorState message={String(e)} />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={t("page.pipeline.title")}
        description={t("page.pipeline.desc")}
      />
      <PipelineClient initialAssets={assets} initialPresets={presets} />
    </div>
  );
}
