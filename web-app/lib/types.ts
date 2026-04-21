export interface TeamCost { team: string; cost: number; pct: number }
export interface TopResource {
  resource_id: string; resource_name: string | null;
  service_name: string | null; region_id: string | null;
  team: string; product: string; env: string;
  cost: number; active_days: number;
}
export interface OverviewData {
  period_start: string; period_end: string;
  total_cost: number; cost_by_team: TeamCost[];
  top_resources: TopResource[]; anomaly_count: number;
  resource_count: number; active_days: number;
}
export interface AnomalyItem {
  resource_id: string; cost_unit_key: string;
  team: string; product: string; env: string;
  charge_date: string; effective_cost: number;
  z_score: number; severity: string; detector_name: string;
}
export interface AnomaliesData {
  items: AnomalyItem[]; total: number; critical: number; warning: number;
}
export interface ForecastItem {
  resource_id: string; monthly_forecast: number;
  actual_cost: number | null; variance_pct: number | null;
  lower_bound: number; upper_bound: number; source: string;
}
export interface ForecastData {
  items: ForecastItem[]; total_forecast: number; total_actual: number;
}
export interface BudgetItem {
  team: string; env: string; budget_amount: number;
  actual_cost: number; used_pct: number; status: string;
}
export interface BudgetData {
  items: BudgetItem[]; total_budget: number; total_actual: number;
}
export interface BudgetEntry {
  team: string; env: string; budget_amount: number; billing_month: string;
}
export interface BudgetEntryList { items: BudgetEntry[] }
export interface DailyCost { charge_date: string; cost: number }
export interface ServiceCost { service_name: string; cost: number; pct: number }
export interface ProviderCost { provider: string; cost: number; pct: number }
export interface ExplorerData {
  daily: DailyCost[];
  by_service: ServiceCost[];
  by_provider: ProviderCost[];
  total: number;
  avg_daily: number;
}
export interface RecommendationItem {
  rule_type: string; resource_id: string;
  team: string; env: string; description: string;
  potential_savings: number; severity: string;
}
export interface RecommendationsData {
  items: RecommendationItem[]; total_potential_savings: number;
}
export interface ChargebackTeam {
  team: string; cost: number; pct: number; resource_count: number;
}
export interface ChargebackItem {
  team: string; product: string; env: string; cost: number; pct: number;
}
export interface ChargebackData {
  billing_month: string;
  available_months: string[];
  total_cost: number;
  by_team: ChargebackTeam[];
  items: ChargebackItem[];
}
export interface SettingItem {
  key: string; value: string; value_type: string; description: string | null;
}
export interface SettingsData { items: SettingItem[] }
export interface FiltersData {
  teams: string[];
  envs: string[];
  providers: string[];
  services: string[];
  billing_months: string[];
  date_min: string | null;
  date_max: string | null;
}
