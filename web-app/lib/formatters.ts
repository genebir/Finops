/** design-system.md §8 금액 표시 규칙 */

export function formatCurrency(value: number, opts?: { decimals?: number; compact?: boolean }): string {
  const { decimals = 0, compact = false } = opts ?? {};

  if (compact && Math.abs(value) >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(1)}M`;
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatPct(value: number, opts?: { sign?: boolean }): string {
  const s = value.toFixed(1);
  return opts?.sign && value > 0 ? `+${s}%` : `${s}%`;
}

export function formatDelta(value: number): { text: string; arrow: string; bad: boolean } {
  const bad = value > 0; // 비용 맥락에서 증가 = bad
  const arrow = value > 0 ? "▲" : "▼";
  return { text: `${Math.abs(value).toFixed(1)}%`, arrow, bad };
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
