"use client";

import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState } from "@/components/primitives/States";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { api } from "@/lib/api";
import type { OpsHealthData, OpsRunsData } from "@/lib/types";
import { useEffect, useState } from "react";

const REFRESH_MS = 10_000;

function humanAgo(iso: string | null): string {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return new Date(iso).toLocaleString();
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.floor(hr / 24)}d ago`;
}

function fmtDuration(sec: number | null): string {
  if (sec === null || sec === undefined) return "—";
  if (sec < 1) return `${Math.round(sec * 1000)}ms`;
  if (sec < 60) return `${sec.toFixed(1)}s`;
  const min = sec / 60;
  if (min < 60) return `${min.toFixed(1)}m`;
  return `${(min / 60).toFixed(1)}h`;
}

export default function OpsClient() {
  const [runs, setRuns] = useState<OpsRunsData | null>(null);
  const [health, setHealth] = useState<OpsHealthData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    async function tick() {
      try {
        const [r, h] = await Promise.all([api.opsRuns(30), api.opsHealth()]);
        if (!alive) return;
        setRuns(r);
        setHealth(h);
        setError(null);
      } catch (e) {
        if (alive) setError(String(e));
      }
    }
    tick();
    const timer = setInterval(tick, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  if (error && !runs) return <ErrorState message={error} />;
  if (!runs || !health) return <div style={{ color: "var(--text-tertiary)" }}>Loading…</div>;

  return (
    <div>
      {/* KPIs */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "16px",
          marginBottom: "32px",
        }}
      >
        <MetricCard
          label="Successful Runs"
          value={String(runs.success_count)}
          sub={runs.latest_success_at ? `latest ${humanAgo(runs.latest_success_at)}` : "no successes yet"}
          valueColor="var(--status-healthy)"
        />
        <MetricCard
          label="Failed Runs"
          value={String(runs.failure_count)}
          sub={runs.latest_failure_at ? `latest ${humanAgo(runs.latest_failure_at)}` : "no failures"}
          valueColor={runs.failure_count > 0 ? "var(--status-critical)" : "var(--text-primary)"}
        />
        <MetricCard
          label="Database"
          value={health.db_reachable ? "UP" : "DOWN"}
          valueColor={health.db_reachable ? "var(--status-healthy)" : "var(--status-critical)"}
          sub={humanAgo(health.checked_at)}
        />
        <MetricCard
          label="Tables Tracked"
          value={String(health.tables.length)}
          sub="see table health below"
        />
      </div>

      {/* Recent runs */}
      <Card style={{ marginBottom: 24 }}>
        <CardHeader>Recent Pipeline Runs</CardHeader>
        {runs.runs.length === 0 ? (
          <p style={{ color: "var(--text-tertiary)", fontSize: 13 }}>
            No runs recorded yet. Trigger a materialize in Dagster to populate the log.
          </p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                <th style={{ textAlign: "left", padding: "0 8px 12px 0", fontWeight: 600, color: "var(--text-tertiary)" }}>Started</th>
                <th style={{ textAlign: "left", padding: "0 8px 12px 8px", fontWeight: 600, color: "var(--text-tertiary)" }}>Asset / Job</th>
                <th style={{ textAlign: "left", padding: "0 8px 12px 8px", fontWeight: 600, color: "var(--text-tertiary)" }}>Partition</th>
                <th style={{ textAlign: "center", padding: "0 8px 12px 8px", fontWeight: 600, color: "var(--text-tertiary)" }}>Status</th>
                <th style={{ textAlign: "right", padding: "0 8px 12px 8px", fontWeight: 600, color: "var(--text-tertiary)" }}>Duration</th>
                <th style={{ textAlign: "left", padding: "0 0 12px 8px", fontWeight: 600, color: "var(--text-tertiary)" }}>Error</th>
              </tr>
            </thead>
            <tbody>
              {runs.runs.map((r) => (
                <tr key={r.id} style={{ borderBottom: "1px solid var(--border-subtle, rgba(0,0,0,0.04))" }}>
                  <td style={{ padding: "10px 0", color: "var(--text-secondary)" }}>{humanAgo(r.started_at)}</td>
                  <td style={{ padding: "10px 8px", fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>{r.asset_key}</td>
                  <td style={{ padding: "10px 8px", color: "var(--text-tertiary)" }}>{r.partition_key ?? "—"}</td>
                  <td style={{ padding: "10px 8px", textAlign: "center" }}><SeverityBadge severity={r.status} /></td>
                  <td style={{ padding: "10px 8px", textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{fmtDuration(r.duration_sec)}</td>
                  <td style={{
                    padding: "10px 0 10px 8px",
                    color: "var(--status-critical)",
                    maxWidth: "360px",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}>
                    {r.error_message ?? ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Table health */}
      <Card>
        <CardHeader>Table Health</CardHeader>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <th style={{ textAlign: "left", padding: "0 8px 12px 0", fontWeight: 600, color: "var(--text-tertiary)" }}>Table</th>
              <th style={{ textAlign: "right", padding: "0 8px 12px 8px", fontWeight: 600, color: "var(--text-tertiary)" }}>Rows</th>
              <th style={{ textAlign: "left", padding: "0 0 12px 8px", fontWeight: 600, color: "var(--text-tertiary)" }}>Latest Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {health.tables.map((t) => (
              <tr key={t.table} style={{ borderBottom: "1px solid var(--border-subtle, rgba(0,0,0,0.04))" }}>
                <td style={{ padding: "10px 0", fontFamily: "var(--font-mono)" }}>{t.table}</td>
                <td style={{ padding: "10px 8px", textAlign: "right", fontFamily: "var(--font-mono)", color: t.row_count === 0 ? "var(--text-tertiary)" : "var(--text-primary)" }}>{t.row_count.toLocaleString()}</td>
                <td style={{ padding: "10px 0 10px 8px", color: "var(--text-tertiary)" }}>{t.latest_ts ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
