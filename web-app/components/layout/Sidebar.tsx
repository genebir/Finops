"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import {
  ChartLine,
  CurrencyDollar,
  Warning,
  TrendUp,
  Wallet,
  Receipt,
  Lightbulb,
  GearSix,
  Bell,
  Fire,
  PiggyBank,
  ShieldWarning,
  Trophy,
  Gauge,
  Database,
  ArrowsLeftRight,
  GridFour,
  CalendarCheck,
  Tag,
  ChartPieSlice,
  Pulse,
  CaretDown,
  CaretRight,
  Package,
  ClipboardText,
  Prohibit,
  Rows,
} from "@phosphor-icons/react";

type NavItem = { href: string; label: string; Icon: React.ElementType };
type NavGroup = { id: string; label: string; Icon: React.ElementType; items: NavItem[] };

const GROUPS: NavGroup[] = [
  {
    id: "costs",
    label: "Costs",
    Icon: CurrencyDollar,
    items: [
      { href: "/cost-explorer",  label: "Cost Explorer",  Icon: CurrencyDollar },
      { href: "/cloud-compare",  label: "Cloud Compare",  Icon: ArrowsLeftRight },
      { href: "/services",       label: "Services",       Icon: GridFour },
      { href: "/leaderboard",    label: "Leaderboard",    Icon: Trophy },
      { href: "/env-breakdown",  label: "Env Breakdown",  Icon: ChartPieSlice },
      { href: "/cost-trend",    label: "Cost Trend",    Icon: TrendUp },
    ],
  },
  {
    id: "anomalies",
    label: "Anomalies",
    Icon: Warning,
    items: [
      { href: "/anomalies",        label: "Anomalies",        Icon: Warning },
      { href: "/anomaly-timeline", label: "Timeline",         Icon: Pulse },
      { href: "/risk",             label: "Risk",             Icon: ShieldWarning },
    ],
  },
  {
    id: "budget",
    label: "Budget",
    Icon: Wallet,
    items: [
      { href: "/budget",          label: "Budget",       Icon: Wallet },
      { href: "/budget-forecast", label: "Forecast",     Icon: CalendarCheck },
      { href: "/burn-rate",       label: "Burn Rate",    Icon: Fire },
      { href: "/savings",         label: "Savings",      Icon: PiggyBank },
      { href: "/chargeback",      label: "Chargeback",   Icon: Receipt },
      { href: "/showback",          label: "Showback",       Icon: ClipboardText },
      { href: "/cost-allocation",   label: "Allocation",     Icon: Rows },
      { href: "/recommendations", label: "Suggestions",  Icon: Lightbulb },
    ],
  },
  {
    id: "compliance",
    label: "Compliance",
    Icon: Tag,
    items: [
      { href: "/tag-compliance", label: "Tag Compliance", Icon: Tag },
      { href: "/tag-policy",     label: "Tag Policy",     Icon: Prohibit },
      { href: "/inventory",      label: "Inventory",      Icon: Package },
      { href: "/data-quality",   label: "Data Quality",   Icon: Database },
    ],
  },
  {
    id: "operations",
    label: "Operations",
    Icon: Gauge,
    items: [
      { href: "/forecast", label: "Forecast", Icon: TrendUp },
      { href: "/alerts",   label: "Alerts",   Icon: Bell },
      { href: "/ops",      label: "Ops",      Icon: Gauge },
    ],
  },
];

function SubItem({ href, label, Icon, active }: NavItem & { active: boolean }) {
  return (
    <Link
      href={href}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "6px 12px 6px 20px",
        borderRadius: "var(--radius-button)",
        fontSize: "13px",
        fontWeight: active ? 600 : 400,
        fontFamily: "Inter, sans-serif",
        color: active ? "var(--text-primary)" : "var(--text-secondary)",
        backgroundColor: active ? "rgba(26,23,20,0.05)" : "transparent",
        borderLeft: active ? "2px solid var(--text-primary)" : "2px solid transparent",
        textDecoration: "none",
        transition: "all 0.12s ease",
        marginLeft: "-2px",
      }}
    >
      <Icon size={15} weight={active ? "duotone" : "regular"} />
      {label}
    </Link>
  );
}

