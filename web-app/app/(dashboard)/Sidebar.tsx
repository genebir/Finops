"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/overview",         label: "Overview" },
  { href: "/cost-explorer",    label: "Cost Explorer" },
  { href: "/anomalies",        label: "Anomalies" },
  { href: "/forecast",         label: "Forecast" },
  { href: "/budget",           label: "Budget" },
  { href: "/recommendations",  label: "Recommendations" },
  { href: "/ops",              label: "Ops" },
  { href: "/data-quality",     label: "Data Quality" },
  { href: "/burn-rate",        label: "Burn Rate" },
  { href: "/alerts",           label: "Alerts" },
  { href: "/cloud-compare",    label: "Cloud Compare" },
  { href: "/savings",          label: "Savings" },
  { href: "/risk",             label: "Risk" },
  { href: "/leaderboard",      label: "Leaderboard" },
  { href: "/services",         label: "Services" },
  { href: "/budget-forecast",  label: "Budget Forecast" },
  { href: "/cost-heatmap",     label: "Cost Heatmap" },
  { href: "/cloud-config",     label: "Cloud Config" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "220px",
        height: "100vh",
        backgroundColor: "var(--bg-dark)",
        borderRight: "1px solid #2E2A26",
        display: "flex",
        flexDirection: "column",
        padding: "24px 0",
      }}
    >
      <div style={{ padding: "0 20px 24px", borderBottom: "1px solid #2E2A26" }}>
        <Link
          href="/overview"
          style={{
            fontSize: "15px",
            fontWeight: 600,
            color: "var(--bg-warm)",
            letterSpacing: "-0.01em",
            textDecoration: "none",
          }}
        >
          FinOps
        </Link>
      </div>

      <nav style={{ padding: "16px 12px", display: "flex", flexDirection: "column", gap: "2px" }}>
        {NAV.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              style={{
                display: "block",
                padding: "8px 12px",
                borderRadius: "10px",
                fontSize: "13px",
                fontWeight: active ? 600 : 500,
                color: active ? "var(--bg-warm)" : "#6B6560",
                backgroundColor: active ? "rgba(250,247,242,0.1)" : "transparent",
                textDecoration: "none",
                transition: "all 0.15s ease",
              }}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
