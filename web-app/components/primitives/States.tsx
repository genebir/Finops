import { SmileySad, Warning } from "@phosphor-icons/react/dist/ssr";

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "64px 24px",
        gap: "12px",
        color: "var(--text-tertiary)",
      }}
    >
      <SmileySad size={32} weight="duotone" />
      <p style={{ fontSize: "14px", fontWeight: 500, color: "var(--text-secondary)" }}>{title}</p>
      {description && (
        <p style={{ fontSize: "12px", textAlign: "center", maxWidth: "360px" }}>{description}</p>
      )}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "60vh",
        gap: "12px",
      }}
    >
      <Warning size={32} weight="duotone" color="var(--status-critical)" />
      <p style={{ fontSize: "14px", fontWeight: 500, color: "var(--status-critical)" }}>
        Failed to load data
      </p>
      <p style={{ fontSize: "12px", color: "var(--text-tertiary)", textAlign: "center" }}>
        {message}
        <br />
        Make sure the API server is running (port 8000)
      </p>
    </div>
  );
}
