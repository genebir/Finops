"use client";

import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState } from "@/components/primitives/States";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { api } from "@/lib/api";
import type { DataQualityData, DqCheck } from "@/lib/types";
import { useEffect, useState } from "react";

const REFRESH_MS = 30_000;

const EXPORTABLE = [
  "fact_daily_cost",
  "anomaly_scores",
  "dim_prophet_forecast",
  "dim_budget_status",
  "dim_chargeback",
  "dim_cost_recommendations",
  "dim_data_quality",
  "dim_fx_rates",
  "pipeline_run_log",
];

function CheckStatus({ passed }: { passed: boolean }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        fontSize: "10px",
        fontWeight: 600,
        letterSpacing: "0.05em",
        textTransform: "uppercase",
        color: passed ? "var(--status-healthy)" : "var(--status-critical)",
        background: passed ? "rgba(127,183,126,0.1)" : "rgba(200,85,61,0.1)",
        border: `1px solid ${passed ? "var(--status-healthy)" : "var(--status-critical)"}`,
        borderRadius: "var(--radius-full)",
        padding: "2px 8px",
      }}
    >
      {passed ? "PASS" : "FAIL"}
    </span>
  );
}

function humanAgo(iso: string | null): string {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return new Date(iso).toLocaleString();
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  return `${Math.floor(min / 60)}h ago`;
}

export default function DataQualityClient() {
  const [data, setData] = useState<DataQualityData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "failed">("all");

  useEffect(() => {
    let alive = true;
    async function tick() {
      try {
        const d = await api.dataQuality();
        if (alive) { setData(d); setError(null); }
      } catch (e) {
        if (alive) setError(String(e));
      }
    }
    tick();
    const t = setInterval(tick, REFRESH_MS);
    return () => { alive = false; clearInterval(t); };
  }, []);

  if (error && !data) return <ErrorState message={error} />;
  if (!data) return <div style={{ color: "var(--text-tertiary)" }}>Loading…</div>;

  const { checks, summary } = data;
  const visible = filter === "failed" ? checks.filter((c) => !c.passed) : checks;
  const passRate = summary.total ? Math.round((summary.passed / summary.total) * 100) : 100;

  return (
    <div>
      {/* Summary KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 32 }}>
        <MetricCard
          label="Total Checks"
          value={String(summary.total)}
          sub="latest run"
        />
        <MetricCard
          label="Passed"
          value={String(summary.passed)}
          valueColor="var(--status-healthy)"
          sub={`${passRate}% pass rate`}
        />
        <MetricCard
          label="Failed"
          value={String(summary.failed)}
          valueColor={summary.failed > 0 ? "var(--status-critical)" : "var(--text-primary)"}
          sub={summary.failed > 0 ? "attention required" : "all good"}
        />
        <MetricCard
          label="Health"
          value={summary.failed === 0 ? "OK" : summary.failed <= 2 ? "WARN" : "FAIL"}
          valueColor={
            summary.failed === 0
              ? "var(--status-healthy)"
              : summary.failed <= 2
              ? "var(--status-warning)"
              : "var(--status-critical)"
          }
          sub="overall pipeline quality"
        />
      </div>

      {/* Check results table */}
      <Card style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <p style={{ fontFamily: "Inter, sans-serif", fontSize: "13px", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>Quality Checks</p>
          <div style={{ display: "flex", gap: 8 }}>
            {(["all", "failed"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                style={{
                  padding: "4px 12px",
                  borderRadius: "var(--radius-full)",
                  border: "1px solid var(--border)",
                  background: filter === f ? "var(--accent)" : "transparent",
                  color: filter === f ? "var(--bg-warm)" : "var(--text-secondary)",
                  fontSize: 12,
                  cursor: "pointer",
                  fontWeight: filter === f ? 600 : 400,
                }}
              >
                {f === "all" ? `All (${summary.total})` : `Failed (${summary.failed})`}
              </button>
            ))}
          </div>
        </div>
        {visible.length === 0 ? (
          <p style={{ color: "var(--text-tertiary)", fontSize: 13 }}>
            {filter === "failed" ? "No failed checks." : "No checks recorded yet. Run the data_quality asset in Dagster."}
          </p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                <th style={{ textAlign: "left", padding: "0 8px 12px 0", fontWeight: 600, color: "var(--text-tertiary)" }}>Table</th>
                <th style={{ textAlign: "left", padding: "0 8px 12px 8px", fontWeight: 600, color: "var(--text-tertiary)" }}>Column</th>
                <th style={{ textAlign: "left", padding: "0 8px 12px 8px", fontWeight: 600, color: "var(--text-tertiary)" }}>Check</th>
                <th style={{ textAlign: "right", padding: "0 8px 12px 8px", fontWeight: 600, color: "var(--text-tertiary)" }}>Rows</th>
                <th style={{ textAlign: "right", padding: "0 8px 12px 8px", fontWeight: 600, color: "var(--text-tertiary)" }}>Failed</th>
                <th style={{ textAlign: "center", padding: "0 8px 12px 8px", fontWeight: 600, color: "var(--text-tertiary)" }}>Result</th>
                <th style={{ textAlign: "left", padding: "0 8px 12px 8px", fontWeight: 600, color: "var(--text-tertiary)" }}>Checked</th>
                <th style={{ textAlign: "left", padding: "0 0 12px 8px", fontWeight: 600, color: "var(--text-tertiary)" }}>Detail</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((c: DqCheck) => (
                <tr key={c.id} style={{ borderBottom: "1px solid var(--border-subtle, rgba(0,0,0,0.04))" }}>
                  <td style={{ padding: "10px 0", fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>{c.table_name}</td>
                  <td style={{ padding: "10px 8px", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{c.column_name}</td>
                  <td style={{ padding: "10px 8px", color: "var(--text-secondary)" }}>{c.check_type}</td>
                  <td style={{ padding: "10px 8px", textAlign: "right", fontFamily: "var(--font-mono)" }}>{c.row_count?.toLocaleString() ?? "—"}</td>
                  <td style={{ padding: "10px 8px", textAlign: "right", fontFamily: "var(--font-mono)", color: (c.failed_count ?? 0) > 0 ? "var(--status-critical)" : "var(--text-tertiary)" }}>
                    {c.failed_count?.toLocaleString() ?? "—"}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center" }}>
                    <CheckStatus passed={c.passed} />
                  </td>
                  <td style={{ padding: "10px 8px", color: "var(--text-tertiary)" }}>{humanAgo(c.checked_at)}</td>
                  <td style={{ padding: "10px 0 10px 8px", color: "var(--text-tertiary)", maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {c.detail ?? ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* CSV Export */}
      <Card>
        <CardHeader>Export Tables</CardHeader>
        <p style={{ color: "var(--text-tertiary)", fontSize: 13, marginBottom: 16 }}>
          Download any table as CSV (up to 100k rows).
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {EXPORTABLE.map((table) => (
            <a
              key={table}
              href={api.exportUrl(table)}
              download={`${table}.csv`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 14px",
                borderRadius: "var(--radius-full)",
                border: "1px solid var(--border)",
                color: "var(--text-secondary)",
                fontSize: 12,
                fontFamily: "var(--font-mono)",
                textDecoration: "none",
                background: "transparent",
                transition: "border-color 0.15s",
              }}
            >
              {table}.csv
            </a>
          ))}
        </div>
      </Card>
    </div>
  );
}
