"use client";

import { useState } from "react";
import { PencilSimple, Check, X, Trash } from "@phosphor-icons/react";
import { Card, CardHeader } from "@/components/primitives/Card";
import { API_BASE } from "@/lib/api";

interface AllocationRule {
  id: number;
  resource_id: string;
  team: string;
  split_pct: number;
  description: string | null;
}

interface AllocationItem {
  allocated_team: string;
  resource_id: string;
  resource_name: string | null;
  service_name: string | null;
  provider: string;
  split_pct: number;
  allocation_type: string;
  total_allocated: number;
  total_original: number;
}

interface Props {
  initialRules: AllocationRule[];
  billingMonth: string;
  allocatedItems: AllocationItem[];
}

const iconBtn: React.CSSProperties = {
  padding: "4px",
  border: "none",
  background: "transparent",
  cursor: "pointer",
  color: "var(--text-tertiary)",
  display: "inline-flex",
  alignItems: "center",
};

const RULES_HEADERS = ["Resource ID", "Team", "Split %", "Description", ""];
const ALLOC_HEADERS = ["Team", "Resource", "Service", "Provider", "Split", "Allocated", "Original"];

export default function AllocationClient({ initialRules, billingMonth, allocatedItems }: Props) {
  const [rules, setRules] = useState<AllocationRule[]>(initialRules);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editSplitPct, setEditSplitPct] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // New rule form
  const [showAdd, setShowAdd] = useState(false);
  const [newResourceId, setNewResourceId] = useState("");
  const [newTeam, setNewTeam] = useState("");
  const [newSplitPct, setNewSplitPct] = useState("100");
  const [newDesc, setNewDesc] = useState("");
  const [adding, setAdding] = useState(false);

  async function startEdit(rule: AllocationRule) {
    setEditingId(rule.id);
    setEditSplitPct(String(rule.split_pct));
    setEditDesc(rule.description ?? "");
  }

  async function saveEdit(id: number) {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/cost-allocation/rules/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ split_pct: parseFloat(editSplitPct), description: editDesc || null }),
      });
      if (!res.ok) throw new Error(await res.text());
      const updated: AllocationRule = await res.json();
      setRules((prev) => prev.map((r) => (r.id === id ? updated : r)));
      setEditingId(null);
    } catch (e) {
      setError(String(e));
    }
  }

  async function deleteRule(id: number) {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/cost-allocation/rules/${id}`, { method: "DELETE" });
      if (!res.ok && res.status !== 204) throw new Error(await res.text());
      setRules((prev) => prev.filter((r) => r.id !== id));
      setDeletingId(null);
    } catch (e) {
      setError(String(e));
    }
  }

  async function addRule() {
    setAdding(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/cost-allocation/rules`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resource_id: newResourceId,
          team: newTeam,
          split_pct: parseFloat(newSplitPct),
          description: newDesc || null,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const created: AllocationRule = await res.json();
      setRules((prev) => [...prev, created]);
      setNewResourceId("");
      setNewTeam("");
      setNewSplitPct("100");
      setNewDesc("");
      setShowAdd(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setAdding(false);
    }
  }

  const inputStyle: React.CSSProperties = {
    fontFamily: '"JetBrains Mono", monospace',
    fontSize: "12px",
    padding: "4px 8px",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-button)",
    background: "var(--bg-warm)",
    color: "var(--text-primary)",
    outline: "none",
  };

  return (
    <div>
      {error && (
        <p style={{ fontSize: "12px", color: "var(--status-critical)", marginBottom: "12px" }}>
          {error}
        </p>
      )}

      {/* Rules CRUD */}
      <Card style={{ marginBottom: "24px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
          <p style={{ fontFamily: "Inter, sans-serif", fontSize: "13px", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>
            Allocation Rules
          </p>
          <button
            onClick={() => setShowAdd(!showAdd)}
            style={{
              padding: "6px 14px",
              borderRadius: "var(--radius-button)",
              border: "1px solid var(--border)",
              background: "transparent",
              fontSize: "12px",
              fontWeight: 600,
              color: "var(--text-secondary)",
              cursor: "pointer",
            }}
          >
            {showAdd ? "Cancel" : "+ Add Rule"}
          </button>
        </div>

        {showAdd && (
          <div style={{
            marginBottom: "16px", padding: "12px 16px", borderRadius: "var(--radius-button)",
            border: "1px solid var(--border)", background: "color-mix(in srgb, var(--border) 20%, transparent)",
            display: "grid", gridTemplateColumns: "1fr 1fr 80px 1fr auto", gap: "8px", alignItems: "center",
          }}>
            <input
              placeholder="resource_id"
              value={newResourceId}
              onChange={(e) => setNewResourceId(e.target.value)}
              style={{ ...inputStyle, width: "100%" }}
            />
            <input
              placeholder="team"
              value={newTeam}
              onChange={(e) => setNewTeam(e.target.value)}
              style={{ ...inputStyle, width: "100%" }}
            />
            <input
              type="number"
              min={1}
              max={100}
              step={1}
              placeholder="%"
              value={newSplitPct}
              onChange={(e) => setNewSplitPct(e.target.value)}
              style={{ ...inputStyle, width: "100%" }}
            />
            <input
              placeholder="description (optional)"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              style={{ ...inputStyle, width: "100%" }}
            />
            <button
              onClick={addRule}
              disabled={adding || !newResourceId || !newTeam}
              style={{
                ...iconBtn,
                color: "var(--status-healthy)",
                padding: "6px 12px",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-button)",
                fontSize: "12px",
                fontWeight: 600,
              }}
            >
              {adding ? "…" : "Save"}
            </button>
          </div>
        )}

        {rules.length === 0 ? (
          <p style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>
            No allocation rules. Add one above to split resource costs across teams.
          </p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {RULES_HEADERS.map((h, idx, arr) => (
                  <th
                    key={h || idx}
                    style={{
                      textAlign: "left",
                      fontSize: "10px",
                      fontWeight: 600,
                      fontFamily: "Inter, sans-serif",
                      color: "var(--text-tertiary)",
                      letterSpacing: "0.07em",
                      textTransform: "uppercase",
                      padding:
                        idx === 0
                          ? "0 8px 12px 0"
                          : idx === arr.length - 1
                          ? "0 0 12px 8px"
                          : "0 8px 12px 8px",
                      borderBottom: "1px solid var(--border)",
                      width: h === "" ? "80px" : h === "Split %" ? "80px" : undefined,
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rules.map((rule, i, arr) => {
                const isEdit = editingId === rule.id;
                const isDelete = deletingId === rule.id;
                return (
                  <tr
                    key={rule.id}
                    style={{ borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}
                  >
                    <td style={{ padding: "8px 8px 8px 0" }}>
                      <code className="font-mono" style={{ fontSize: "11px", color: "var(--text-primary)" }}>
                        {rule.resource_id}
                      </code>
                    </td>
                    <td style={{ padding: "8px" }}>
                      {isEdit ? (
                        <input
                          value={editSplitPct}
                          readOnly
                          style={{ ...inputStyle, width: "60px" }}
                          title="Edit via Split % column"
                        />
                      ) : (
                        <span style={{ fontSize: "13px", color: "var(--text-secondary)" }}>{rule.team}</span>
                      )}
                    </td>
                    <td style={{ padding: "8px", textAlign: "right" }}>
                      {isEdit ? (
                        <input
                          type="number"
                          min={1}
                          max={100}
                          value={editSplitPct}
                          onChange={(e) => setEditSplitPct(e.target.value)}
                          style={{ ...inputStyle, width: "60px", textAlign: "right" }}
                        />
                      ) : (
                        <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-primary)" }}>
                          {rule.split_pct}%
                        </span>
                      )}
                    </td>
                    <td style={{ padding: "8px" }}>
                      {isEdit ? (
                        <input
                          value={editDesc}
                          onChange={(e) => setEditDesc(e.target.value)}
                          style={{ ...inputStyle, width: "100%" }}
                          placeholder="description"
                        />
                      ) : (
                        <span style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
                          {rule.description || "—"}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: "8px 0 8px 8px", textAlign: "right", whiteSpace: "nowrap" }}>
                      {isEdit ? (
                        <>
                          <button type="button" style={{ ...iconBtn, color: "var(--status-healthy)" }} onClick={() => saveEdit(rule.id)} title="Save">
                            <Check size={15} weight="bold" />
                          </button>
                          <button type="button" style={iconBtn} onClick={() => setEditingId(null)} title="Cancel">
                            <X size={15} weight="bold" />
                          </button>
                        </>
                      ) : isDelete ? (
                        <>
                          <button type="button" style={{ ...iconBtn, color: "var(--status-critical)" }} onClick={() => deleteRule(rule.id)} title="Confirm delete">
                            <Check size={15} weight="bold" />
                          </button>
                          <button type="button" style={iconBtn} onClick={() => setDeletingId(null)} title="Cancel">
                            <X size={15} weight="bold" />
                          </button>
                        </>
                      ) : (
                        <>
                          <button type="button" style={iconBtn} onClick={() => startEdit(rule)} title="Edit">
                            <PencilSimple size={14} />
                          </button>
                          <button type="button" style={{ ...iconBtn, color: "var(--status-critical)" }} onClick={() => setDeletingId(rule.id)} title="Delete">
                            <Trash size={14} />
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>

      {/* Allocated costs view */}
      <Card>
        <CardHeader>Allocated Costs — {billingMonth}</CardHeader>
        {allocatedItems.length === 0 ? (
          <p style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>
            No allocated costs for this period. Run the <code className="font-mono" style={{ fontSize: "11px" }}>cost_allocation</code> asset in Dagster.
          </p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {ALLOC_HEADERS.map((h, idx, arr) => (
                  <th
                    key={h}
                    style={{
                      textAlign: idx >= 5 ? "right" : "left",
                      fontSize: "10px",
                      fontWeight: 600,
                      fontFamily: "Inter, sans-serif",
                      color: "var(--text-tertiary)",
                      letterSpacing: "0.07em",
                      textTransform: "uppercase",
                      padding:
                        idx === 0
                          ? "0 8px 12px 0"
                          : idx === arr.length - 1
                          ? "0 0 12px 8px"
                          : "0 8px 12px 8px",
                      borderBottom: "1px solid var(--border)",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {allocatedItems.map((item, i, arr) => (
                <tr
                  key={`${item.resource_id}-${item.allocated_team}`}
                  style={{ borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none" }}
                >
                  <td style={{ padding: "10px 8px 10px 0", fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
                    {item.allocated_team}
                  </td>
                  <td style={{ padding: "10px 8px" }}>
                    <code className="font-mono" style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                      {item.resource_id}
                    </code>
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "13px", color: "var(--text-secondary)" }}>
                    {item.service_name || "—"}
                  </td>
                  <td style={{ padding: "10px 8px", fontSize: "13px", color: "var(--text-secondary)" }}>
                    {item.provider}
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                      {item.split_pct}%
                    </span>
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-primary)" }}>
                      <span className="currency-symbol">$</span>
                      {Math.round(Number(item.total_allocated)).toLocaleString("en-US")}
                    </span>
                  </td>
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "right" }}>
                    <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-tertiary)" }}>
                      <span className="currency-symbol">$</span>
                      {Math.round(Number(item.total_original)).toLocaleString("en-US")}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
