import Link from "next/link";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { EmptyState, ErrorState } from "@/components/primitives/States";
import { ProviderBadge } from "@/components/status/SeverityBadge";
import { API_BASE } from "@/lib/api";
import { formatCurrency } from "@/lib/formatters";
import { getT } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";
export const metadata = { title: "Search — FinOps" };

interface ResourceHit {
  resource_id: string;
  resource_name: string | null;
  service_name: string | null;
  provider: string | null;
  team: string | null;
  env: string | null;
  cost_30d: number;
}
interface TeamHit {
  team: string;
  curr_month_cost: number;
  resource_count: number;
}
interface ServiceHit {
  service_name: string;
  service_category: string | null;
  curr_month_cost: number;
  resource_count: number;
}
interface SearchResponse {
  query: string;
  resources: ResourceHit[];
  teams: TeamHit[];
  services: ServiceHit[];
  total: number;
}

async function fetchSearch(q: string): Promise<SearchResponse> {
  const res = await fetch(
    `${API_BASE}/api/search?q=${encodeURIComponent(q)}&limit=20`,
    { cache: "no-store" },
  );
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

const TH_BASE: React.CSSProperties = {
  textAlign: "left",
  fontSize: "10px",
  fontWeight: 600,
  fontFamily: "Inter, sans-serif",
  color: "var(--text-tertiary)",
  letterSpacing: "0.07em",
  textTransform: "uppercase",
  borderBottom: "1px solid var(--border)",
};

function thStyle(idx: number, count: number, align: "left" | "right" = "left"): React.CSSProperties {
  return {
    ...TH_BASE,
    textAlign: align,
    padding:
      idx === 0
        ? "0 8px 12px 0"
        : idx === count - 1
        ? "0 0 12px 8px"
        : "0 8px 12px 8px",
  };
}

export default async function SearchPage({
  searchParams,
}: {
  searchParams: { q?: string };
}) {
  const t = getT();
  const query = (searchParams.q ?? "").trim();

  if (!query) {
    return (
      <div style={{ maxWidth: "1200px" }}>
        <PageHeader title={t("page.search.title")} description={t("page.search.desc")} />
        <Card>
          <EmptyState
            title={t("page.search.title")}
            description={t("page.search.empty_query")}
          />
        </Card>
      </div>
    );
  }

  let data: SearchResponse;
  try {
    data = await fetchSearch(query);
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { resources, teams, services, total } = data;

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title={`${t("search.results_for")} "${query}"`}
        description={`${total} ${total === 1 ? "match" : "matches"}`}
      />

      {total === 0 && (
        <Card>
          <EmptyState
            title={t("page.search.no_results")}
            description={t("page.search.no_results_desc")}
          />
        </Card>
      )}

      {teams.length > 0 && (
        <Card style={{ marginBottom: "20px" }}>
          <CardHeader>
            {t("search.section.teams")} ({teams.length})
          </CardHeader>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={thStyle(0, 3)}>{t("th.team")}</th>
                <th style={thStyle(1, 3, "right")}>{t("th.cost")}</th>
                <th style={thStyle(2, 3, "right")}>{t("th.resources")}</th>
              </tr>
            </thead>
            <tbody>
              {teams.map((row, i) => (
                <tr
                  key={row.team}
                  style={{
                    borderBottom: i < teams.length - 1 ? "1px solid var(--border)" : "none",
                  }}
                >
                  <td style={{ padding: "10px 8px 10px 0", fontSize: "12px" }}>
                    <Link
                      href={`/teams/${encodeURIComponent(row.team)}`}
                      style={{
                        textDecoration: "none",
                        color: "var(--text-primary)",
                        fontWeight: 600,
                      }}
                    >
                      {row.team}
                    </Link>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span
                      className="font-mono"
                      style={{ fontSize: "12px", color: "var(--text-primary)" }}
                    >
                      {formatCurrency(row.curr_month_cost, { compact: true })}
                    </span>
                  </td>
                  <td
                    style={{
                      padding: "10px 0 10px 8px",
                      textAlign: "right",
                      fontSize: "11px",
                      color: "var(--text-tertiary)",
                    }}
                  >
                    {row.resource_count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {services.length > 0 && (
        <Card style={{ marginBottom: "20px" }}>
          <CardHeader>
            {t("search.section.services")} ({services.length})
          </CardHeader>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={thStyle(0, 4)}>{t("th.service")}</th>
                <th style={thStyle(1, 4)}>{t("th.category")}</th>
                <th style={thStyle(2, 4, "right")}>{t("th.cost")}</th>
                <th style={thStyle(3, 4, "right")}>{t("th.resources")}</th>
              </tr>
            </thead>
            <tbody>
              {services.map((row, i) => (
                <tr
                  key={row.service_name}
                  style={{
                    borderBottom: i < services.length - 1 ? "1px solid var(--border)" : "none",
                  }}
                >
                  <td style={{ padding: "10px 8px 10px 0", fontSize: "12px" }}>
                    <Link
                      href={`/services/${encodeURIComponent(row.service_name)}`}
                      style={{
                        textDecoration: "none",
                        color: "var(--text-primary)",
                        fontWeight: 600,
                      }}
                    >
                      {row.service_name}
                    </Link>
                  </td>
                  <td
                    style={{
                      padding: "10px 8px",
                      fontSize: "11px",
                      color: "var(--text-tertiary)",
                    }}
                  >
                    {row.service_category ?? "—"}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span
                      className="font-mono"
                      style={{ fontSize: "12px", color: "var(--text-primary)" }}
                    >
                      {formatCurrency(row.curr_month_cost, { compact: true })}
                    </span>
                  </td>
                  <td
                    style={{
                      padding: "10px 0 10px 8px",
                      textAlign: "right",
                      fontSize: "11px",
                      color: "var(--text-tertiary)",
                    }}
                  >
                    {row.resource_count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {resources.length > 0 && (
        <Card>
          <CardHeader>
            {t("search.section.resources")} ({resources.length})
          </CardHeader>
          <div className="table-responsive">
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={thStyle(0, 6)}>{t("th.resource")}</th>
                  <th style={thStyle(1, 6)}>{t("th.service")}</th>
                  <th style={{ ...thStyle(2, 6), textAlign: "center" }}>{t("th.provider")}</th>
                  <th style={thStyle(3, 6)}>{t("th.team")}</th>
                  <th style={{ ...thStyle(4, 6), textAlign: "center" }}>{t("th.env")}</th>
                  <th style={thStyle(5, 6, "right")}>{t("th.cost_30d")}</th>
                </tr>
              </thead>
              <tbody>
                {resources.map((row, i) => (
                  <tr
                    key={row.resource_id}
                    style={{
                      borderBottom: i < resources.length - 1 ? "1px solid var(--border)" : "none",
                    }}
                  >
                    <td style={{ padding: "10px 8px 10px 0" }}>
                      <Link
                        href={`/resources/${encodeURIComponent(row.resource_id)}`}
                        style={{ textDecoration: "none" }}
                      >
                        <code
                          className="font-mono"
                          style={{ fontSize: "11px", color: "var(--text-primary)" }}
                        >
                          {row.resource_name ?? row.resource_id}
                        </code>
                      </Link>
                    </td>
                    <td
                      style={{
                        padding: "10px 8px",
                        fontSize: "12px",
                        color: "var(--text-secondary)",
                      }}
                    >
                      {row.service_name ?? "—"}
                    </td>
                    <td style={{ padding: "10px 8px", textAlign: "center" }}>
                      {row.provider ? (
                        <ProviderBadge provider={row.provider as "aws" | "gcp" | "azure"} />
                      ) : (
                        <span style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>—</span>
                      )}
                    </td>
                    <td
                      style={{
                        padding: "10px 8px",
                        fontSize: "12px",
                        color: "var(--text-secondary)",
                      }}
                    >
                      {row.team ? (
                        <Link
                          href={`/teams/${encodeURIComponent(row.team)}`}
                          style={{
                            textDecoration: "none",
                            color: "var(--text-secondary)",
                          }}
                        >
                          {row.team}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td
                      style={{
                        padding: "10px 8px",
                        textAlign: "center",
                        fontSize: "11px",
                        color: "var(--text-tertiary)",
                      }}
                    >
                      {row.env ?? "—"}
                    </td>
                    <td style={{ padding: "10px 0 10px 8px", textAlign: "right" }}>
                      <span
                        className="font-mono"
                        style={{ fontSize: "12px", color: "var(--text-primary)" }}
                      >
                        {formatCurrency(row.cost_30d, { compact: true })}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
