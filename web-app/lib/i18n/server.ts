import { cookies } from "next/headers";
import type { Locale, TranslationKey } from "./translations";
import { translations } from "./translations";

export function getLocale(): Locale {
  try {
    const cookieStore = cookies();
    const val = cookieStore.get("finops-locale")?.value;
    if (val === "ko" || val === "en") return val;
  } catch {
    // cookies() not available outside request context
  }
  return "en";
}

export function getT(): (key: TranslationKey) => string {
  const locale = getLocale();
  return (key: TranslationKey): string => {
    const entry = translations[key];
    if (!entry) return key;
    return entry[locale] ?? entry.en;
  };
}
