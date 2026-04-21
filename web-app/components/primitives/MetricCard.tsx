import { Card, SectionLabel } from "./Card";

interface MetricCardProps {
  label: string;
  value: string;
  sub?: string;
  valueColor?: string;
  delta?: { value: number; context?: "cost" | "savings" };
}

export function MetricCard({ label, value, sub, valueColor, delta }: MetricCardProps) {
  const deltaColor = delta
    ? delta.context === "savings"
      ? delta.value > 0 ? "var(--status-healthy)" : "var(--status-critical)"
      : delta.value > 0 ? "var(--status-critical)" : "var(--status-healthy)"
    : undefined;

  const deltaArrow = delta ? (delta.value > 0 ? "▲" : "▼") : null;

  return (
    <Card>
      <SectionLabel>{label}</SectionLabel>
      <p
        className="font-mono"
        style={{
          fontSize: "32px",
          fontWeight: 500,
          color: valueColor ?? "var(--text-primary)",
          letterSpacing: "-0.02em",
          lineHeight: 1.1,
          marginBottom: delta || sub ? "6px" : 0,
        }}
      >
        {value}
      </p>
      {delta && (
        <p style={{ fontSize: "12px", color: deltaColor, fontWeight: 500 }}>
          {deltaArrow} {Math.abs(delta.value).toFixed(1)}%
        </p>
      )}
      {sub && !delta && (
        <p style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>{sub}</p>
      )}
    </Card>
  );
}
