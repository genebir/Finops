interface PageHeaderProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export default function PageHeader({ title, description, action }: PageHeaderProps) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-end",
        marginBottom: "32px",
      }}
    >
      <div>
        <h1
          className="font-display"
          style={{
            fontSize: "clamp(32px, 3vw, 48px)",
            color: "var(--text-primary)",
            lineHeight: 1.1,
            letterSpacing: "-0.02em",
            marginBottom: description ? "8px" : 0,
          }}
        >
          {title}
        </h1>
        {description && (
          <p
            style={{
              fontSize: "15px",
              color: "var(--text-secondary)",
              fontFamily: "Inter, sans-serif",
            }}
          >
            {description}
          </p>
        )}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}
