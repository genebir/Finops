import { API_BASE } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState } from "@/components/primitives/States";
import AllocationClient from "./AllocationClient";

export const dynamic = "force-dynamic";

export const metadata = { title: "Cost Allocation — FinOps" };

async function fetchRules() {
  const res = await fetch(`${API_BASE}/api/cost-allocation/rules`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch allocation rules");
  return res.json();
}

async function fetchAllocated() {
  const res = await fetch(`${API_BASE}/api/cost-allocation`, { cache: "no-store" });
  if (!res.ok) return { items: [], billing_month: "—", total_allocated: 0 };
  return res.json();
}

export default async function CostAllocationPage() {
  let rulesData: { items: unknown[] };
  let allocData: { items: unknown[]; billing_month: string; total_allocated: number };
  try {
    [rulesData, allocData] = await Promise.all([fetchRules(), fetchAllocated()]);
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const totalAllocated = allocData.total_allocated ?? 0;
  const uniqueResources = new Set(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (rulesData.items as any[]).map((r) => r.resource_id)
  ).size;
  const uniqueTeams = new Set(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (rulesData.items as any[]).map((r) => r.team)
  ).size;

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title="Cost Allocation"
        description="Split resource costs across teams — configure allocation rules and view allocated spend"
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "16px", marginBottom: "32px" }}>
        <MetricCard label="Allocation Rules" value={String(rulesData.items.length)} />
        <MetricCard label="Unique Resources" value={String(uniqueResources)} />
        <MetricCard label="Teams" value={String(uniqueTeams)} />
        <MetricCard
          label="Total Allocated"
          value={`$${Math.round(totalAllocated).toLocaleString("en-US")}`}
          sub={allocData.billing_month}
        />
      </div>

      <AllocationClient
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        initialRules={rulesData.items as any}
        billingMonth={allocData.billing_month}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        allocatedItems={allocData.items as any}
      />
    </div>
  );
}
