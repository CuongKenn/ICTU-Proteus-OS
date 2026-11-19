// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React from "react";
import { useLang } from "@/components/i18n/LanguageContext";

export const LanguageToggle: React.FC<{ className?: string }> = ({ className }) => {
  const { lang, setLang } = useLang();

  return (
    <button
      type="button"
      onClick={() => setLang(lang === "vi" ? "en" : "vi")}
      className={`px-2.5 py-1 rounded-md text-xs font-medium tracking-wide uppercase border border-line-hi text-muted hover:text-ink hover:bg-paper-subtle hover:border-ghost transition-colors cursor-pointer ${className || ""}`}
      title={lang === "vi" ? "Switch to English" : "Chuyển sang Tiếng Việt"}
      aria-label="Toggle language"
    >
      {lang === "vi" ? "EN" : "VI"}
    </button>
  );
};
