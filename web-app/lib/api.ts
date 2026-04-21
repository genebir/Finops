import type {
  AnomaliesData, BudgetData, ChargebackData, ExplorerData, ForecastData,
  OverviewData, RecommendationsData, SettingsData,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const OPTS = { next: { revalidate: 60 } } as const;

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE}${path}`);
  if (params) Object.entries(params).forEach(([k, v]) => v && url.searchParams.set(k, v));
  const res = await fetch(url.toString(), OPTS);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  overview: () => get<OverviewData>("/api/overview"),
  anomalies: (p?: { severity?: string }) => get<AnomaliesData>("/api/anomalies", p),
  forecast: () => get<ForecastData>("/api/forecast"),
  budget: () => get<BudgetData>("/api/budget"),
  costExplorer: (p?: { team?: string; env?: string; service?: string }) =>
    get<ExplorerData>("/api/cost-explorer", p),
  recommendations: () => get<RecommendationsData>("/api/recommendations"),
  chargeback: () => get<ChargebackData>("/api/chargeback"),
  settings: () => get<SettingsData>("/api/settings"),
};
