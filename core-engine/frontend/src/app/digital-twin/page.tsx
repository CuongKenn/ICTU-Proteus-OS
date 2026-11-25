// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Digital Twin Command Center Page (`/digital-twin` — Issue #872)
// Trực quan hóa Bản sao số Thời gian thực chuẩn ETSI NGSI-LD v1.6, PostGIS & Hasura Live.

import type { Metadata } from "next";
import { AppShell } from "@/components/AppShell";
import { DigitalTwinClient } from "@/components/digital-twin/DigitalTwinClient";

export const metadata: Metadata = {
  title: "Bản sao số (Digital Twin) — Proteus OS",
};

export default function DigitalTwinPage() {
  return (
    <AppShell>
      <DigitalTwinClient />
    </AppShell>
  );
}
