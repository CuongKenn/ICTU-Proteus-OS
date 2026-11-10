// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import { AppShell } from "@/components/AppShell";
import { SsoEmbed } from "@/components/ui/SsoEmbed";

export default function ChatPage() {
  const mattermostUrl = process.env.NEXT_PUBLIC_MATTERMOST_URL || "http://chat.proteus.local";

  return (
    <AppShell>
      <SsoEmbed
        baseUrl={mattermostUrl}
        ssoUrl={`${mattermostUrl}/oauth/gitlab/login`}
        title="Mattermost Chat"
        storageKey="sso_mattermost"
      />
    </AppShell>
  );
}