function GroupSection({
  group,
  isOpen,
  onToggle,
  pathname,
}: {
  group: NavGroup;
  isOpen: boolean;
  onToggle: () => void;
  pathname: string;
}) {
  const { Icon } = group;
  const isAnyChildActive = group.items.some(
    (item) => pathname === item.href || pathname.startsWith(item.href + "/")
  );

  return (
    <div>
      <button
        onClick={onToggle}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          width: "100%",
          padding: "7px 12px",
          borderRadius: "var(--radius-button)",
          border: "none",
          background: "transparent",
          cursor: "pointer",
          fontSize: "13px",
          fontWeight: 600,
          fontFamily: "Inter, sans-serif",
          color: isAnyChildActive ? "var(--text-primary)" : "var(--text-secondary)",
          textAlign: "left",
          transition: "color 0.12s ease",
        }}
      >
        <Icon size={16} weight={isAnyChildActive ? "duotone" : "regular"} />
        <span style={{ flex: 1 }}>{group.label}</span>
        {isOpen
          ? <CaretDown size={12} weight="bold" style={{ opacity: 0.5 }} />
          : <CaretRight size={12} weight="bold" style={{ opacity: 0.4 }} />
        }
      </button>

      {isOpen && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1px", marginTop: "1px" }}>
          {group.items.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return <SubItem key={item.href} {...item} active={active} />;
          })}
        </div>
      )}
    </div>
  );
}

function PinnedItem({ href, label, Icon, active }: NavItem & { active: boolean }) {
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
        transition: "all 0.12s ease",
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

  // Determine which groups contain the active page
  const activeGroupIds = GROUPS
    .filter((g) => g.items.some((item) => pathname === item.href || pathname.startsWith(item.href + "/")))
    .map((g) => g.id);

  const [openGroups, setOpenGroups] = useState<Set<string>>(() => new Set(activeGroupIds));

  // Auto-expand group containing the current page when pathname changes
  useEffect(() => {
    setOpenGroups((prev) => {
      const next = new Set(prev);
      activeGroupIds.forEach((id) => next.add(id));
      return next;
    });
  }, [pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleGroup = (id: string) => {
    setOpenGroups((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const isOverviewActive = pathname === "/overview" || pathname === "/";

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
      <div style={{ padding: "20px 20px 16px", borderBottom: "1px solid var(--border)" }}>
        <Link href="/overview" style={{ textDecoration: "none" }}>
          <span className="font-display" style={{ fontSize: "20px", color: "var(--text-primary)" }}>
            FinOps
          </span>
        </Link>
        <p style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "2px" }}>
          Cost Intelligence
        </p>
      </div>

      {/* Main nav */}
      <nav
        style={{
          flex: 1,
          padding: "10px 8px",
          display: "flex",
          flexDirection: "column",
          gap: "2px",
          overflowY: "auto",
        }}
      >
        {/* Pinned: Overview */}
        <PinnedItem href="/overview" label="Overview" Icon={ChartLine} active={isOverviewActive} />

        <div style={{ height: "4px" }} />

        {/* Collapsible groups */}
        {GROUPS.map((group) => (
          <GroupSection
            key={group.id}
            group={group}
            isOpen={openGroups.has(group.id)}
            onToggle={() => toggleGroup(group.id)}
            pathname={pathname}
          />
        ))}
      </nav>

      {/* Bottom: Settings */}
      <div style={{ padding: "8px 8px 16px", borderTop: "1px solid var(--border)" }}>
        <PinnedItem
          href="/settings"
          label="Settings"
          Icon={GearSix}
          active={pathname === "/settings" || pathname.startsWith("/settings/")}
        />
      </div>
    </aside>
  );
}
