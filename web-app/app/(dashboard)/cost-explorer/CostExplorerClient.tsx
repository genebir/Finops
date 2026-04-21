"use client";

import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { DailyCost, ExplorerData, FiltersData } from "@/lib/types";

const selectStyle: React.CSSProperties = {
  fontFamily: "Inter, sans-serif",
  fontSize: "13px",
  padding: "8px 12px",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-button)",
  background: "var(--bg-warm)",
  color: "var(--text-primary)",
  cursor: "pointer",
  outline: "none",
};

const dateStyle: React.CSSProperties = {
  ...selectStyle,
  fontFamily: '"JetBrains Mono", monospace',
  fontSize: "12px",
  minWidth: "140px",
};

const PROVIDER_COLORS: Record<string, string> = {
  aws: "var(--provider-aws)",
  gcp: "var(--provider-gcp)",
  azure: "var(--provider-azure)",
};

function DailyBarChart({ data }: { data: DailyCost[] }) {
  if (!data.length) return null;
  const max = Math.max(...data.map((d) => d.cost));
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: "3px", height: "100px" }}>
      {data.map((d) => (
        <div
          key={d.charge_date}
          title={`${d.charge_date}: $${d.cost.toFixed(0)}`}
          style={{
            flex: 1,
            height: `${(d.cost / max) * 100}%`,
            minHeight: "2px",
            background: "var(--provider-aws)",
            borderRadius: "3px 3px 0 0",
            opacity: 0.8,
            transition: "opacity 0.15s",
            cursor: "default",
          }}
          onMouseEnter={(e) => ((e.currentTarget as HTMLDivElement).style.opacity = "1")}
          onMouseLeave={(e) => ((e.currentTarget as HTMLDivElement).style.opacity = "0.8")}
        />
      ))}
    </div>
  );
}

