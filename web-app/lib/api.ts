import type {
  AlertHistoryData, AlertHistoryItem,
  AnomaliesData, AssetListResponse, BudgetData, BudgetEntry, BudgetEntryList, BurnRateData,
  ChargebackData, CostHeatmapData, DataQualityData, ExplorerData, FiltersData, ForecastData,
  OpsHealthData, OpsRunsData, OverviewData, PipelinePreset, RecommendationsData,
  SavingsData, SettingItem, SettingsData, TriggerResponse,
} from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const READ_OPTS = { next: { revalidate: 60 } } as const;
const FRESH_OPTS = { cache: "no-store" } as const;

function buildUrl(path: string, params?: Record<string, string | undefined>): string {
  const url = new URL(`${API_BASE}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") url.searchParams.set(k, v);
    });
  }
  return url.toString();
}

async function get<T>(path: string, params?: Record<string, string | undefined>): Promise<T> {
  const res = await fetch(buildUrl(path, params), READ_OPTS);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function getFresh<T>(path: string, params?: Record<string, string | undefined>): Promise<T> {
  const res = await fetch(buildUrl(path, params), FRESH_OPTS);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function send<T>(
  method: "POST" | "PUT" | "DELETE",
  path: string,
  body?: unknown,
  params?: Record<string, string | undefined>,
): Promise<T | null> {
  const res = await fetch(buildUrl(path, params), {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} — ${text}`);
  }
  if (res.status === 204) return null;
  return res.json() as Promise<T>;
}

export const api = {
  overview: (p?: { start?: string; end?: string; provider?: string }) =>
    get<OverviewData>("/api/overview", p),

  anomalies: (p?: { severity?: string; team?: string; env?: string }) =>
    get<AnomaliesData>("/api/anomalies", p),

  forecast: () => get<ForecastData>("/api/forecast"),

  budget: () => get<BudgetData>("/api/budget"),
  budgetEntries: (p?: { billing_month?: string }) =>
    getFresh<BudgetEntryList>("/api/budget/entries", p),
  createBudget: (body: {
    team: string; env: string; budget_amount: number; billing_month?: string;
  }) => send<BudgetEntry>("POST", "/api/budget", body),
  updateBudget: (team: string, env: string, amount: number, billing_month = "default") =>
    send<BudgetEntry>("PUT", `/api/budget/${encodeURIComponent(team)}/${encodeURIComponent(env)}`,
      { budget_amount: amount }, { billing_month }),
  deleteBudget: (team: string, env: string, billing_month = "default") =>
    send<null>("DELETE", `/api/budget/${encodeURIComponent(team)}/${encodeURIComponent(env)}`,
      undefined, { billing_month }),

  costExplorer: (p?: {
    team?: string; env?: string; service?: string; provider?: string;
    start?: string; end?: string;
  }) => get<ExplorerData>("/api/cost-explorer", p),

  recommendations: () => get<RecommendationsData>("/api/recommendations"),

  chargeback: (p?: { billing_month?: string }) =>
    get<ChargebackData>("/api/chargeback", p),

  settings: () => get<SettingsData>("/api/settings"),
  createSetting: (body: {
    key: string; value: string; value_type?: string; description?: string;
  }) => send<SettingItem>("POST", "/api/settings", body),
  updateSetting: (key: string, value: string) =>
    send<SettingItem>("PUT", `/api/settings/${encodeURIComponent(key)}`, { value }),
  deleteSetting: (key: string) =>
    send<null>("DELETE", `/api/settings/${encodeURIComponent(key)}`),

  filters: () => getFresh<FiltersData>("/api/filters"),

  opsRuns: (limit?: number) =>
    getFresh<OpsRunsData>("/api/ops/runs", limit ? { limit: String(limit) } : undefined),
  opsHealth: () => getFresh<OpsHealthData>("/api/ops/health"),

  dataQuality: () => getFresh<DataQualityData>("/api/data-quality"),
  exportUrl: (table: string) => `${API_BASE}/api/export/${encodeURIComponent(table)}`,

  burnRate: (billing_month?: string) =>
    get<BurnRateData>("/api/burn-rate", billing_month ? { billing_month } : undefined),

  alerts: (p?: { severity?: string; acknowledged?: string; alert_type?: string; limit?: string }) =>
    getFresh<AlertHistoryData>("/api/alerts", p),
  acknowledgeAlert: (id: number, acknowledged_by = "dashboard") =>
    send<AlertHistoryItem>("POST", `/api/alerts/${id}/acknowledge`, { acknowledged_by }),

  savings: (p?: { billing_month?: string; team?: string; status?: string }) =>
    get<SavingsData>("/api/savings", p),

  costHeatmap: (p?: { billing_month?: string; provider?: string; team?: string }) =>
    get<CostHeatmapData>("/api/cost-heatmap", p),

  pipelineAssets: () => getFresh<AssetListResponse>("/api/pipeline/assets"),
  pipelinePresets: () => getFresh<PipelinePreset[]>("/api/pipeline/presets"),
  triggerPipeline: (assets: string[], partition_key?: string) =>
    send<TriggerResponse>("POST", "/api/pipeline/trigger", { assets, partition_key }),
};
