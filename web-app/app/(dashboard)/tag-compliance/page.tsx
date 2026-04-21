import { API_BASE } from "@/lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState, EmptyState } from "@/components/primitives/States";

interface TeamRow {
  team: string;
  provider: string;
  total_resources: number;
  tagged_resources: number;
  violation_count: number;
  tag_completeness: number;
  compliance_score: number;
  rank: number;
}

interface Summary {
  avg_score: number;
  perfect_count: number;
  below_threshold_count: number;
  total_teams: number;
}

interface TagComplianceData {
  billing_month: string;
  summary: Summary;
  teams: TeamRow[];
}

async function fetchTagCompliance(): Promise<TagComplianceData> {
  const res = await fetch(`${API_BASE}/api/tag-compliance`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error("Failed to fetch tag-compliance");
  return res.json();
}

function ScoreBar({ score }: { score: number }) {
  const color = score >= 90 ? "var(--status-healthy)" : score >= 70 ? "var(--status-warning)" : "var(--status-critical)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <div style={{ flex: 1, height: "6px", borderRadius: "3px", backgroundColor: "var(--border)", overflow: "hidden" }}>
        <div style={{ width: `${Math.min(score, 100)}%`, height: "100%", backgroundColor: color, borderRadius: "3px", transition: "width 0.3s ease" }} />
      </div>
      <span className="font-mono" style={{ fontSize: "12px", fontWeight: 600, color, width: "36px", textAlign: "right" }}>
        {score.toFixed(0)}
      </span>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const [color, label] =
    score >= 90
      ? ["var(--status-healthy)", "High"]
      : score >= 70
      ? ["var(--status-warning)", "Medium"]
      : ["var(--status-critical)", "Low"];
  return (
    <span style={{
      display: "inline-block", padding: "2px 8px", borderRadius: "4px",
      fontSize: "11px", fontWeight: 600,
      background: `color-mix(in srgb, ${color} 15%, transparent)`,
      color,
    }}>
      {label}
    </span>
  );
}

const PROVIDER_COLORS: Record<string, string> = {
  aws:   "var(--provider-aws)",
  gcp:   "var(--provider-gcp)",
  azure: "var(--provider-azure)",
};

function ProviderTag({ provider }: { provider: string }) {
  const color = PROVIDER_COLORS[provider.toLowerCase()] ?? "var(--text-secondary)";
  return (
    <span style={{
      display: "inline-block", padding: "2px 8px", borderRadius: "4px",
      fontSize: "11px", fontWeight: 600,
      background: `color-mix(in srgb, ${color} 15%, transparent)`,
      color,
    }}>
      {provider.toUpperCase()}
    </span>
  );
}

const tableHeaders = ["#", "Team", "Provider", "Resources", "Tagged", "Violations", "Score", "Grade"];

export default async function TagCompliancePage() {
  let data: TagComplianceData;
  try {
    data = await fetchTagCompliance();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { summary, teams } = data;
  const avgScoreColor = summary.avg_score >= 90
    ? "var(--status-healthy)"
    : summary.avg_score >= 70
    ? "var(--status-warning)"
    : "var(--status-critical)";

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title="Tag Compliance"
        description={`${data.billing_month} — team · provider tag completeness scores`}
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "16px", marginBottom: "32px" }}>
        <MetricCard
          label="Avg Compliance Score"
          value={`${summary.avg_score}`}
          sub="/ 100"
          valueColor={avgScoreColor}
        />
        <MetricCard
          label="Perfect Teams"
          value={String(summary.perfect_count)}
          sub="≥ 99%"
          valueColor="var(--status-healthy)"
        />
        <MetricCard
          label="Below Threshold"
          value={String(summary.below_threshold_count)}
          sub="< 70%"
          valueColor="var(--status-critical)"
        />
        <MetricCard
          label="Total Teams"
          value={String(summary.total_teams)}
          sub="tracked"
        />
      </div>

      <Card>
        <CardHeader>Team Compliance Scores</CardHeader>
        {teams.length === 0 ? (
          <EmptyState title="No compliance data" description="Run the tag_compliance_score Dagster asset first." />
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {tableHeaders.map((h, idx, arr) => (
                  <th key={h} style={{
                    textAlign: idx <= 1 ? "left" : "center",
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
              {teams.map((row, i, arr) => (
                <tr key={`${row.team}-${row.provider}`} style={{ borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <td style={{ padding: "10px 0", fontSize: "13px", color: "var(--text-tertiary)", textAlign: "center" }}>
                    {row.rank}
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
                    {row.team}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center" }}>
                    <ProviderTag provider={row.provider} />
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center", fontSize: "13px", color: "var(--text-secondary)" }}>
                    {row.total_resources.toLocaleString()}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center", fontSize: "13px", color: "var(--text-secondary)" }}>
                    {row.tagged_resources.toLocaleString()}
                    <span style={{ fontSize: "11px", color: "var(--text-tertiary)", marginLeft: "4px" }}>
                      ({row.tag_completeness.toFixed(0)}%)
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "center", fontSize: "13px", color: row.violation_count > 0 ? "var(--status-critical)" : "var(--text-secondary)" }}>
                    {row.violation_count}
                  </td>
                  <td style={{ padding: "10px 8px", minWidth: "140px" }}>
                    <ScoreBar score={row.compliance_score} />
                  </td>
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "center" }}>
                    <ScoreBadge score={row.compliance_score} />
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
