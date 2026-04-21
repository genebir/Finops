import PageHeader from "@/components/layout/PageHeader";
import { ErrorState } from "@/components/primitives/States";
import { api } from "@/lib/api";
import CostExplorerClient from "./CostExplorerClient";

export default async function CostExplorerPage() {
  let data;
  try { data = await api.overview(); }
  catch (e) { return <ErrorState message={String(e)} />; }

  const teams = data.cost_by_team.map((t) => t.team);

  return (
    <div style={{ maxWidth: "1100px" }}>
      <PageHeader
        title="Cost Explorer"
        description={`${data.period_start} – ${data.period_end}`}
      />
      <CostExplorerClient teams={teams} />
    </div>
  );
}
