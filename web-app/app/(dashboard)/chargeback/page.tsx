import PageHeader from "@/components/layout/PageHeader";
import { ErrorState } from "@/components/primitives/States";
import { api } from "@/lib/api";
import { getT } from "@/lib/i18n/server";

import ChargebackClient from "./ChargebackClient";

export const dynamic = "force-dynamic";

export const metadata = { title: "Chargeback — FinOps" };

export default async function ChargebackPage() {
  const t = getT();
  let data;
  try { data = await api.chargeback(); }
  catch (e) { return <ErrorState message={String(e)} />; }

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={t("page.chargeback.title")}
        description={`${data.billing_month} — ${t("page.chargeback.desc")}`}
      />
      <ChargebackClient initial={data} />
    </div>
  );
}
