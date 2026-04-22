"use client";

import { useState } from "react";
import { useT } from "@/lib/i18n";
import type { SettingItem } from "@/lib/types";
import SettingsClient from "./SettingsClient";
import CloudConfigClient from "./CloudConfigClient";

type CloudData = Record<string, Record<string, { value: string; value_type: string; description: string }>>;

export default function SettingsTabs({
  settingsItems,
  cloudData,
}: {
  settingsItems: SettingItem[];
  cloudData: CloudData;
}) {
  const t = useT();
  const [tab, setTab] = useState<0 | 1>(0);

  const tabs = [
    t("section.platform_settings"),
    t("section.cloud_connections"),
  ];

  return (
    <>
      <div style={{ marginBottom: "24px", borderBottom: "1px solid var(--border)", display: "flex", gap: "0" }}>
        {tabs.map((label, i) => (
          <button
            key={label}
            type="button"
            onClick={() => setTab(i as 0 | 1)}
            style={{
              padding: "10px 20px",
              fontSize: "13px",
              fontWeight: 600,
              fontFamily: "Inter, sans-serif",
              color: tab === i ? "var(--text-primary)" : "var(--text-secondary)",
              borderBottom: tab === i ? "2px solid var(--text-primary)" : "2px solid transparent",
              background: "transparent",
              border: "none",
              borderBottomWidth: "2px",
              borderBottomStyle: "solid",
              borderBottomColor: tab === i ? "var(--text-primary)" : "transparent",
              cursor: "pointer",
              transition: "all 0.12s ease",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 0 && <SettingsClient initial={settingsItems} />}
      {tab === 1 && <CloudConfigClient initial={cloudData} />}
    </>
  );
}
