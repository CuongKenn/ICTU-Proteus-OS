// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

import type { Metadata } from "next";
import { AppShell } from "@/components/AppShell";
import { AIWorkspaceClient } from "@/components/ai/AIWorkspaceClient";

export const metadata: Metadata = {
  title: "Proteus AI — Trung tâm Điều hành Glass-box AI",
};

export default function ProteusAIPage() {
  return (
    <AppShell>
      <AIWorkspaceClient />
    </AppShell>
  );
}
