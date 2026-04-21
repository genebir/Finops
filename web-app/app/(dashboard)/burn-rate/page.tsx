import PageHeader from "@/components/layout/PageHeader";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

const STATUS_COLOR: Record<string, string> = {
  critical: "var(--status-critical)",
  warning: "var(--status-warning)",
  on_track: "var(--status-healthy)",
  no_budget: "var(--text-tertiary)",
};

function fmt(n: number | null | undefined, prefix = "$"): string {
  if (n == null) return "—";
  return `${prefix}${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function BurnBar({ pct }: { pct: number | null }) {
  if (pct == null) return <span style={{ color: "var(--text-tertiary)", fontSize: 12 }}>no budget</span>;
  const clamped = Math.min(pct, 150);
  const color = pct >= 100 ? "var(--status-critical)" : pct >= 80 ? "var(--status-warning)" : "var(--status-healthy)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 6, background: "var(--border)", borderRadius: 3 }}>
        <div style={{ height: "100%", width: `${clamped}%`, maxWidth: "100%", background: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color, minWidth: 42, textAlign: "right" }}>
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

export default async function BurnRatePage() {
  let data: Awaited<ReturnType<typeof api.burnRate>> | null = null;
  try {
    data = await api.burnRate();
  } catch {
    data = null;
  }

  const items = data?.items ?? [];
  const summary = data?.summary ?? {};
  const month = data?.billing_month ?? "—";

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title="Burn Rate"
        description={`MTD spend velocity and projected end-of-month cost — ${month}`}
      />

      {/* Summary KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 32 }}>
        {[
          { label: "MTD Total", value: fmt(summary.total_mtd), sub: "month-to-date" },
          { label: "Projected EOM", value: fmt(summary.total_projected_eom), sub: "end-of-month estimate" },
          { label: "Critical", value: String(summary.critical_count ?? 0), sub: "over budget trajectory", color: (summary.critical_count ?? 0) > 0 ? "var(--status-critical)" : undefined },
          { label: "Warning", value: String(summary.warning_count ?? 0), sub: "approaching budget", color: (summary.warning_count ?? 0) > 0 ? "var(--status-warning)" : undefined },
        ].map((kpi) => (
          <div key={kpi.label} style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--radius-card)", padding: "20px 24px" }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>{kpi.label}</div>
            <div style={{ fontSize: 28, fontWeight: 700, fontFamily: "var(--font-mono)", color: kpi.color ?? "var(--text-primary)", letterSpacing: "-0.02em" }}>{kpi.value}</div>
            <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>{kpi.sub}</div>
          </div>
        ))}
      </div>

      {/* Burn rate table */}
      <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--radius-card)", padding: "24px" }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 16 }}>Team / Environment Burn Rate</div>
        {items.length === 0 ? (
          <p style={{ color: "var(--text-tertiary)", fontSize: 13 }}>
            No data yet. Materialize the <code>burn_rate</code> asset in Dagster.
          </p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Team", "Env", "MTD Cost", "Daily Avg", "Projected EOM", "Budget", "Projected %", ""].map((h, i) => (
                  <th key={h + i} style={{
                    textAlign: i >= 2 && i <= 5 ? "right" : i === 6 ? "left" : "left",
                    padding: i === 0 ? "0 8px 12px 0" : i === 7 ? "0 0 12px 8px" : "0 8px 12px 8px",
                    fontWeight: 600, color: "var(--text-tertiary)",
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((r, idx) => (
                <tr key={idx} style={{ borderBottom: "1px solid var(--border-subtle, rgba(0,0,0,0.04))" }}>
                  <td style={{ padding: "10px 0", fontFamily: "var(--font-mono)" }}>{r.team}</td>
                  <td style={{ padding: "10px 8px", color: "var(--text-secondary)" }}>{r.env}</td>
                  <td style={{ padding: "10px 8px", textAlign: "right", fontFamily: "var(--font-mono)" }}>{fmt(r.mtd_cost)}</td>
                  <td style={{ padding: "10px 8px", textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>{fmt(r.daily_avg)}/d</td>
                  <td style={{ padding: "10px 8px", textAlign: "right", fontFamily: "var(--font-mono)", fontWeight: 600, color: STATUS_COLOR[r.status] ?? "var(--text-primary)" }}>{fmt(r.projected_eom)}</td>
                  <td style={{ padding: "10px 8px", textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--text-tertiary)" }}>{fmt(r.budget_amount)}</td>
                  <td style={{ padding: "10px 8px", minWidth: 140 }}><BurnBar pct={r.projected_utilization} /></td>
                  <td style={{ padding: "10px 0 10px 8px" }}>
                    <span style={{
                      fontSize: 10, fontWeight: 600, textTransform: "uppercase",
                      color: STATUS_COLOR[r.status] ?? "var(--text-tertiary)",
                      background: r.status === "critical" ? "rgba(200,85,61,0.1)" : r.status === "warning" ? "rgba(232,160,74,0.1)" : r.status === "on_track" ? "rgba(127,183,126,0.1)" : "rgba(168,159,148,0.1)",
                      border: `1px solid ${STATUS_COLOR[r.status] ?? "var(--text-tertiary)"}`,
                      borderRadius: "var(--radius-full)",
                      padding: "2px 8px",
                    }}>
                      {r.status.replace("_", " ")}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
