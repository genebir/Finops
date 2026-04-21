"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ChartLine,
  CurrencyDollar,
  Warning,
  TrendUp,
  Wallet,
  Receipt,
  Lightbulb,
  GearSix,
} from "@phosphor-icons/react";

const NAV_MAIN = [
  { href: "/overview",        label: "Overview",        Icon: ChartLine },
  { href: "/cost-explorer",   label: "Costs",           Icon: CurrencyDollar },
  { href: "/anomalies",       label: "Anomalies",       Icon: Warning },
  { href: "/forecast",        label: "Forecast",        Icon: TrendUp },
  { href: "/budget",          label: "Budget",          Icon: Wallet },
  { href: "/chargeback",      label: "Chargeback",      Icon: Receipt },
  { href: "/recommendations", label: "Recommendations", Icon: Lightbulb },
];

const NAV_BOTTOM = [
  { href: "/settings", label: "Settings", Icon: GearSix },
];

function NavItem({
  href,
  label,
  Icon,
  active,
}: {
  href: string;
  label: string;
  Icon: React.ElementType;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: "8px 12px",
        borderRadius: "var(--radius-button)",
        fontSize: "14px",
        fontWeight: active ? 600 : 500,
        fontFamily: "Inter, sans-serif",
        color: active ? "var(--text-primary)" : "var(--text-secondary)",
        backgroundColor: active ? "rgba(26,23,20,0.05)" : "transparent",
        borderLeft: active ? "2px solid var(--text-primary)" : "2px solid transparent",
        textDecoration: "none",
        transition: "all 0.15s ease",
        marginLeft: "-2px",
      }}
    >
      <Icon size={18} weight={active ? "duotone" : "regular"} />
      {label}
    </Link>
  );
}

export default function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string) =>
    pathname === href || pathname.startsWith(href + "/");

  return (
    <aside
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "240px",
        height: "100vh",
        backgroundColor: "var(--bg-warm-subtle)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        zIndex: 40,
      }}
    >
      {/* Logo */}
      <div
        style={{
          padding: "20px 20px 16px",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <Link
          href="/overview"
          style={{ textDecoration: "none" }}
        >
          <span
            className="font-display"
            style={{
              fontSize: "20px",
              color: "var(--text-primary)",
            }}
          >
            FinOps
          </span>
        </Link>
        <p
          style={{
            fontSize: "11px",
            color: "var(--text-tertiary)",
            marginTop: "2px",
          }}
        >
          Cost Intelligence
        </p>
      </div>

      {/* Main nav */}
      <nav
        style={{
          flex: 1,
          padding: "12px 8px",
          display: "flex",
          flexDirection: "column",
          gap: "2px",
          overflowY: "auto",
        }}
      >
        {NAV_MAIN.map(({ href, label, Icon }) => (
          <NavItem
            key={href}
            href={href}
            label={label}
            Icon={Icon}
            active={isActive(href)}
          />
        ))}
      </nav>

      {/* Bottom nav */}
      <div
        style={{
          padding: "8px 8px 16px",
          borderTop: "1px solid var(--border)",
        }}
      >
        {NAV_BOTTOM.map(({ href, label, Icon }) => (
          <NavItem
            key={href}
            href={href}
            label={label}
            Icon={Icon}
            active={isActive(href)}
          />
        ))}
      </div>
    </aside>
  );
}
