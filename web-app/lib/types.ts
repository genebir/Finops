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

export interface RunLogEntry {
  id: number;
  run_id: string;
  asset_key: string;
  partition_key: string | null;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  duration_sec: number | null;
  row_count: number | null;
  error_message: string | null;
}
export interface OpsRunsData {
  runs: RunLogEntry[];
  success_count: number;
  failure_count: number;
  latest_success_at: string | null;
  latest_failure_at: string | null;
}
export interface TableHealthRow {
  table: string; row_count: number; latest_ts: string | null;
}
export interface OpsHealthData {
  db_reachable: boolean;
  tables: TableHealthRow[];
  checked_at: string;
}

export interface BurnRateItem {
  team: string; env: string;
  days_elapsed: number; days_in_month: number;
  mtd_cost: number; daily_avg: number; projected_eom: number;
  budget_amount: number | null;
  projected_utilization: number | null;
  status: string;
  refreshed_at: string | null;
}
export interface BurnRateSummary {
  total_mtd: number; total_projected_eom: number;
  critical_count: number; warning_count: number; on_track_count: number;
}
export interface BurnRateData {
  billing_month: string; items: BurnRateItem[]; summary: BurnRateSummary;
}

export interface SavingsItem {
  resource_id: string; team: string; product: string; env: string;
  provider: string; recommendation_type: string;
  estimated_savings: number; realized_savings: number | null;
  prev_month_cost: number | null; curr_month_cost: number | null;
  status: string;
}
export interface SavingsSummary {
  total_estimated: number; total_realized: number;
  realized_count: number; partial_count: number;
  pending_count: number; cost_increased_count: number;
}
export interface SavingsData {
  billing_month: string; items: SavingsItem[]; summary: SavingsSummary;
}

export interface HeatmapRow { team: string; values: number[] }
export interface CostHeatmapData {
  billing_month: string; dates: string[]; teams: string[];
  matrix: HeatmapRow[]; max_cost: number;
}

export interface AlertHistoryItem {
  id: number;
  alert_type: string;
  severity: string;
  resource_id: string;
  cost_unit_key: string;
  message: string;
  actual_cost: number | null;
  reference_cost: number | null;
  deviation_pct: number | null;
  triggered_at: string;
  acknowledged: boolean;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
}
export interface AlertSummary {
  critical: number; warning: number; info: number; unacknowledged: number;
}
export interface AlertHistoryData {
  items: AlertHistoryItem[]; total: number; summary: AlertSummary;
}

export interface AssetInfo {
  key: string;
  group: string | null;
  description: string | null;
  has_partitions: boolean;
}
export interface AssetListResponse {
  assets: AssetInfo[];
  total: number;
}
export interface PipelinePreset {
  name: string;
  description: string;
  assets: string[];
}
export interface TriggerResult {
  asset_key: string;
  success: boolean;
  error: string | null;
  duration_sec: number | null;
}
export interface TriggerResponse {
  results: TriggerResult[];
  total: number;
  succeeded: number;
  failed: number;
}

export interface DqCheck {
  id: number;
  checked_at: string | null;
  table_name: string;
  column_name: string;
  check_type: string;
  row_count: number | null;
  failed_count: number | null;
  null_ratio: number | null;
  passed: boolean;
  detail: string | null;
}
export interface DqSummary { total: number; passed: number; failed: number }
export interface DataQualityData { checks: DqCheck[]; summary: DqSummary }
