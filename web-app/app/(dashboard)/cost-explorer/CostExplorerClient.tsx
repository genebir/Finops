"use client";

import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { useCallback, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface DailyCost { charge_date: string; cost: number; }
interface ServiceCost { service_name: string; cost: number; pct: number; }
interface ExplorerData {
  daily: DailyCost[];
  by_service: ServiceCost[];
  total: number;
  avg_daily: number;
}

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

export default function CostExplorerClient({ teams }: { teams: string[] }) {
  const [team, setTeam] = useState("");
  const [env, setEnv] = useState("");
  const [data, setData] = useState<ExplorerData | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (team) params.set("team", team);
    if (env) params.set("env", env);
    try {
      const res = await fetch(`${API}/api/cost-explorer?${params}`);
      if (res.ok) setData(await res.json());
    } finally {
      setLoading(false);
    }
  }, [team, env]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      {/* Filters */}
      <div style={{ display: "flex", gap: "12px", marginBottom: "24px", alignItems: "center" }}>
        <select value={team} onChange={(e) => setTeam(e.target.value)} style={selectStyle}>
          <option value="">All Teams</option>
          {teams.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={env} onChange={(e) => setEnv(e.target.value)} style={selectStyle}>
          <option value="">All Envs</option>
          {["prod", "staging", "dev"].map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
        {loading && (
          <span style={{ fontSize: "12px", color: "var(--text-tertiary)", fontFamily: "Inter, sans-serif" }}>
            Loading…
          </span>
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
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginTop: "8px",
              }}
            >
              <span style={{ fontSize: "11px", color: "var(--text-tertiary)", fontFamily: "Inter, sans-serif" }}>
                {data.daily[0]?.charge_date}
              </span>
              <span style={{ fontSize: "11px", color: "var(--text-tertiary)", fontFamily: "Inter, sans-serif" }}>
                {data.daily[data.daily.length - 1]?.charge_date}
              </span>
            </div>
          </Card>

          <Card>
            <CardHeader>Cost by Service</CardHeader>
            <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              {data.by_service.map((s) => (
                <div key={s.service_name} style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <span
                    style={{
                      width: "160px",
                      fontSize: "13px",
                      fontWeight: 500,
                      color: "var(--text-primary)",
                      flexShrink: 0,
                      fontFamily: "Inter, sans-serif",
                    }}
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
