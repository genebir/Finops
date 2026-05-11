import PageHeader from "@/components/layout/PageHeader";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState } from "@/components/primitives/States";
import { api } from "@/lib/api";
import { getT } from "@/lib/i18n/server";
import AnomaliesClient from "./AnomaliesClient";

export const dynamic = "force-dynamic";

export const metadata = { title: "Anomalies — FinOps" };

export default async function AnomaliesPage() {
  const t = getT();
  let data;
  try { data = await api.anomalies(); }
  catch (e) { return <ErrorState message={String(e)} />; }

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={t("page.anomalies.title")}
        description={t("page.anomalies.desc")}
      />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "16px",
          marginBottom: "32px",
        }}
      >
        <MetricCard label={t("label.total_anomalies")} value={String(data.total)} />
        <MetricCard
          label={t("label.critical")}
          value={String(data.critical)}
          valueColor={data.critical > 0 ? "var(--status-critical)" : "var(--text-primary)"}
        />
        <MetricCard
          label={t("label.warning")}
          value={String(data.warning)}
          valueColor={data.warning > 0 ? "var(--status-warning)" : "var(--text-primary)"}
        />
      </div>

      <AnomaliesClient initialItems={data.items} />
    </div>
  );
}
