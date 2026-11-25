// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React, { useMemo, useRef, useState, useEffect } from "react";
import { AppShell } from "@/components/AppShell";
import { SsoEmbed } from "@/components/ui/SsoEmbed";
import { usePlugins } from "@/hooks/usePlugins";

interface PluginPageProps {
  params: {
    code_name: string;
  };
}

function resolvePluginBaseUrl(rawUrl: string | null | undefined, codeName: string): string {
  const mfeBase = (process.env.NEXT_PUBLIC_PLUGINS_MFE_URL || "/plugins-mfe").replace(
    /\/+$/,
    ""
  );
  if (!rawUrl) {
    return `${mfeBase}/${codeName}`;
  }
  return rawUrl
    .replace(/\$\{PLUGINS_MFE_URL\}/g, mfeBase)
    .replace(/\/+$/, "");
}

function isInternalMfeUrl(url: string): boolean {
  const trimmed = url.trim();
  if (!trimmed) return false;

  const appsmithBase = (
    process.env.NEXT_PUBLIC_APPSMITH_URL || "http://apps.proteus.local"
  ).toLowerCase();
  if (trimmed.toLowerCase().startsWith(appsmithBase)) {
    return false;
  }

  if (trimmed.startsWith("/plugins-mfe")) {
    return true;
  }

  const configuredMfe = (process.env.NEXT_PUBLIC_PLUGINS_MFE_URL || "").trim();
  if (configuredMfe && trimmed.startsWith(configuredMfe.replace(/\/+$/, ""))) {
    return true;
  }

  try {
    const parsed = new URL(
      trimmed,
      typeof window !== "undefined" ? window.location.origin : "http://localhost:3000"
    );
    if (parsed.pathname.startsWith("/plugins-mfe")) {
      return true;
    }
    if (
      typeof window !== "undefined" &&
      parsed.hostname === window.location.hostname &&
      !parsed.pathname.startsWith("/app/")
    ) {
      return true;
    }
  } catch {
    return false;
  }

  return false;
}

function buildSeamlessMfeSrc(baseUrl: string): string {
  const sep = baseUrl.includes("?") ? "&" : "?";
  let currentTheme = "light";
  if (typeof document !== "undefined") {
    currentTheme = document.documentElement.classList.contains("dark")
      ? "dark"
      : "light";
  }
  return `${baseUrl}${sep}embed=1&theme=${currentTheme}`;
}

export default function PluginPage({ params }: PluginPageProps) {
  const { code_name } = params;
  const { plugins, isLoading } = usePlugins();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [iframeReady, setIframeReady] = useState(false);

  const plugin = useMemo(
    () => plugins.find((p) => p.code_name === code_name),
    [plugins, code_name]
  );

  const targetUrl = useMemo(() => {
    if (!plugin) {
      return resolvePluginBaseUrl(null, code_name);
    }
    const candidate = plugin.external_url || plugin.homepage_url;
    if (candidate && candidate.includes("github.com")) {
      return resolvePluginBaseUrl(null, code_name);
    }
    return resolvePluginBaseUrl(candidate, code_name);
  }, [plugin, code_name]);

  const isInternalMfe = useMemo(() => isInternalMfeUrl(targetUrl), [targetUrl]);
  const mfeSrc = useMemo(
    () => (isInternalMfe ? buildSeamlessMfeSrc(targetUrl) : targetUrl),
    [isInternalMfe, targetUrl]
  );

  useEffect(() => {
    setIframeReady(false);
  }, [mfeSrc]);

  // Đồng bộ theme Sáng/Tối tức thời từ Core Engine xuống MFE iframe qua postMessage
  useEffect(() => {
    if (!isInternalMfe || typeof document === "undefined") return;

    const syncThemeToIframe = () => {
      const nextTheme = document.documentElement.classList.contains("dark")
        ? "dark"
        : "light";
      try {
        iframeRef.current?.contentWindow?.postMessage(
          { type: "proteus-theme", theme: nextTheme },
          "*"
        );
      } catch {
        // Ignore cross-origin frame errors if any
      }
    };

    const observer = new MutationObserver(syncThemeToIframe);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "data-theme"],
    });

    return () => observer.disconnect();
  }, [isInternalMfe]);

  return (
    <AppShell>
      <div className="w-full h-[calc(100vh-64px)] flex flex-col">
        {isLoading ? (
          <div className="w-full h-full min-h-[420px] flex flex-col items-center justify-center gap-3 bg-paper">
            <div className="w-8 h-8 border-2 border-line-hi border-t-accent rounded-full animate-spin" />
            <p className="text-sm text-muted font-medium">
              Đang tải phân hệ {code_name}…
            </p>
          </div>
        ) : isInternalMfe ? (
          <div className="relative flex-1 w-full h-full min-h-0 bg-paper">
            {!iframeReady && (
              <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-paper">
                <div className="w-8 h-8 border-2 border-line-hi border-t-accent rounded-full animate-spin" />
                <p className="text-sm text-muted font-medium">
                  Đang mở {plugin?.display_name || code_name}…
                </p>
              </div>
            )}
            <iframe
              ref={iframeRef}
              src={mfeSrc}
              title={plugin?.display_name || code_name}
              onLoad={() => setIframeReady(true)}
              className="w-full h-full border-0 bg-paper"
              allow="clipboard-read; clipboard-write; fullscreen"
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-downloads"
            />
          </div>
        ) : (
          <SsoEmbed
            baseUrl={targetUrl}
            title={plugin?.display_name || code_name}
            storageKey={`sso_plugin_${code_name}`}
          />
        )}
      </div>
    </AppShell>
  );
}
