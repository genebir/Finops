import PageHeader from "@/components/layout/PageHeader";
import { getT } from "@/lib/i18n/server";
import OpsClient from "./OpsClient";

export const dynamic = "force-dynamic";

export const metadata = { title: "Operations — FinOps" };

export default function OpsPage() {
  const t = getT();
  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={t("page.ops.title")}
        description={t("page.ops.desc")}
      />
      <OpsClient />
    </div>
  );
}
