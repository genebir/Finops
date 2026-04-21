"use client";

import { Plus, PencilSimple, Trash, Check, X } from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";

import { Card, CardHeader } from "@/components/primitives/Card";
import { EmptyState } from "@/components/primitives/States";
import { SeverityBadge } from "@/components/status/SeverityBadge";
import { api } from "@/lib/api";
import type { BudgetEntry, FiltersData } from "@/lib/types";

const inputStyle: React.CSSProperties = {
  fontFamily: "Inter, sans-serif",
  fontSize: "13px",
  padding: "6px 10px",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-button)",
  background: "var(--bg-warm)",
  color: "var(--text-primary)",
  outline: "none",
  minWidth: "100px",
};

const btnStyle: React.CSSProperties = {
  fontFamily: "Inter, sans-serif",
  fontSize: "12px",
  fontWeight: 500,
  padding: "6px 12px",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-button)",
  background: "var(--bg-warm)",
  color: "var(--text-primary)",
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
};

const btnPrimary: React.CSSProperties = {
  ...btnStyle,
  background: "var(--text-primary)",
  color: "#fff",
  border: "1px solid var(--text-primary)",
};

const iconBtn: React.CSSProperties = {
  padding: "4px",
  border: "none",
  background: "transparent",
  cursor: "pointer",
  color: "var(--text-tertiary)",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
};

export default function BudgetManager({ filters }: { filters: FiltersData }) {
  const [entries, setEntries] = useState<BudgetEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create form
  const [newTeam, setNewTeam] = useState("");
  const [newEnv, setNewEnv] = useState(filters.envs[0] ?? "prod");
  const [newAmount, setNewAmount] = useState("");
  const [newMonth, setNewMonth] = useState("default");
  const [creating, setCreating] = useState(false);

  // Inline edit state
  const [editKey, setEditKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.budgetEntries();
      setEntries(data.items);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newTeam || !newEnv || !newAmount) return;
    setCreating(true);
    setError(null);
    try {
      await api.createBudget({
        team: newTeam,
        env: newEnv,
        budget_amount: Number(newAmount),
        billing_month: newMonth || "default",
      });
      setNewTeam("");
      setNewAmount("");
      setNewMonth("default");
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setCreating(false);
    }
  }

  async function handleSaveEdit(entry: BudgetEntry) {
    setError(null);
    try {
      await api.updateBudget(entry.team, entry.env, Number(editValue), entry.billing_month);
      setEditKey(null);
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  async function handleDelete(entry: BudgetEntry) {
    if (!confirm(`Delete budget for ${entry.team} / ${entry.env} (${entry.billing_month})?`)) return;
    setError(null);
    try {
      await api.deleteBudget(entry.team, entry.env, entry.billing_month);
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  const entryKey = (e: BudgetEntry) => `${e.team}|${e.env}|${e.billing_month}`;

  return (
    <Card>
      <CardHeader>Manage Budget Entries</CardHeader>

      {error && (
        <p style={{ fontSize: "12px", color: "var(--status-critical)", marginBottom: "12px" }}>
          {error}
        </p>
      )}

      <form
        onSubmit={handleCreate}
        style={{
          display: "flex",
          gap: "8px",
          alignItems: "center",
          flexWrap: "wrap",
          marginBottom: "20px",
          paddingBottom: "20px",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <input
          list="team-list"
          placeholder="team"
          value={newTeam}
          onChange={(e) => setNewTeam(e.target.value)}
          style={inputStyle}
          required
        />
        <datalist id="team-list">
          {filters.teams.map((t) => <option key={t} value={t} />)}
          <option value="*" />
        </datalist>

        <select value={newEnv} onChange={(e) => setNewEnv(e.target.value)} style={inputStyle}>
          {filters.envs.map((v) => <option key={v} value={v}>{v}</option>)}
          <option value="*">* (all envs)</option>
        </select>

        <input
          type="number"
          min="0"
          step="0.01"
          placeholder="Amount (USD)"
          value={newAmount}
          onChange={(e) => setNewAmount(e.target.value)}
          style={{ ...inputStyle, minWidth: "140px" }}
          required
        />

        <input
          placeholder="billing_month (default | YYYY-MM)"
          value={newMonth}
          onChange={(e) => setNewMonth(e.target.value)}
          style={{ ...inputStyle, minWidth: "200px" }}
        />

        <button type="submit" style={btnPrimary} disabled={creating}>
          <Plus size={14} weight="bold" />
          {creating ? "Adding…" : "Add budget"}
        </button>
      </form>

      {loading ? (
        <p style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>Loading entries…</p>
      ) : entries.length === 0 ? (
        <EmptyState
          title="No budget entries"
          description="Add a budget above or run the budget pipeline in Dagster."
        />
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["Team", "Env", "Amount", "Billing Month", ""].map((h) => (
                <th
                  key={h}
                  style={{
                    textAlign: h === "Amount" ? "right" : "left",
                    fontSize: "10px",
                    fontWeight: 600,
                    fontFamily: "Inter, sans-serif",
                    color: "var(--text-tertiary)",
                    letterSpacing: "0.07em",
                    textTransform: "uppercase",
                    paddingBottom: "12px",
                    borderBottom: "1px solid var(--border)",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, i) => {
              const isEditing = editKey === entryKey(entry);
              return (
                <tr
                  key={entryKey(entry)}
                  style={{
                    borderBottom: i < entries.length - 1 ? "1px solid var(--border)" : "none",
                  }}
                >
                  <td style={{ padding: "10px 0", fontSize: "13px", fontWeight: 500, color: "var(--text-primary)" }}>
                    {entry.team}
                  </td>
                  <td style={{ padding: "10px 8px" }}>
                    <SeverityBadge severity={entry.env} />
                  </td>
                  <td style={{ padding: "10px 8px", textAlign: "right" }}>
                    {isEditing ? (
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        style={{ ...inputStyle, width: "120px", textAlign: "right" }}
                        autoFocus
                      />
                    ) : (
                      <span className="font-mono" style={{ fontSize: "12px", color: "var(--text-primary)" }}>
                        <span className="currency-symbol">$</span>
                        {Math.round(entry.budget_amount).toLocaleString("en-US")}
                      </span>
                    )}
                  </td>
                  <td style={{ padding: "10px 8px" }}>
                    <code
                      className="font-mono"
                      style={{ fontSize: "11px", color: "var(--text-secondary)" }}
                    >
                      {entry.billing_month}
                    </code>
                  </td>
                  <td style={{ padding: "10px 0 10px 8px", textAlign: "right", whiteSpace: "nowrap" }}>
                    {isEditing ? (
                      <>
                        <button
                          type="button"
                          style={{ ...iconBtn, color: "var(--status-healthy)" }}
                          onClick={() => handleSaveEdit(entry)}
                          title="Save"
                        >
                          <Check size={16} weight="bold" />
                        </button>
                        <button
                          type="button"
                          style={iconBtn}
                          onClick={() => setEditKey(null)}
                          title="Cancel"
                        >
                          <X size={16} weight="bold" />
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          style={iconBtn}
                          onClick={() => {
                            setEditKey(entryKey(entry));
                            setEditValue(String(entry.budget_amount));
                          }}
                          title="Edit"
                        >
                          <PencilSimple size={16} />
                        </button>
                        <button
                          type="button"
                          style={{ ...iconBtn, color: "var(--status-critical)" }}
                          onClick={() => handleDelete(entry)}
                          title="Delete"
                        >
                          <Trash size={16} />
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
  );
}
