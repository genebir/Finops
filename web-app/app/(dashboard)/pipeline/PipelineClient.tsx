"use client";

import { Card, CardHeader, SectionLabel } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState } from "@/components/primitives/States";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { api, API_BASE } from "@/lib/api";
import type { AssetInfo, PipelinePreset, TriggerResponse, TriggerResult } from "@/lib/types";
import { useEffect, useState } from "react";

const GROUP_ORDER = ["ingestion", "transform", "marts", "analytics", "forecast", "budget", "compliance", "support"];

function groupAssets(assets: AssetInfo[]): Map<string, AssetInfo[]> {
  const grouped = new Map<string, AssetInfo[]>();
  for (const g of GROUP_ORDER) grouped.set(g, []);
  for (const a of assets) {
    const g = a.group ?? "other";
    if (!grouped.has(g)) grouped.set(g, []);
    grouped.get(g)!.push(a);
  }
  return grouped;
}

function fmtDuration(sec: number | null): string {
  if (sec === null || sec === undefined) return "--";
  if (sec < 1) return `${Math.round(sec * 1000)}ms`;
  if (sec < 60) return `${sec.toFixed(1)}s`;
  return `${(sec / 60).toFixed(1)}m`;
}

export default function PipelineClient({ initialAssets, initialPresets }: {
  initialAssets: AssetInfo[];
  initialPresets: PipelinePreset[];
}) {
  const [assets] = useState(initialAssets);
  const [presets] = useState(initialPresets);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [partitionKey, setPartitionKey] = useState("2024-01-01");
  const [running, setRunning] = useState(false);
  const [lastResult, setLastResult] = useState<TriggerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const grouped = groupAssets(assets);

  function toggleAsset(key: string) {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function selectPreset(preset: PipelinePreset) {
    setSelected(new Set(preset.assets));
  }

  function selectAll() {
    setSelected(new Set(assets.map(a => a.key)));
  }

  function selectNone() {
    setSelected(new Set());
  }

  async function handleTrigger() {
    if (selected.size === 0) return;
    setRunning(true);
    setError(null);
    setLastResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/pipeline/trigger`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          assets: Array.from(selected),
          partition_key: partitionKey || null,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        setError(`${res.status}: ${text}`);
      } else {
        const data: TriggerResponse = await res.json();
        setLastResult(data);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      {/* Quick presets */}
      <Card style={{ marginBottom: 24 }}>
        <CardHeader>Quick Presets</CardHeader>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          {presets.map(p => (
            <button
              key={p.name}
              onClick={() => selectPreset(p)}
              style={{
                padding: "8px 16px",
                borderRadius: "var(--radius-button)",
                border: "1px solid var(--border)",
                background: "var(--bg-warm)",
                cursor: "pointer",
                fontFamily: "Inter, sans-serif",
                fontSize: "13px",
                fontWeight: 500,
                color: "var(--text-primary)",
                transition: "all 0.12s ease",
              }}
              title={p.description}
            >
              {p.name.replace(/_/g, " ")}
            </button>
          ))}
          <button
            onClick={selectAll}
            style={{
              padding: "8px 16px",
              borderRadius: "var(--radius-button)",
              border: "1px solid var(--border)",
              background: "transparent",
              cursor: "pointer",
              fontFamily: "Inter, sans-serif",
              fontSize: "13px",
              color: "var(--text-secondary)",
            }}
          >
            Select All
          </button>
          <button
            onClick={selectNone}
            style={{
              padding: "8px 16px",
              borderRadius: "var(--radius-button)",
              border: "1px solid var(--border)",
              background: "transparent",
              cursor: "pointer",
              fontFamily: "Inter, sans-serif",
              fontSize: "13px",
              color: "var(--text-secondary)",
            }}
          >
            Clear
          </button>
        </div>
      </Card>

      {/* Asset selection grid */}
      <Card style={{ marginBottom: 24 }}>
        <CardHeader>Select Assets ({selected.size} selected)</CardHeader>
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          {Array.from(grouped.entries()).map(([group, items]) => {
            if (items.length === 0) return null;
            const allSelected = items.every(a => selected.has(a.key));
            return (
              <div key={group}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                  <button
                    onClick={() => {
                      const keys = items.map(a => a.key);
                      setSelected(prev => {
                        const next = new Set(prev);
                        if (allSelected) {
                          keys.forEach(k => next.delete(k));
                        } else {
                          keys.forEach(k => next.add(k));
                        }
                        return next;
                      });
                    }}
                    style={{
                      padding: "2px 10px",
                      borderRadius: "var(--radius-full)",
                      border: "1px solid var(--border)",
                      background: allSelected ? "var(--text-primary)" : "transparent",
                      color: allSelected ? "var(--bg-warm)" : "var(--text-secondary)",
                      cursor: "pointer",
                      fontFamily: "Inter, sans-serif",
                      fontSize: "11px",
                      fontWeight: 600,
                      letterSpacing: "0.05em",
                      textTransform: "uppercase" as const,
                    }}
                  >
                    {group}
                  </button>
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                  {items.map(a => (
                    <button
                      key={a.key}
                      onClick={() => toggleAsset(a.key)}
                      title={a.description ?? a.key}
                      style={{
                        padding: "4px 12px",
                        borderRadius: "var(--radius-button)",
                        border: selected.has(a.key)
                          ? "1px solid var(--accent)"
                          : "1px solid var(--border)",
                        background: selected.has(a.key)
                          ? "rgba(217,119,87,0.1)"
                          : "transparent",
                        color: selected.has(a.key)
                          ? "var(--accent)"
                          : "var(--text-secondary)",
                        cursor: "pointer",
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: "11px",
                        fontWeight: 500,
                        transition: "all 0.12s ease",
                      }}
                    >
                      {a.key}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Trigger controls */}
      <Card style={{ marginBottom: 24 }}>
        <CardHeader>Run Pipeline</CardHeader>
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div>
            <label
              style={{
                display: "block",
                fontSize: "11px",
                fontWeight: 600,
                color: "var(--text-tertiary)",
                letterSpacing: "0.07em",
                textTransform: "uppercase" as const,
                marginBottom: "4px",
              }}
            >
              Partition Key
            </label>
            <input
              type="text"
              value={partitionKey}
              onChange={e => setPartitionKey(e.target.value)}
              placeholder="YYYY-MM-DD"
              style={{
                padding: "8px 12px",
                borderRadius: "var(--radius-input)",
                border: "1px solid var(--border)",
                background: "var(--bg-warm)",
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: "13px",
                color: "var(--text-primary)",
                width: "160px",
              }}
            />
          </div>
          <div style={{ flex: 1 }} />
          <button
            onClick={handleTrigger}
            disabled={running || selected.size === 0}
            style={{
              padding: "10px 28px",
              borderRadius: "var(--radius-button)",
              border: "none",
              background: running || selected.size === 0
                ? "var(--border)"
                : "var(--accent)",
              color: running || selected.size === 0
                ? "var(--text-tertiary)"
                : "#fff",
              cursor: running || selected.size === 0 ? "not-allowed" : "pointer",
              fontFamily: "Inter, sans-serif",
              fontSize: "14px",
              fontWeight: 600,
              transition: "all 0.15s ease",
            }}
          >
            {running ? "Running..." : `Trigger ${selected.size} Asset${selected.size !== 1 ? "s" : ""}`}
          </button>
        </div>
      </Card>

      {/* Error */}
      {error && (
        <Card style={{ marginBottom: 24, borderColor: "var(--status-critical)" }}>
          <p style={{ color: "var(--status-critical)", fontSize: "13px", fontWeight: 500 }}>
            {error}
          </p>
        </Card>
      )}

      {/* Results */}
      {lastResult && (
        <Card>
          <CardHeader>Run Results</CardHeader>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: "16px",
              marginBottom: "24px",
            }}
          >
            <MetricCard
              label="Total"
              value={String(lastResult.total)}
            />
            <MetricCard
              label="Succeeded"
              value={String(lastResult.succeeded)}
              valueColor="var(--status-healthy)"
            />
            <MetricCard
              label="Failed"
              value={String(lastResult.failed)}
              valueColor={lastResult.failed > 0 ? "var(--status-critical)" : "var(--text-primary)"}
            />
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                <th style={{ textAlign: "left", padding: "0 8px 12px 0", fontWeight: 600, color: "var(--text-tertiary)" }}>Asset</th>
                <th style={{ textAlign: "center", padding: "0 8px 12px 8px", fontWeight: 600, color: "var(--text-tertiary)" }}>Status</th>
                <th style={{ textAlign: "right", padding: "0 8px 12px 8px", fontWeight: 600, color: "var(--text-tertiary)" }}>Duration</th>
                <th style={{ textAlign: "left", padding: "0 0 12px 8px", fontWeight: 600, color: "var(--text-tertiary)" }}>Error</th>
              </tr>
            </thead>
            <tbody>
              {lastResult.results.map(r => (
                <tr key={r.asset_key} style={{ borderBottom: "1px solid rgba(0,0,0,0.04)" }}>
                  <td style={{ padding: "10px 8px 10px 0", fontFamily: "'JetBrains Mono', monospace", color: "var(--text-primary)" }}>
                    {r.asset_key}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center" }}>
                    <SeverityBadge severity={r.success ? "success" : "failure"} />
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right", fontFamily: "'JetBrains Mono', monospace", color: "var(--text-secondary)" }}>
                    {fmtDuration(r.duration_sec)}
                  </td>
                  <td style={{
                    padding: "10px 0 10px 8px",
                    color: "var(--status-critical)",
                    maxWidth: "400px",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}>
                    {r.error ?? ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
