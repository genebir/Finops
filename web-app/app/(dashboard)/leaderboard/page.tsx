import Link from "next/link";
import { API_BASE } from "../../../lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState, EmptyState } from "@/components/primitives/States";

export const metadata = { title: "Leaderboard — FinOps" };

interface LeaderboardItem {
  rank: number; team: string;
  curr_cost: number; prev_cost: number;
  mom_change_pct: number | null;
  pct_of_total: number; resource_count: number;
}
interface LeaderboardData {
  billing_month: string; prev_month: string;
  items: LeaderboardItem[];
  summary: { total_curr: number; total_prev: number; team_count: number };
}

async function fetchLeaderboard(): Promise<LeaderboardData> {
  const res = await fetch(`${API_BASE}/api/leaderboard`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error("Failed to load leaderboard data");
  return res.json();
}

function MomBadge({ pct }: { pct: number | null }) {
  if (pct === null) return <span style={{ color: "var(--text-tertiary)", fontSize: "12px" }}>—</span>;
  const color = pct > 10
    ? "var(--status-critical)"
    : pct < -5
    ? "var(--status-healthy)"
    : "var(--status-warning)";
  return (
    <span className="font-mono" style={{ color, fontWeight: 600, fontSize: "12px" }}>
      {pct > 0 ? "+" : ""}{pct.toFixed(1)}%
    </span>
  );
}

function PctBar({ pct }: { pct: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <div style={{ height: "6px", background: "var(--border)", borderRadius: "3px", overflow: "hidden", width: "80px" }}>
        <div style={{ height: "100%", width: `${Math.min(pct, 100)}%`, background: "var(--text-secondary)", borderRadius: "3px" }} />
      </div>
      <span style={{ fontSize: "11px", color: "var(--text-tertiary)", minWidth: "32px" }}>{pct.toFixed(1)}%</span>
    </div>
  );
}

const MEDALS = ["1st", "2nd", "3rd"];

export default async function LeaderboardPage() {
  let data: LeaderboardData;
  try {
    data = await fetchLeaderboard();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { summary, items, billing_month, prev_month } = data;
  const overallMom = summary.total_prev > 0
    ? ((summary.total_curr - summary.total_prev) / summary.total_prev * 100)
    : null;

  const headers = ["#", "Team", "Curr Cost", "Prev Cost", "MoM", "Share", "Resources"];

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title="Team Leaderboard"
        description={`${billing_month} vs ${prev_month} — ranked by total spend`}
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: "16px", marginBottom: "32px" }}>
        <MetricCard
          label="Total Spend"
          value={`$${summary.total_curr.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
          delta={overallMom !== null ? { value: overallMom, context: "cost" } : undefined}
        />
        <MetricCard
          label="Teams"
          value={String(summary.team_count)}
        />
        <MetricCard
          label="Prev Month"
          value={`$${summary.total_prev.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
          valueColor="var(--text-secondary)"
        />
      </div>

      <Card>
        <CardHeader>Team Rankings</CardHeader>
        {items.length === 0 ? (
          <EmptyState title="No leaderboard data" description="Materialize gold_marts assets first." />
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {headers.map((h, idx, arr) => (
                  <th key={h} style={{
                    textAlign: idx >= 2 ? "right" : "left",
                    fontSize: "10px",
                    fontWeight: 600,
                    fontFamily: "Inter, sans-serif",
                    color: "var(--text-tertiary)",
                    letterSpacing: "0.07em",
                    textTransform: "uppercase",
                    padding: idx === 0 ? "0 8px 12px 0" : idx === arr.length - 1 ? "0 0 12px 8px" : "0 8px 12px 8px",
                    borderBottom: "1px solid var(--border)",
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item, i, arr) => (
                <tr key={item.rank} style={{ borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <td style={{ padding: "10px 0" }}>
                    <span style={{ fontSize: "11px", fontWeight: 700, color: item.rank <= 3 ? "var(--text-primary)" : "var(--text-tertiary)" }}>
                      {item.rank <= 3 ? MEDALS[item.rank - 1] : item.rank}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px" }}>
                    <Link
                      href={`/teams/${encodeURIComponent(item.team)}`}
                      style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: "13px", textDecoration: "none" }}
                    >
                      {item.team}
                    </Link>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-primary)" }}>
                      ${item.curr_cost.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                      ${item.prev_cost.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <MomBadge pct={item.mom_change_pct} />
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <PctBar pct={item.pct_of_total} />
                  </td>
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "right", color: "var(--text-secondary)", fontSize: "13px" }}>
                    {item.resource_count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