export default function CostExplorerClient({ filters }: { filters: FiltersData }) {
  const [team, setTeam] = useState("");
  const [env, setEnv] = useState("");
  const [provider, setProvider] = useState("");
  const [service, setService] = useState("");
  const [start, setStart] = useState(filters.date_min ?? "");
  const [end, setEnd] = useState(filters.date_max ?? "");
  const [data, setData] = useState<ExplorerData | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.costExplorer({
        team: team || undefined,
        env: env || undefined,
        provider: provider || undefined,
        service: service || undefined,
        start: start || undefined,
        end: end || undefined,
      });
      setData(res);
    } finally {
      setLoading(false);
    }
  }, [team, env, provider, service, start, end]);

  useEffect(() => { load(); }, [load]);

  const appliedCount = useMemo(
    () => [team, env, provider, service].filter(Boolean).length,
    [team, env, provider, service],
  );

  return (
    <div>
      <div
        style={{
          display: "flex",
          gap: "10px",
          marginBottom: "24px",
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <select value={team} onChange={(e) => setTeam(e.target.value)} style={selectStyle}>
          <option value="">All Teams</option>
          {filters.teams.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>

        <select value={env} onChange={(e) => setEnv(e.target.value)} style={selectStyle}>
          <option value="">All Envs</option>
          {filters.envs.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>

        <select value={provider} onChange={(e) => setProvider(e.target.value)} style={selectStyle}>
          <option value="">All Providers</option>
          {filters.providers.map((p) => <option key={p} value={p}>{p.toUpperCase()}</option>)}
        </select>

        <select value={service} onChange={(e) => setService(e.target.value)} style={selectStyle}>
          <option value="">All Services</option>
          {filters.services.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        <div style={{ display: "flex", alignItems: "center", gap: "6px", marginLeft: "auto" }}>
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            min={filters.date_min ?? undefined}
            max={filters.date_max ?? undefined}
            style={dateStyle}
          />
          <span style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>—</span>
          <input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            min={filters.date_min ?? undefined}
            max={filters.date_max ?? undefined}
            style={dateStyle}
          />
        </div>

        {loading && (
          <span style={{ fontSize: "12px", color: "var(--text-tertiary)", fontFamily: "Inter, sans-serif" }}>
            Loading…
          </span>
        )}
        {!loading && appliedCount > 0 && (
          <button
            onClick={() => {
              setTeam(""); setEnv(""); setProvider(""); setService("");
            }}
            style={{
              ...selectStyle,
              fontSize: "12px",
              padding: "6px 10px",
              color: "var(--text-tertiary)",
            }}
          >
            Clear {appliedCount} filter{appliedCount > 1 ? "s" : ""}
          </button>
        )}
      </div>

      {data && (
        <>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, 1fr)",
              gap: "16px",
              marginBottom: "24px",
            }}
          >
            <MetricCard
              label="Total Cost"
              value={`$${data.total.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
            />
            <MetricCard
              label="Daily Avg"
              value={`$${data.avg_daily.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
            />
          </div>

          <Card style={{ marginBottom: "20px" }}>
            <CardHeader>Daily Cost</CardHeader>
            <DailyBarChart data={data.daily} />
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: "8px" }}>
              <span style={{ fontSize: "11px", color: "var(--text-tertiary)", fontFamily: "Inter, sans-serif" }}>
                {data.daily[0]?.charge_date}
              </span>
              <span style={{ fontSize: "11px", color: "var(--text-tertiary)", fontFamily: "Inter, sans-serif" }}>
                {data.daily[data.daily.length - 1]?.charge_date}
              </span>
            </div>
          </Card>

          {data.by_provider.length > 1 && (
            <Card style={{ marginBottom: "20px" }}>
              <CardHeader>Cost by Provider</CardHeader>
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {data.by_provider.map((p) => (
                  <div key={p.provider} style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <span
                      style={{
                        width: "100px",
                        fontSize: "13px",
                        fontWeight: 500,
                        color: "var(--text-primary)",
                        textTransform: "uppercase",
                        flexShrink: 0,
                        fontFamily: "Inter, sans-serif",
                      }}
                    >
                      {p.provider}
                    </span>
                    <div
                      style={{
                        flex: 1,
                        height: "8px",
                        background: "var(--bg-warm-subtle)",
                        borderRadius: "var(--radius-full)",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          width: `${p.pct}%`,
                          height: "100%",
                          background: PROVIDER_COLORS[p.provider] ?? "var(--text-tertiary)",
                          borderRadius: "var(--radius-full)",
                        }}
                      />
                    </div>
                    <span
                      className="font-mono"
                      style={{ fontSize: "12px", color: "var(--text-secondary)", width: "80px", textAlign: "right" }}
                    >
                      <span className="currency-symbol">$</span>
                      {p.cost.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                    </span>
                    <span
                      style={{
                        fontSize: "11px",
                        color: "var(--text-tertiary)",
                        width: "36px",
                        textAlign: "right",
                        fontFamily: "Inter, sans-serif",
                      }}
                    >
                      {p.pct}%
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          <Card>
            <CardHeader>Cost by Service</CardHeader>
            <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              {data.by_service.map((s) => (
                <div key={s.service_name} style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <span
                    style={{
                      width: "180px",
                      fontSize: "13px",
                      fontWeight: 500,
                      color: "var(--text-primary)",
                      flexShrink: 0,
                      fontFamily: "Inter, sans-serif",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={s.service_name}
                  >
                    {s.service_name}
                  </span>
                  <div
                    style={{
                      flex: 1,
                      height: "8px",
                      background: "var(--bg-warm-subtle)",
                      borderRadius: "var(--radius-full)",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${s.pct}%`,
                        height: "100%",
                        background: "var(--provider-gcp)",
                        borderRadius: "var(--radius-full)",
                      }}
                    />
                  </div>
                  <span
                    className="font-mono"
                    style={{ fontSize: "12px", color: "var(--text-secondary)", width: "80px", textAlign: "right" }}
                  >
                    <span className="currency-symbol">$</span>
                    {s.cost.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                  </span>
                  <span
                    style={{
                      fontSize: "11px",
                      color: "var(--text-tertiary)",
                      width: "36px",
                      textAlign: "right",
                      fontFamily: "Inter, sans-serif",
                    }}
                  >
                    {s.pct}%
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
