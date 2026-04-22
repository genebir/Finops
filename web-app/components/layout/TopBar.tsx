"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useT } from "@/lib/i18n";
import type { TranslationKey } from "@/lib/i18n";

interface Crumb {
  label: TranslationKey;
  href?: string;
}

interface RouteEntry {
  groupLabel: TranslationKey;
  pageLabel: TranslationKey;
  groupHref?: string;
}

const ROUTE_MAP: Record<string, RouteEntry> = {
  "/cost-explorer":    { groupLabel: "nav.costs",      pageLabel: "nav.cost_explorer" },
  "/cloud-compare":    { groupLabel: "nav.costs",      pageLabel: "nav.cloud_compare" },
  "/services":         { groupLabel: "nav.costs",      pageLabel: "nav.services" },
  "/leaderboard":      { groupLabel: "nav.costs",      pageLabel: "nav.leaderboard" },
  "/env-breakdown":    { groupLabel: "nav.costs",      pageLabel: "nav.env_breakdown" },
  "/cost-trend":       { groupLabel: "nav.costs",      pageLabel: "nav.cost_trend" },
  "/cost-heatmap":     { groupLabel: "nav.costs",      pageLabel: "nav.cost_heatmap" },

  "/anomalies":        { groupLabel: "nav.anomalies",  pageLabel: "nav.anomalies" },
  "/anomaly-timeline": { groupLabel: "nav.anomalies",  pageLabel: "nav.timeline" },
  "/risk":             { groupLabel: "nav.anomalies",  pageLabel: "nav.risk" },

  "/budget":           { groupLabel: "nav.budget",     pageLabel: "nav.budget" },
  "/budget-forecast":  { groupLabel: "nav.budget",     pageLabel: "nav.budget_forecast" },
  "/burn-rate":        { groupLabel: "nav.budget",     pageLabel: "nav.burn_rate" },
  "/savings":          { groupLabel: "nav.budget",     pageLabel: "nav.savings" },
  "/chargeback":       { groupLabel: "nav.budget",     pageLabel: "nav.chargeback" },
  "/showback":         { groupLabel: "nav.budget",     pageLabel: "nav.showback" },
  "/cost-allocation":  { groupLabel: "nav.budget",     pageLabel: "nav.allocation" },
  "/recommendations":  { groupLabel: "nav.budget",     pageLabel: "nav.suggestions" },

  "/tag-compliance":   { groupLabel: "nav.compliance", pageLabel: "nav.tag_compliance" },
  "/tag-policy":       { groupLabel: "nav.compliance", pageLabel: "nav.tag_policy" },
  "/inventory":        { groupLabel: "nav.compliance", pageLabel: "nav.inventory" },
  "/data-quality":     { groupLabel: "nav.compliance", pageLabel: "nav.data_quality" },

  "/pipeline":         { groupLabel: "nav.operations", pageLabel: "nav.pipeline" },
  "/forecast":         { groupLabel: "nav.operations", pageLabel: "nav.forecast" },
  "/alerts":           { groupLabel: "nav.operations", pageLabel: "nav.alerts" },
  "/ops":              { groupLabel: "nav.operations", pageLabel: "nav.ops" },

  "/cloud-config":     { groupLabel: "nav.settings",   pageLabel: "nav.cloud_config" },
};

function buildCrumbs(pathname: string): Crumb[] {
  if (pathname === "/" || pathname === "/overview") {
    return [{ label: "nav.overview" }];
  }

  if (pathname === "/settings") {
    return [{ label: "nav.settings" }];
  }

  const segments = pathname.split("/").filter(Boolean);
  const base = "/" + segments[0];

  if (segments[0] === "resources" && segments[1]) {
    return [
      { label: "nav.compliance", href: "/inventory" },
      { label: "nav.inventory", href: "/inventory" },
    ];
  }

  if (segments[0] === "teams" && segments[1]) {
    return [
      { label: "nav.costs", href: "/leaderboard" },
      { label: "nav.leaderboard", href: "/leaderboard" },
    ];
  }

  if (segments[0] === "services" && segments[1]) {
    return [
      { label: "nav.costs", href: "/services" },
      { label: "nav.services", href: "/services" },
    ];
  }

  if (segments[0] === "environments" && segments[1]) {
    return [
      { label: "nav.costs", href: "/env-breakdown" },
      { label: "nav.env_breakdown", href: "/env-breakdown" },
    ];
  }

  const entry = ROUTE_MAP[base];
  if (entry) {
    return [
      { label: entry.groupLabel },
      { label: entry.pageLabel },
    ];
  }

  return [];
}

export default function TopBar() {
  const pathname = usePathname();
  const t = useT();
  const crumbs = buildCrumbs(pathname);

  const segments = pathname.split("/").filter(Boolean);
  const isDrillDown = (
    (segments[0] === "resources" && segments[1]) ||
    (segments[0] === "teams" && segments[1]) ||
    (segments[0] === "services" && segments[1]) ||
    (segments[0] === "environments" && segments[1])
  );
  const drillDownName = isDrillDown ? decodeURIComponent(segments[1]) : null;

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        height: "56px",
        backgroundColor: "var(--bg-warm)",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        padding: "0 40px",
        zIndex: 30,
        gap: "8px",
      }}
    >
      <Link
        href="/overview"
        style={{
          fontSize: "11px",
          color: "var(--text-tertiary)",
          fontFamily: "Inter, sans-serif",
          textDecoration: "none",
        }}
      >
        FinOps
      </Link>

      {crumbs.map((crumb, i) => (
        <span key={i} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "11px", color: "var(--border-strong)" }}>/</span>
          {crumb.href ? (
            <Link
              href={crumb.href}
              style={{
                fontSize: i === crumbs.length - 1 && !drillDownName ? "13px" : "11px",
                fontWeight: i === crumbs.length - 1 && !drillDownName ? 500 : 400,
                color: i === crumbs.length - 1 && !drillDownName ? "var(--text-secondary)" : "var(--text-tertiary)",
                fontFamily: "Inter, sans-serif",
                textDecoration: "none",
              }}
            >
              {t(crumb.label)}
            </Link>
          ) : (
            <span
              style={{
                fontSize: i === crumbs.length - 1 && !drillDownName ? "13px" : "11px",
                fontWeight: i === crumbs.length - 1 && !drillDownName ? 500 : 400,
                color: i === crumbs.length - 1 && !drillDownName ? "var(--text-secondary)" : "var(--text-tertiary)",
                fontFamily: "Inter, sans-serif",
              }}
            >
              {t(crumb.label)}
            </span>
          )}
        </span>
      ))}

      {drillDownName && (
        <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "11px", color: "var(--border-strong)" }}>/</span>
          <span
            style={{
              fontSize: "13px",
              fontWeight: 500,
              color: "var(--text-secondary)",
              fontFamily: "Inter, sans-serif",
              maxWidth: "300px",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {drillDownName}
          </span>
        </span>
      )}
    </header>
  );
}
