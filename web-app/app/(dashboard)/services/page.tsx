import { API_BASE } from "../../../lib/api";
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { ErrorState } from "@/components/primitives/States";

export const metadata = { title: "Services — FinOps" };

interface CategoryItem { category: string; cost: number; resource_count: number; pct: number }
interface ServiceItem { service_name: string; category: string; cost: number; resource_count: number; pct: number }
interface ServiceBreakdownData {
  billing_month: string; grand_total: number;
  by_category: CategoryItem[]; by_service: ServiceItem[];
}

async function fetchServices(): Promise<ServiceBreakdownData> {
  const res = await fetch(`${API_BASE}/api/service-breakdown`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error("Failed to load service breakdown");
  return res.json();
}

const CATEGORY_COLORS = [
  "var(--provider-aws)",
  "var(--provider-gcp)",
  "var(--provider-azure)",
  "var(--status-healthy)",
  "#9B7BB5",
  "#5B9B9B",
  "var(--status-critical)",
  "var(--status-under)",
];

function PctBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div style={{ height: "8px", background: "var(--border)", borderRadius: "4px", overflow: "hidden", flex: 1 }}>
      <div style={{ height: "100%", width: `${Math.min(pct, 100)}%`, background: color, borderRadius: "4px" }} />
    </div>
  );
}

const svcHeaders = ["Service", "Category", "Cost"];

export default async function ServicesPage() {
  let data: ServiceBreakdownData;
  try {
    data = await fetchServices();
  } catch (e) {
    return <ErrorState message={String(e)} />;
  }

  const { billing_month, grand_total, by_category, by_service } = data;

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title="Service Breakdown"
        description={`${billing_month} — total $${grand_total.toLocaleString("en-US", { maximumFractionDigits: 0 })} by service category`}
      />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
        {/* By category */}
        <Card>
          <CardHeader>By Service Category</CardHeader>
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {by_category.map((cat, idx) => {
              const color = CATEGORY_COLORS[idx % CATEGORY_COLORS.length];
              return (
                <div key={cat.category}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                    <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-primary)" }}>{cat.category}</span>
                    <div style={{ fontSize: "12px", color: "var(--text-secondary)", textAlign: "right" }}>
                      <span className="font-mono">${cat.cost.toLocaleString("en-US", { maximumFractionDigits: 0 })}</span>
                      <span style={{ marginLeft: "8px" }}>{cat.pct.toFixed(1)}%</span>
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <PctBar pct={cat.pct} color={color} />
                    <span style={{ fontSize: "10px", color: "var(--text-tertiary)", minWidth: "50px" }}>
                      {cat.resource_count} res.
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        {/* By service name */}
        <Card>
          <CardHeader>Top Services</CardHeader>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {svcHeaders.map((h, idx, arr) => (
                  <th key={h} style={{
                    textAlign: idx === arr.length - 1 ? "right" : "left",
                    fontSize: "10px",
                    fontWeight: 600,
                    fontFamily: "Inter, sans-serif",
                    color: "var(--text-tertiary)",
                    letterSpacing: "0.07em",
                    textTransform: "uppercase",
                    padding: idx === 0 ? "0 8px 12px 0" : idx === arr.length - 1 ? "0 0 12px 8px" : "0 8px 12px 8px",
                    borderBottom: "1px solid var(--border)",
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {by_service.map((svc, idx, arr) => (
                <tr key={idx} style={{ borderBottom: idx < arr.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <td style={{ padding: "10px 0", color: "var(--text-primary)", fontSize: "13px", maxWidth: "140px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {svc.service_name}
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "12px", color: "var(--text-secondary)" }}>{svc.category}</td>
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-primary)" }}>
                      ${svc.cost.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                    </span>
                    <span style={{ color: "var(--text-tertiary)", marginLeft: "6px", fontSize: "11px" }}>
                      {svc.pct.toFixed(1)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  );
}
