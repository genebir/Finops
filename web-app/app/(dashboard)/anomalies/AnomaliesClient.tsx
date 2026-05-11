"use client";

import { useState } from "react";
import { Card, CardHeader } from "@/components/primitives/Card";
import { EmptyState } from "@/components/primitives/States";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { AnomalyItem, AnomalyRootCause } from "@/lib/types";

interface Props {
  initialItems: AnomalyItem[];
}

interface RowKey {
  resource_id: string;
  charge_date: string;
}

function rowKey(item: RowKey): string {
  return `${item.resource_id}::${item.charge_date}`;
}

const CAUSE_COLOR: Record<string, string> = {
  cost_spike: "var(--status-critical)",
  peer_spike: "var(--status-warning)",
  new_resource: "var(--accent)",
  unknown: "var(--text-tertiary)",
};

function formatMoney(v: number): string {
  return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatPct(v: number | null): string {
  if (v === null) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(1)}%`;
}

export default function AnomaliesClient({ initialItems }: Props) {
  const t = useT();
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [cache, setCache] = useState<Record<string, AnomalyRootCause>>({});
  const [loadingKey, setLoadingKey] = useState<string | null>(null);
  const [errorKey, setErrorKey] = useState<{ key: string; message: string } | null>(null);

  async function toggleRow(item: AnomalyItem) {
    const key = rowKey(item);
    if (openKey === key) {
      setOpenKey(null);
      return;
    }
    setOpenKey(key);
    setErrorKey(null);
    if (cache[key]) return;
    setLoadingKey(key);
    try {
      const data = await api.anomalyRootCause(item.resource_id, item.charge_date);
      setCache((prev) => ({ ...prev, [key]: data }));
    } catch (e) {
      setErrorKey({ key, message: String(e) });
    } finally {
      setLoadingKey(null);
    }
  }

  const headers = [
    { key: "th.resource", align: "left" },
    { key: "th.team", align: "left" },
    { key: "th.env", align: "center" },
    { key: "th.date", align: "center" },
    { key: "th.cost", align: "right" },
    { key: "th.z_score", align: "right" },
    { key: "th.severity", align: "center" },
    { key: "th.detector", align: "center" },
  ] as const;

  return (
    <Card>
      <CardHeader>{t("section.anomaly_events")}</CardHeader>

      {initialItems.length === 0 ? (
        <EmptyState
          title={t("empty.no_anomaly")}
          description={t("empty.run_anomaly")}
        />
      ) : (
        <>
          <p
            style={{
              fontSize: "11px",
              color: "var(--text-tertiary)",
              fontFamily: "Inter, sans-serif",
              marginTop: "-4px",
              marginBottom: "16px",
            }}
          >
            {t("label.root_cause_hint")}
          </p>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {headers.map((col, idx, arr) => (
                  <th
                    key={col.key}
                    style={{
                      textAlign: col.align,
                      fontSize: "10px",
                      fontWeight: 600,
                      fontFamily: "Inter, sans-serif",
                      color: "var(--text-tertiary)",
                      letterSpacing: "0.07em",
                      textTransform: "uppercase",
                      padding: idx === 0
                        ? "0 8px 12px 0"
                        : idx === arr.length - 1
                        ? "0 0 12px 8px"
                        : "0 8px 12px 8px",
                      borderBottom: "1px solid var(--border)",
                    }}
                  >
                    {t(col.key)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {initialItems.map((item, i) => {
                const key = rowKey(item);
                const isOpen = openKey === key;
                const rootCause = cache[key];
                const isLoading = loadingKey === key;
                const isError = errorKey?.key === key;
                return (
                  <ExpandableRow
                    key={key}
                    item={item}
                    isLast={i === initialItems.length - 1}
                    isOpen={isOpen}
                    onToggle={() => toggleRow(item)}
                    rootCause={rootCause}
                    isLoading={isLoading}
                    errorMessage={isError ? errorKey?.message ?? null : null}
                    t={t}
                  />
                );
              })}
            </tbody>
          </table>
        </>
      )}
    </Card>
  );
}

function ExpandableRow({
  item,
  isLast,
  isOpen,
  onToggle,
  rootCause,
  isLoading,
  errorMessage,
  t,
}: {
  item: AnomalyItem;
  isLast: boolean;
  isOpen: boolean;
  onToggle: () => void;
  rootCause: AnomalyRootCause | undefined;
  isLoading: boolean;
  errorMessage: string | null;
  t: ReturnType<typeof useT>;
}) {
  return (
    <>
      <tr
        onClick={onToggle}
        style={{
          borderBottom:
            isOpen
              ? "none"
              : isLast
                ? "none"
                : "1px solid var(--border)",
          cursor: "pointer",
          background: isOpen ? "color-mix(in srgb, var(--border) 18%, transparent)" : undefined,
        }}
      >
        <td style={{ padding: "10px 0" }}>
          <code className="font-mono" style={{ fontSize: "11px", color: "var(--text-primary)" }}>
            {item.resource_id}
          </code>
        </td>
        <td style={{ padding: "10px 8px", fontSize: "12px", color: "var(--text-secondary)" }}>
          {item.team}
        </td>
        <td style={{ padding: "10px 8px", textAlign: "center" }}>
          <SeverityBadge severity={item.env} />
        </td>
        <td style={{ padding: "10px 8px", textAlign: "center", fontSize: "12px", color: "var(--text-secondary)" }}>
          {item.charge_date}
        </td>
        <td style={{ padding: "10px 8px", textAlign: "right" }}>
          <span className="font-mono" style={{ fontSize: "12px" }}>
            <span className="currency-symbol">$</span>
            {item.effective_cost.toFixed(2)}
          </span>
        </td>
        <td style={{ padding: "10px 8px", textAlign: "right" }}>
          <span className="font-mono" style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
            {item.z_score.toFixed(2)}
          </span>
        </td>
        <td style={{ padding: "10px 8px", textAlign: "center" }}>
          <SeverityBadge severity={item.severity} />
        </td>
        <td style={{ padding: "10px 0 10px 8px", textAlign: "center", fontSize: "11px", color: "var(--text-tertiary)" }}>
          {item.detector_name}
        </td>
      </tr>
      {isOpen && (
        <tr style={{ borderBottom: isLast ? "none" : "1px solid var(--border)" }}>
          <td colSpan={8} style={{ padding: "0 0 16px 0" }}>
            <RootCausePanel
              data={rootCause}
              isLoading={isLoading}
              errorMessage={errorMessage}
              t={t}
            />
          </td>
        </tr>
      )}
    </>
  );
}

function RootCausePanel({
  data,
  isLoading,
  errorMessage,
  t,
}: {
  data: AnomalyRootCause | undefined;
  isLoading: boolean;
  errorMessage: string | null;
  t: ReturnType<typeof useT>;
}) {
  if (isLoading) {
    return (
      <div
        style={{
          padding: "16px",
          fontSize: "12px",
          color: "var(--text-tertiary)",
          fontFamily: "Inter, sans-serif",
        }}
      >
        Loading…
      </div>
    );
  }
  if (errorMessage) {
    return (
      <div
        style={{
          padding: "16px",
          fontSize: "12px",
          color: "var(--status-critical)",
        }}
      >
        {errorMessage}
      </div>
    );
  }
  if (!data) return null;

  const causeColor = CAUSE_COLOR[data.root_cause.cause] ?? "var(--text-tertiary)";
  const causeLabel =
    data.root_cause.cause === "cost_spike"   ? t("cause.cost_spike")
    : data.root_cause.cause === "peer_spike"  ? t("cause.peer_spike")
    : data.root_cause.cause === "new_resource" ? t("cause.new_resource")
    : t("cause.unknown");
  const confidencePct = Math.round(data.root_cause.confidence * 100);
  const spikeRatio = data.history.spike_ratio;

  return (
    <div
      style={{
        margin: "0 4px",
        padding: "16px 18px",
        borderRadius: "var(--radius-card)",
        background: "color-mix(in srgb, var(--border) 14%, transparent)",
        border: "1px solid var(--border)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          marginBottom: "14px",
          gap: "16px",
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: "12px" }}>
          <span
            style={{
              fontSize: "10px",
              fontFamily: "Inter, sans-serif",
              fontWeight: 600,
              letterSpacing: "0.07em",
              textTransform: "uppercase",
              color: "var(--text-tertiary)",
            }}
          >
            {t("section.root_cause")}
          </span>
          <span
            style={{
              fontSize: "13px",
              fontWeight: 600,
              color: causeColor,
              padding: "2px 10px",
              borderRadius: "var(--radius-full)",
              background: `color-mix(in srgb, ${causeColor} 14%, transparent)`,
              border: `1px solid color-mix(in srgb, ${causeColor} 35%, transparent)`,
            }}
          >
            {causeLabel}
          </span>
          <span
            className="font-mono"
            style={{ fontSize: "11px", color: "var(--text-tertiary)" }}
          >
            {t("label.confidence")}: {confidencePct}%
          </span>
        </div>
      </div>

      <p
        style={{
          fontSize: "13px",
          color: "var(--text-primary)",
          margin: "0 0 16px 0",
          lineHeight: 1.5,
        }}
      >
        {data.root_cause.reason}
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "12px",
        }}
      >
        <FactBlock
          title={t("label.target_cost")}
          rows={[
            { label: t("label.target_cost"), value: `$${formatMoney(data.target_cost)}` },
            { label: t("label.prior_7d_avg"), value: `$${formatMoney(data.history.avg_prior_7d)}` },
            {
              label: t("label.spike_ratio"),
              value: spikeRatio === null ? "—" : `${spikeRatio.toFixed(2)}×`,
              emphasis: spikeRatio !== null && spikeRatio >= 2,
            },
          ]}
        />
        <FactBlock
          title="Peers"
          rows={[
            { label: t("label.peer_count"), value: String(data.peers.peer_count) },
            { label: t("label.peer_avg"), value: `$${formatMoney(data.peers.peer_avg_cost)}` },
            {
              label: "Peers spiked",
              value: data.peers.peers_also_spiked ? "Yes" : "No",
              emphasis: data.peers.peers_also_spiked,
            },
          ]}
        />
        <FactBlock
          title="Team"
          rows={[
            { label: t("label.team_today"), value: `$${formatMoney(data.team_context.team_total_today)}` },
            { label: t("label.prior_7d_avg"), value: `$${formatMoney(data.team_context.team_avg_prior_7d)}` },
            {
              label: t("label.team_change"),
              value: formatPct(data.team_context.team_change_pct),
            },
          ]}
        />
      </div>
    </div>
  );
}

function FactBlock({
  title,
  rows,
}: {
  title: string;
  rows: { label: string; value: string; emphasis?: boolean }[];
}) {
  return (
    <div
      style={{
        padding: "12px 14px",
        borderRadius: "var(--radius-button)",
        background: "var(--bg-warm)",
        border: "1px solid var(--border)",
      }}
    >
      <p
        style={{
          fontSize: "10px",
          fontFamily: "Inter, sans-serif",
          fontWeight: 600,
          letterSpacing: "0.07em",
          textTransform: "uppercase",
          color: "var(--text-tertiary)",
          margin: "0 0 8px 0",
        }}
      >
        {title}
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        {rows.map((r) => (
          <div
            key={r.label}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              gap: "10px",
            }}
          >
            <span style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>{r.label}</span>
            <span
              className="font-mono"
              style={{
                fontSize: "12px",
                fontWeight: r.emphasis ? 600 : 400,
                color: r.emphasis ? "var(--status-critical)" : "var(--text-primary)",
              }}
            >
              {r.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
