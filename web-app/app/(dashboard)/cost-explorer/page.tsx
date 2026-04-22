import PageHeader from "@/components/layout/PageHeader";
import { ErrorState } from "@/components/primitives/States";
import { api } from "@/lib/api";
import { getT } from "@/lib/i18n/server";

import CostExplorerClient from "./CostExplorerClient";

export const dynamic = "force-dynamic";

export const metadata = { title: "Cost Explorer — FinOps" };

export default async function CostExplorerPage() {
  const t = getT();
  let filters;
  try { filters = await api.filters(); }
  catch (e) { return <ErrorState message={String(e)} />; }

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={t("page.cost_explorer.title")}
        description={
          filters.date_min && filters.date_max
            ? `${filters.date_min} – ${filters.date_max}`
            : t("page.cost_explorer.desc")
        }
      />
      <CostExplorerClient filters={filters} />
    </div>
  );
}
