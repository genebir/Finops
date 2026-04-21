export function PageHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <div style={{ marginBottom: "40px" }}>
      <h1
        style={{
          fontSize: "26px",
          fontWeight: 600,
          color: "var(--text-primary)",
          letterSpacing: "-0.02em",
          marginBottom: "6px",
        }}
      >
        {title}
      </h1>
      {sub && <p style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>{sub}</p>}
    </div>
  );
}

export function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid var(--border)",
        borderRadius: "20px",
        padding: "28px",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

export function CardLabel({ children }: { children: React.ReactNode }) {
  return (
    <p
      style={{
        fontSize: "13px",
        fontWeight: 600,
        color: "var(--text-primary)",
        marginBottom: "20px",
      }}
    >
      {children}
    </p>
  );
}

export function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p
      style={{
        fontSize: "11px",
        fontWeight: 600,
        color: "var(--text-tertiary)",
        letterSpacing: "0.07em",
        textTransform: "uppercase" as const,
        marginBottom: "10px",
      }}
    >
      {children}
    </p>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div
      style={{
        padding: "48px 0",
        textAlign: "center",
        color: "var(--text-tertiary)",
        fontSize: "13px",
      }}
    >
      {message}
    </div>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const map: Record<string, { color: string; bg: string }> = {
    critical: { color: "#C8553D", bg: "#C8553D18" },
    warning:  { color: "#E8A04A", bg: "#E8A04A18" },
    over:     { color: "#C8553D", bg: "#C8553D18" },
    ok:       { color: "#7FB77E", bg: "#7FB77E18" },
    info:     { color: "#6B8CAE", bg: "#6B8CAE18" },
    unknown:  { color: "#A89F94", bg: "#A89F9418" },
  };
  const { color, bg } = map[severity] ?? map.unknown;
  return (
    <span
      style={{
        fontSize: "10px",
        fontWeight: 600,
        color,
        background: bg,
        border: `1px solid ${color}30`,
        borderRadius: "9999px",
        padding: "2px 8px",
        letterSpacing: "0.04em",
        textTransform: "uppercase" as const,
        whiteSpace: "nowrap" as const,
      }}
    >
      {severity}
    </span>
  );
}

export function Mono({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <code
      style={{
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: "12px",
        color: "var(--text-primary)",
        fontVariantNumeric: "tabular-nums",
        ...style,
      }}
    >
      {children}
    </code>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "60vh",
        flexDirection: "column",
        gap: "12px",
      }}
    >
      <p style={{ fontSize: "14px", color: "var(--status-critical)" }}>Failed to load data</p>
      <p style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
        {message} — Make sure the API server is running (port 8000)
      </p>
    </div>
  );
}
