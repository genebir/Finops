import PageHeader from "@/components/layout/PageHeader";
import { ErrorState } from "@/components/primitives/States";
import { api } from "@/lib/api";

import ChargebackClient from "./ChargebackClient";

export default async function ChargebackPage() {
  let data;
  try { data = await api.chargeback(); }
  catch (e) { return <ErrorState message={String(e)} />; }

  return (
    <div style={{ maxWidth: "1100px" }}>
      <PageHeader
        title="Chargeback"
        description={`${data.billing_month} — Cost allocation report by team`}
      />
      <ChargebackClient initial={data} />
    </div>
  );
}
