import PageHeader from "@/components/layout/PageHeader";
import AlertsClient from "./AlertsClient";
import { getT } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";

export const metadata = { title: "Alerts — FinOps" };

export default function AlertsPage() {
  const t = getT();
  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={t("page.alerts.title")}
        description={t("page.alerts.desc")}
      />
      <AlertsClient />
    </div>
  );
}
