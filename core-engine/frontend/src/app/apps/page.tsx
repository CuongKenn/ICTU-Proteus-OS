// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import { AppShell } from "@/components/AppShell";
import { SsoEmbed } from "@/components/ui/SsoEmbed";
import { LayoutGrid } from "lucide-react";

export default function AppsPage() {
  const appsmithUrl = process.env.NEXT_PUBLIC_APPSMITH_URL || "http://apps.proteus.local";

  return (
    <AppShell>
      {appsmithUrl ? (
        <SsoEmbed
          baseUrl={appsmithUrl}
          title="Apps (Low-code)"
          storageKey="sso_appsmith"
        />
      ) : (
        <div className="flex flex-col items-center justify-center h-full gap-4 text-text-secondary">
          <LayoutGrid className="w-16 h-16 opacity-30" />
          <p className="mt-4 text-text-secondary">
            Tích hợp Appsmith chưa được cấu hình. Vui lòng liên hệ Admin để thiết lập.
          </p>
        </div>
      )}
    </AppShell>
  );
}
