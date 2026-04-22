"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { useT } from "@/lib/i18n";
import type { TranslationKey } from "@/lib/i18n";
import LanguageToggle from "./LanguageToggle";
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
  Play,
} from "@phosphor-icons/react";

type NavItem = { href: string; labelKey: TranslationKey; Icon: React.ElementType };
type NavGroup = { id: string; labelKey: TranslationKey; Icon: React.ElementType; items: NavItem[] };

const GROUPS: NavGroup[] = [
  {
    id: "costs",
    labelKey: "nav.costs",
    Icon: CurrencyDollar,
    items: [
      { href: "/cost-explorer",  labelKey: "nav.cost_explorer",  Icon: CurrencyDollar },
      { href: "/cloud-compare",  labelKey: "nav.cloud_compare",  Icon: ArrowsLeftRight },
      { href: "/services",       labelKey: "nav.services",       Icon: GridFour },
      { href: "/leaderboard",    labelKey: "nav.leaderboard",    Icon: Trophy },
      { href: "/env-breakdown",  labelKey: "nav.env_breakdown",  Icon: ChartPieSlice },
      { href: "/cost-trend",     labelKey: "nav.cost_trend",     Icon: TrendUp },
    ],
  },
  {
    id: "anomalies",
    labelKey: "nav.anomalies",
    Icon: Warning,
    items: [
      { href: "/anomalies",        labelKey: "nav.anomalies",  Icon: Warning },
      { href: "/anomaly-timeline", labelKey: "nav.timeline",   Icon: Pulse },
      { href: "/risk",             labelKey: "nav.risk",       Icon: ShieldWarning },
    ],
  },
  {
    id: "budget",
    labelKey: "nav.budget",
    Icon: Wallet,
    items: [
      { href: "/budget",          labelKey: "nav.budget",       Icon: Wallet },
      { href: "/budget-forecast", labelKey: "nav.budget_forecast", Icon: CalendarCheck },
      { href: "/burn-rate",       labelKey: "nav.burn_rate",    Icon: Fire },
      { href: "/savings",         labelKey: "nav.savings",      Icon: PiggyBank },
      { href: "/chargeback",      labelKey: "nav.chargeback",   Icon: Receipt },
      { href: "/showback",        labelKey: "nav.showback",     Icon: ClipboardText },
      { href: "/cost-allocation", labelKey: "nav.allocation",   Icon: Rows },
      { href: "/recommendations", labelKey: "nav.suggestions",  Icon: Lightbulb },
    ],
  },
  {
    id: "compliance",
    labelKey: "nav.compliance",
    Icon: Tag,
    items: [
      { href: "/tag-compliance", labelKey: "nav.tag_compliance", Icon: Tag },
      { href: "/tag-policy",     labelKey: "nav.tag_policy",     Icon: Prohibit },
      { href: "/inventory",      labelKey: "nav.inventory",      Icon: Package },
      { href: "/data-quality",   labelKey: "nav.data_quality",   Icon: Database },
    ],
  },
  {
    id: "operations",
    labelKey: "nav.operations",
    Icon: Gauge,
    items: [
      { href: "/pipeline",  labelKey: "nav.pipeline",  Icon: Play },
      { href: "/forecast",  labelKey: "nav.forecast",  Icon: TrendUp },
      { href: "/alerts",    labelKey: "nav.alerts",    Icon: Bell },
      { href: "/ops",       labelKey: "nav.ops",       Icon: Gauge },
    ],
  },
];

function SubItem({ href, labelKey, Icon, active }: NavItem & { active: boolean }) {
  const t = useT();
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
      {t(labelKey)}
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
  const t = useT();
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
        <span style={{ flex: 1 }}>{t(group.labelKey)}</span>
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

function PinnedItem({ href, labelKey, Icon, active }: NavItem & { active: boolean }) {
  const t = useT();
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
      {t(labelKey)}
    </Link>
  );
}

export default function Sidebar() {
  const pathname = usePathname();

  const activeGroupIds = GROUPS
    .filter((g) => g.items.some((item) => pathname === item.href || pathname.startsWith(item.href + "/")))
    .map((g) => g.id);

  const [openGroups, setOpenGroups] = useState<Set<string>>(() => new Set(activeGroupIds));

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
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <Link href="/overview" style={{ textDecoration: "none" }}>
            <span className="font-display" style={{ fontSize: "20px", color: "var(--text-primary)" }}>
              FinOps
            </span>
          </Link>
          <LanguageToggle />
        </div>
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
        <PinnedItem href="/overview" labelKey="nav.overview" Icon={ChartLine} active={isOverviewActive} />

        <div style={{ height: "4px" }} />

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
          labelKey="nav.settings"
          Icon={GearSix}
          active={pathname === "/settings" || pathname.startsWith("/settings/")}
        />
      </div>
    </aside>
  );
}
