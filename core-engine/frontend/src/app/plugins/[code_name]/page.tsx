// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React, { useMemo } from "react";
import { AppShell } from "@/components/AppShell";
import { SsoEmbed } from "@/components/ui/SsoEmbed";
import { usePlugins } from "@/hooks/usePlugins";

interface PluginPageProps {
  params: {
    code_name: string;
  };
}

export default function PluginPage({ params }: PluginPageProps) {
  const { code_name } = params;
  const { plugins } = usePlugins();

  const plugin = useMemo(
    () => plugins.find((p) => p.code_name === code_name),
    [plugins, code_name]
  );

  const targetUrl = useMemo(() => {
    if (!plugin) return `${process.env.NEXT_PUBLIC_APPSMITH_URL || "http://apps.proteus.local"}/app/${code_name}`;
    return (
      plugin.external_url ||
      plugin.homepage_url ||
      `${process.env.NEXT_PUBLIC_APPSMITH_URL || "http://apps.proteus.local"}/app/${code_name}`
    );
  }, [plugin, code_name]);

  return (
    <AppShell>
      <div className="w-full h-full">
        <SsoEmbed
          baseUrl={targetUrl}
          title={plugin?.display_name || code_name}
          storageKey={`sso_plugin_${code_name}`}
        />
      </div>
    </AppShell>
  );
}
