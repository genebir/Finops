import PageHeader from "@/components/layout/PageHeader";
import { ErrorState } from "@/components/primitives/States";
import { api } from "@/lib/api";

import CostExplorerClient from "./CostExplorerClient";

export default async function CostExplorerPage() {
  let filters;
  try { filters = await api.filters(); }
  catch (e) { return <ErrorState message={String(e)} />; }

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title="Cost Explorer"
        description={
          filters.date_min && filters.date_max
            ? `${filters.date_min} – ${filters.date_max}`
            : "Explore costs across teams, services, providers, and time."
        }
      />
      <CostExplorerClient filters={filters} />
    </div>
  );
}
