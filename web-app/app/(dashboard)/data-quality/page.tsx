import PageHeader from "@/components/layout/PageHeader";
import DataQualityClient from "./DataQualityClient";

export const dynamic = "force-dynamic";

export default function DataQualityPage() {
  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title="Data Quality"
        description="Pipeline output validation — row counts, null checks, cost sanity. Auto-refresh every 30s."
      />
      <DataQualityClient />
    </div>
  );
}
