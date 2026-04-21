import PageHeader from "@/components/layout/PageHeader";
import OpsClient from "./OpsClient";

export const dynamic = "force-dynamic";

export default function OpsPage() {
  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title="Ops"
        description="Pipeline run log, database health, and live metrics. Auto-refresh every 10s."
      />
      <OpsClient />
    </div>
  );
}
