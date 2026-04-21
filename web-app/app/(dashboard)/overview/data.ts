const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface TeamCost {
  team: string;
  cost: number;
  pct: number;
}

export interface TopResource {
  resource_id: string;
  resource_name: string | null;
  service_name: string | null;
  region_id: string | null;
  team: string;
  product: string;
  env: string;
  cost: number;
  active_days: number;
}

export interface OverviewData {
  period_start: string;
  period_end: string;
  total_cost: number;
  cost_by_team: TeamCost[];
  top_resources: TopResource[];
  anomaly_count: number;
  resource_count: number;
  active_days: number;
}

export async function fetchOverview(): Promise<OverviewData> {
  const res = await fetch(`${API_BASE}/api/overview`, {
    next: { revalidate: 60 },
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json() as Promise<OverviewData>;
}
