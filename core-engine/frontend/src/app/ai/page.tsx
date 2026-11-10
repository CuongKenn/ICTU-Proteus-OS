// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

import type { Metadata } from "next";
import { AppShell } from "@/components/AppShell";
import { AIChatPanel } from "@/components/AIChatWidget";

export const metadata: Metadata = {
  title: "Proteus AI — Proteus OS",
};

export default function ProteusAIPage() {
  return (
    <AppShell>
      <div className="w-full h-[calc(100vh-80px)] p-4 md:p-6 flex flex-col max-w-5xl mx-auto">
        <AIChatPanel mode="inline" />
      </div>
    </AppShell>
  );
}
