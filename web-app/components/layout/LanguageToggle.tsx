"use client";

import { useI18n } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";

const LOCALES: { value: Locale; label: string }[] = [
  { value: "en", label: "EN" },
  { value: "ko", label: "KO" },
];

export default function LanguageToggle() {
  const { locale, setLocale } = useI18n();

  return (
    <div style={{ display: "flex", gap: "2px", padding: "2px", borderRadius: "var(--radius-button)", background: "var(--border)" }}>
      {LOCALES.map(({ value, label }) => (
        <button
          key={value}
          onClick={() => setLocale(value)}
          style={{
            padding: "3px 10px",
            borderRadius: "calc(var(--radius-button) - 2px)",
            border: "none",
            fontSize: "11px",
            fontWeight: locale === value ? 600 : 400,
            fontFamily: "Inter, sans-serif",
            color: locale === value ? "var(--text-primary)" : "var(--text-tertiary)",
            background: locale === value ? "var(--bg-warm)" : "transparent",
            cursor: "pointer",
            transition: "all 0.12s ease",
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
