const SEVERITY: Record<string, { color: string; bg: string }> = {
  critical: { color: "var(--status-critical)", bg: "rgba(200,85,61,0.1)" },
  warning:  { color: "var(--status-warning)",  bg: "rgba(232,160,74,0.1)" },
  healthy:  { color: "var(--status-healthy)",  bg: "rgba(127,183,126,0.1)" },
  over:     { color: "var(--status-critical)", bg: "rgba(200,85,61,0.1)" },
  under:    { color: "var(--status-under)",    bg: "rgba(107,140,174,0.1)" },
  ok:       { color: "var(--status-healthy)",  bg: "rgba(127,183,126,0.1)" },
  within_band: { color: "var(--status-healthy)", bg: "rgba(127,183,126,0.1)" },
  prod:     { color: "var(--status-critical)", bg: "rgba(200,85,61,0.08)" },
  staging:  { color: "var(--status-warning)",  bg: "rgba(232,160,74,0.08)" },
  dev:      { color: "var(--status-healthy)",  bg: "rgba(127,183,126,0.08)" },
  unknown:  { color: "var(--text-tertiary)",   bg: "rgba(168,159,148,0.1)" },
  success:  { color: "var(--status-healthy)",  bg: "rgba(127,183,126,0.1)" },
  failure:  { color: "var(--status-critical)", bg: "rgba(200,85,61,0.1)" },
  started:  { color: "var(--status-warning)",  bg: "rgba(232,160,74,0.1)" },
};

export function SeverityBadge({ severity }: { severity: string }) {
  const { color, bg } = SEVERITY[severity] ?? SEVERITY.unknown;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        fontSize: "10px",
        fontWeight: 600,
        fontFamily: "Inter, sans-serif",
        letterSpacing: "0.05em",
        textTransform: "uppercase",
        color,
        background: bg,
        border: `1px solid ${color}`,
        borderRadius: "var(--radius-full)",
        padding: "2px 8px",
        whiteSpace: "nowrap",
        opacity: 0.9,
      }}
    >
      {severity}
    </span>
  );
}

export function ProviderBadge({ provider }: { provider: "aws" | "gcp" | "azure" | string }) {
  const colorMap: Record<string, string> = {
    aws: "var(--provider-aws)",
    gcp: "var(--provider-gcp)",
    azure: "var(--provider-azure)",
  };
  const color = colorMap[provider] ?? "var(--text-tertiary)";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
        fontSize: "11px",
        fontWeight: 500,
        color,
        background: `color-mix(in srgb, ${color} 12%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 30%, transparent)`,
        borderRadius: "var(--radius-full)",
        padding: "2px 8px",
      }}
    >
      {provider.toUpperCase()}
    </span>
  );
}
