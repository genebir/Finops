import PageHeader from "@/components/layout/PageHeader";
import { getT } from "@/lib/i18n/server";
import DataQualityClient from "./DataQualityClient";

export const dynamic = "force-dynamic";

export const metadata = { title: "Data Quality — FinOps" };

export default function DataQualityPage() {
  const t = getT();
  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={t("page.data_quality.title")}
        description={t("page.data_quality.desc")}
      />
      <DataQualityClient />
    </div>
  );
}
