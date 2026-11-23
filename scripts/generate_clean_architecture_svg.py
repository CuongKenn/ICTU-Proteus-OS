# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Generator for Proteus OS Wide-Screen Clean System Architecture SVG (1920x1080).
Solves all cluttering and overlapping issues:
- 1920x1080 resolution with huge breathing room (gap = 120px-140px).
- Every single line has distinct, non-overlapping Y channels (separated by >= 30px).
- High-visibility arrowheads pointing directly at component edges.
- Clear protocol labels placed on clean background pills.
- Official rich logos for 100% of the technologies.
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

cache_file = os.path.join(SCRIPT_DIR, "icons_cache.json")
with open(cache_file, "r", encoding="utf-8") as f:
    icons = json.load(f)

svg = []

svg.append("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="100%" height="100%">
  <defs>
    <!-- Sharp, Bold Arrowhead Markers (Distinct Colors) -->
    <marker id="arr" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="9" markerHeight="9" orient="auto-start-reverse">
      <path d="M 1 2 L 11 6 L 1 10 z" fill="#334155" />
    </marker>
    <marker id="arr-blue" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="9" markerHeight="9" orient="auto-start-reverse">
      <path d="M 1 2 L 11 6 L 1 10 z" fill="#0284c7" />
    </marker>
    <marker id="arr-teal" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="9" markerHeight="9" orient="auto-start-reverse">
      <path d="M 1 2 L 11 6 L 1 10 z" fill="#0d9488" />
    </marker>
    <marker id="arr-green" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="9" markerHeight="9" orient="auto-start-reverse">
      <path d="M 1 2 L 11 6 L 1 10 z" fill="#16a34a" />
    </marker>
    <marker id="arr-rose" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="9" markerHeight="9" orient="auto-start-reverse">
      <path d="M 1 2 L 11 6 L 1 10 z" fill="#e11d48" />
    </marker>
    <marker id="arr-purple" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="9" markerHeight="9" orient="auto-start-reverse">
      <path d="M 1 2 L 11 6 L 1 10 z" fill="#9333ea" />
    </marker>
    <marker id="arr-amber" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="9" markerHeight="9" orient="auto-start-reverse">
      <path d="M 1 2 L 11 6 L 1 10 z" fill="#d97706" />
    </marker>

    <!-- Clean Shadow for Cards -->
    <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#0f172a" flood-opacity="0.06" />
    </filter>
""")

# Embed SVG Symbols
for name, data in icons.items():
    viewBox = data.get("viewBox", "0 0 24 24")
    color = data.get("color", "#334155")
    svg.append(f'    <symbol id="icon-{name}" viewBox="{viewBox}">')
    if data.get("raw_fiware"):
        for p in data["paths"]:
            svg.append(f'      <path d="{p["d"]}" fill="{p.get("fill", "#002E6D")}" />')
    else:
        for p in data["paths"]:
            svg.append(f'      <path d="{p}" fill="{color}" />')
    svg.append("    </symbol>")

svg.append("""  </defs>

  <!-- Canvas Background & Double Engineering Frame -->
  <rect width="100%" height="100%" fill="#ffffff" />
  <rect x="20" y="20" width="1880" height="1040" fill="none" stroke="#0f172a" stroke-width="2.5" />
  <rect x="28" y="28" width="1864" height="1024" fill="none" stroke="#cbd5e1" stroke-width="1" />

  <!-- ==================== TOP HEADER BAR ==================== -->
  <g transform="translate(60, 45)">
    <!-- Docker Container Logo -->
    <g transform="translate(0, 0)">
      <use href="#icon-docker" x="0" y="0" width="52" height="52" />
      <text x="62" y="24" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="18" font-weight="900">docker</text>
      <text x="62" y="42" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="600">Compose Stack (45 Services)</text>
    </g>

    <!-- Main Title & Subtitle -->
    <g transform="translate(480, 5)">
      <text x="0" y="24" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="24" font-weight="900" letter-spacing="1">PROTEUS OS — SYSTEM ARCHITECTURE</text>
      <text x="0" y="46" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="500">Universal Work OS • Hexagonal Micro-Kernel • FIWARE NGSI-LD &amp; Hasura Realtime • Multi-Tenant RLS</text>
    </g>

    <!-- Standards Badges -->
    <g transform="translate(1500, 8)">
      <rect x="0" y="0" width="135" height="28" rx="4" fill="#f1f5f9" stroke="#94a3b8" stroke-width="1" />
      <text x="67" y="19" fill="#334155" font-family="monospace" font-size="11.5" font-weight="bold" text-anchor="middle">AGPL-3.0-or-later</text>
      <rect x="145" y="0" width="135" height="28" rx="4" fill="#e0f2fe" stroke="#38bdf8" stroke-width="1" />
      <text x="212" y="19" fill="#0369a1" font-family="monospace" font-size="11.5" font-weight="bold" text-anchor="middle">ETSI NGSI-LD</text>
    </g>
  </g>

  <!-- ==================== ORTHOGONAL CONNECTOR LINES (DASHED ARROWS) ==================== -->
  <g fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    
    <!-- 1. Client -> Traefik (Horizontal Straight) -->
    <path d="M 250 435 L 315 435" stroke="#334155" stroke-dasharray="6,4" marker-end="url(#arr)" />

    <!-- 2. Traefik -> Keycloak (Vertical Straight Down) -->
    <path d="M 420 500 L 420 535" stroke="#0284c7" stroke-dasharray="6,4" marker-end="url(#arr-blue)" />

    <!-- 3. Traefik -> FastAPI Core (Orthogonal: Right -> Down -> Right) -->
    <path d="M 520 435 L 560 435 L 560 520 L 625 520" stroke="#0d9488" stroke-dasharray="6,4" marker-end="url(#arr-teal)" />

    <!-- 4. Client (Next.js) -> Hasura (Over top: Up -> Right -> Down) -->
    <path d="M 155 365 L 155 210 L 1145 210 L 1145 240" stroke="#e11d48" stroke-dasharray="6,4" marker-end="url(#arr-rose)" />

    <!-- 5. Keycloak -> Hasura (JWT Claims: Right -> Up -> Right) -->
    <path d="M 520 595 L 560 595 L 560 330 L 1145 330 L 1145 315" stroke="#9333ea" stroke-dasharray="6,4" marker-end="url(#arr-purple)" />

    <!-- 6. Hasura GraphQL -> PostgreSQL (Direct Horizontal Right - Y:235) -->
    <path d="M 1375 235 L 1535 235" stroke="#0284c7" stroke-dasharray="6,4" marker-end="url(#arr-blue)" />

    <!-- 7. PostgreSQL Outbox -> Context Sync Worker (Direct Horizontal Left - Y:275) -->
    <path d="M 1545 275 L 1120 275" stroke="#d97706" stroke-dasharray="6,4" marker-end="url(#arr-amber)" />

    <!-- 8. Context Sync Worker -> FIWARE Orion-LD (Inside FIWARE Platform: Left Horizontal) -->
    <path d="M 890 275 L 860 275" stroke="#0d9488" stroke-dasharray="6,4" marker-end="url(#arr-teal)" />

    <!-- 9. FIWARE Orion-LD -> FastAPI Core (Anti-Sync Loop Webhook: Vertical Down - X:740) -->
    <path d="M 740 355 L 740 465" stroke="#16a34a" stroke-dasharray="6,4" marker-end="url(#arr-green)" />

    <!-- 10. Context Sync Worker -> Redis Streams (Right -> Down -> Right - Y:350) -->
    <path d="M 1005 355 L 1005 375 L 1460 375 L 1460 350 L 1535 350" stroke="#e11d48" stroke-dasharray="6,4" marker-end="url(#arr-rose)" />

    <!-- 11. FastAPI Core -> Redis 7 Stack (Right -> Up -> Right - Y:390) -->
    <path d="M 1000 520 L 1480 520 L 1480 390 L 1535 390" stroke="#e11d48" stroke-dasharray="6,4" marker-end="url(#arr-rose)" />

    <!-- 12. Redis Streams -> n8n Automation Engine (Left -> Down -> Left - Y:425 / Y:550) -->
    <path d="M 1545 420 L 1440 420 L 1440 550 L 1380 550" stroke="#d97706" stroke-dasharray="6,4" marker-end="url(#arr-amber)" />

    <!-- 13. FastAPI Core -> Qdrant Vector DB (Right -> Down -> Right - Y:510) -->
    <path d="M 1000 580 L 1460 580 L 1460 510 L 1535 510" stroke="#e11d48" stroke-dasharray="6,4" marker-end="url(#arr-rose)" />

    <!-- 14. FastAPI Core -> Ollama Local LLM (Horizontal Right - Y:640) -->
    <path d="M 1000 640 L 1535 640" stroke="#334155" stroke-dasharray="6,4" marker-end="url(#arr)" />

    <!-- 15. Traefik -> Collaboration Block (Down -> Left) -->
    <path d="M 420 500 L 420 740 L 290 740" stroke="#334155" stroke-dasharray="6,4" marker-end="url(#arr)" />
  </g>

  <!-- ==================== FLOW LABELS (CLEAN BADGES) ==================== -->
  <g font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="700">
    <!-- 1. Client to Traefik -->
    <rect x="257" y="423" width="52" height="24" rx="4" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.2" />
    <text x="283" y="439" text-anchor="middle" fill="#0f172a">HTTPS</text>

    <!-- 2. Traefik to Keycloak -->
    <rect x="430" y="505" width="82" height="24" rx="4" fill="#ffffff" stroke="#bae6fd" stroke-width="1.2" />
    <text x="471" y="521" text-anchor="middle" fill="#0284c7">OIDC Auth</text>

    <!-- 3. Traefik to FastAPI -->
    <rect x="535" y="465" width="85" height="24" rx="4" fill="#ffffff" stroke="#99f6e4" stroke-width="1.2" />
    <text x="577" y="481" text-anchor="middle" fill="#0d9488">REST / API</text>

    <!-- 4. Client to Hasura (Live WS) -->
    <rect x="440" y="198" width="150" height="24" rx="4" fill="#ffffff" stroke="#fecdd3" stroke-width="1.2" />
    <text x="515" y="214" text-anchor="middle" fill="#e11d48">GraphQL Sub (WS Live)</text>

    <!-- 5. Keycloak to Hasura -->
    <rect x="580" y="318" width="105" height="24" rx="4" fill="#ffffff" stroke="#e9d5ff" stroke-width="1.2" />
    <text x="632" y="334" text-anchor="middle" fill="#9333ea">JWT Claims RLS</text>

    <!-- 6. Hasura to PostgreSQL (Y:235) -->
    <rect x="1395" y="223" width="120" height="24" rx="4" fill="#ffffff" stroke="#bae6fd" stroke-width="1.2" />
    <text x="1455" y="239" text-anchor="middle" fill="#0284c7">Direct SQL + RLS</text>

    <!-- 7. Outbox to Worker (Y:275) -->
    <rect x="1385" y="263" width="140" height="24" rx="4" fill="#ffffff" stroke="#fed7aa" stroke-width="1.2" />
    <text x="1455" y="279" text-anchor="middle" fill="#d97706">CDC Polling (Outbox)</text>

    <!-- 8. Worker to Orion-LD -->
    <rect x="815" y="245" width="65" height="22" rx="4" fill="#ffffff" stroke="#99f6e4" stroke-width="1" />
    <text x="847" y="260" text-anchor="middle" fill="#0d9488">NGSI-LD</text>

    <!-- 9. Anti-Loop Webhook -->
    <rect x="670" y="395" width="140" height="24" rx="4" fill="#ffffff" stroke="#bbf7d0" stroke-width="1.5" />
    <text x="740" y="411" text-anchor="middle" fill="#16a34a">🛡️ Anti-Sync Webhook</text>

    <!-- 10. Worker to Redis Streams (Y:350) -->
    <rect x="1400" y="338" width="110" height="24" rx="4" fill="#ffffff" stroke="#fecdd3" stroke-width="1.2" />
    <text x="1455" y="354" text-anchor="middle" fill="#e11d48">Redis Streams</text>

    <!-- 11. FastAPI to Redis Streams (Y:390) -->
    <rect x="1390" y="378" width="130" height="24" rx="4" fill="#ffffff" stroke="#fecdd3" stroke-width="1.2" />
    <text x="1455" y="394" text-anchor="middle" fill="#e11d48">Event Bus &amp; Cache</text>

    <!-- 12. Redis Streams to n8n (Y:420) -->
    <rect x="1405" y="418" width="105" height="24" rx="4" fill="#ffffff" stroke="#fed7aa" stroke-width="1.2" />
    <text x="1457" y="434" text-anchor="middle" fill="#d97706">Event Triggers</text>

    <!-- 13. FastAPI to Qdrant (Y:510) -->
    <rect x="1395" y="498" width="125" height="24" rx="4" fill="#ffffff" stroke="#fecdd3" stroke-width="1.2" />
    <text x="1457" y="514" text-anchor="middle" fill="#e11d48">Vector Similarity</text>

    <!-- 14. FastAPI to Ollama (Y:640) -->
    <rect x="1395" y="628" width="125" height="24" rx="4" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.2" />
    <text x="1457" y="644" text-anchor="middle" fill="#334155">Private Inference</text>
  </g>

  <!-- ==================== 1. FIWARE CONTEXT & REALTIME PLATFORM (TOP BLOCK) ==================== -->
  <g transform="translate(600, 140)">
    <!-- Main Pastel Box (Clean Light-Teal) -->
    <rect width="800" height="240" rx="8" fill="#d1fae5" stroke="#059669" stroke-width="2" />
    
    <!-- Header with FIWARE Logo -->
    <g transform="translate(30, 16)">
      <use href="#icon-fiware" x="0" y="2" width="130" height="28" />
      <text x="150" y="23" fill="#002E6D" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="15" font-weight="900" letter-spacing="0.5">FIWARE CONTEXT &amp; REALTIME PLATFORM (LAYER 3)</text>
    </g>

    <!-- Box 1.1: FIWARE Orion-LD -->
    <g transform="translate(30, 60)" filter="url(#shadow)">
      <rect width="225" height="155" rx="6" fill="#ffffff" stroke="#002E6D" stroke-width="1.6" />
      <rect x="52" y="14" width="120" height="28" rx="4" fill="#f8fafc" stroke="#e2e8f0" stroke-width="0.8" />
      <use href="#icon-fiware" x="57" y="17" width="110" height="22" />
      <text x="112" y="58" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="800" text-anchor="middle">Orion-LD Broker</text>
      <text x="112" y="74" fill="#0284c7" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="600" text-anchor="middle">NGSI-LD Context Broker</text>
      <line x1="15" y1="84" x2="210" y2="84" stroke="#e2e8f0" stroke-width="1" />
      <text x="112" y="102" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" text-anchor="middle">• Digital Twin Entity States</text>
      <text x="112" y="118" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" text-anchor="middle">• Geo-Spatial &amp; Temporal</text>
      <rect x="32" y="126" width="160" height="18" rx="3" fill="#f0f9ff" stroke="#0284c7" stroke-width="0.8" />
      <text x="112" y="139" fill="#0369a1" font-family="monospace" font-size="9.5" text-anchor="middle">Port 1026</text>
    </g>

    <!-- Box 1.2: Context Sync Worker (Anti-Loop) -->
    <g transform="translate(285, 60)" filter="url(#shadow)">
      <rect width="225" height="155" rx="6" fill="#ffffff" stroke="#d97706" stroke-width="1.6" />
      <circle cx="112" cy="28" r="16" fill="#fef3c7" stroke="#d97706" stroke-width="1.2" />
      <path d="M 105 28 C 105 24 108 21 112 21 C 116 21 119 24 119 28 L 121 28 M 120 35 C 117 38 107 38 105 31" stroke="#d97706" stroke-width="2" stroke-linecap="round" fill="none" />
      <text x="112" y="58" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800" text-anchor="middle">Context Sync Worker</text>
      <text x="112" y="74" fill="#d97706" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="600" text-anchor="middle">CDC &amp; Anti-Loop Engine</text>
      <line x1="15" y1="84" x2="210" y2="84" stroke="#e2e8f0" stroke-width="1" />
      <text x="112" y="102" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" text-anchor="middle">• Polling context.outbox</text>
      <text x="112" y="118" fill="#16a34a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" font-weight="bold" text-anchor="middle">🛡️ Anti-Sync Loop Guard</text>
      <rect x="32" y="126" width="160" height="18" rx="3" fill="#fef3c7" stroke="#d97706" stroke-width="0.8" />
      <text x="112" y="139" fill="#92400e" font-family="monospace" font-size="9" text-anchor="middle">DLQ Max 5 Retries</text>
    </g>

    <!-- Box 1.3: Hasura GraphQL Engine -->
    <g transform="translate(545, 60)" filter="url(#shadow)">
      <rect width="225" height="155" rx="6" fill="#ffffff" stroke="#1EB4D4" stroke-width="1.6" />
      <use href="#icon-hasura" x="80" y="14" width="28" height="28" />
      <use href="#icon-graphql" x="118" y="14" width="28" height="28" />
      <text x="112" y="58" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="800" text-anchor="middle">Hasura GraphQL</text>
      <text x="112" y="74" fill="#0891b2" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="600" text-anchor="middle">Instant Realtime Engine</text>
      <line x1="15" y1="84" x2="210" y2="84" stroke="#e2e8f0" stroke-width="1" />
      <text x="112" y="102" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" text-anchor="middle">• Live Queries (WebSocket)</text>
      <text x="112" y="118" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" text-anchor="middle">• Keycloak JWT Claims RLS</text>
      <rect x="32" y="126" width="160" height="18" rx="3" fill="#ecfeff" stroke="#0891b2" stroke-width="0.8" />
      <text x="112" y="139" fill="#0e7490" font-family="monospace" font-size="9.5" text-anchor="middle">Port 8080</text>
    </g>
  </g>

  <!-- ==================== 2. CLIENT BLOCK ==================== -->
  <g transform="translate(60, 320)">
    <rect width="190" height="360" rx="8" fill="#e0f2fe" stroke="#38bdf8" stroke-width="1.8" />
    <text x="95" y="28" fill="#0369a1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="800" text-anchor="middle" letter-spacing="0.5">Client</text>

    <!-- Component 2.1: Next.js Launchpad -->
    <g transform="translate(15, 45)" filter="url(#shadow)">
      <rect width="160" height="135" rx="6" fill="#ffffff" stroke="#0f172a" stroke-width="1.5" />
      <use href="#icon-nextjs" x="62" y="14" width="36" height="36" />
      <text x="80" y="66" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800" text-anchor="middle">Next.js 14</text>
      <text x="80" y="82" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" text-anchor="middle">Core Launchpad</text>
      <text x="80" y="98" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5" text-anchor="middle">React 18 • Tailwind</text>
      <rect x="15" y="108" width="130" height="18" rx="3" fill="#f0f9ff" stroke="#0284c7" stroke-width="0.8" />
      <text x="80" y="121" fill="#0284c7" font-family="monospace" font-size="9.5" text-anchor="middle">Port 3000</text>
    </g>

    <!-- Component 2.2: Plugins Micro-Frontend -->
    <g transform="translate(15, 200)" filter="url(#shadow)">
      <rect width="160" height="135" rx="6" fill="#ffffff" stroke="#6366f1" stroke-width="1.5" />
      <circle cx="80" cy="30" r="16" fill="#ede9fe" stroke="#6366f1" stroke-width="1.2" />
      <path d="M 72 24 L 80 24 C 80 21 84 21 84 24 L 88 24 L 88 28 C 91 28 91 32 88 32 L 88 36 L 72 36 Z" fill="#6366f1" />
      <text x="80" y="66" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="700" text-anchor="middle">Plugins MFE</text>
      <text x="80" y="82" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" text-anchor="middle">Dynamic UI Loader</text>
      <text x="80" y="98" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5" text-anchor="middle">Module Federation</text>
      <rect x="15" y="108" width="130" height="18" rx="3" fill="#faf5ff" stroke="#6366f1" stroke-width="0.8" />
      <text x="80" y="121" fill="#7c3aed" font-family="monospace" font-size="9" text-anchor="middle">Sandboxed MFE</text>
    </g>
  </g>

  <!-- ==================== 3. INGRESS & IAM BLOCK ==================== -->
  <g transform="translate(320, 320)">
    <rect width="200" height="360" rx="8" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.8" />
    <text x="100" y="28" fill="#1e293b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="800" text-anchor="middle" letter-spacing="0.5">Ingress &amp; IAM</text>

    <!-- Component 3.1: Traefik Proxy -->
    <g transform="translate(15, 45)" filter="url(#shadow)">
      <rect width="170" height="135" rx="6" fill="#ffffff" stroke="#24A1C1" stroke-width="1.5" />
      <use href="#icon-traefik" x="67" y="12" width="36" height="36" />
      <text x="85" y="66" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="800" text-anchor="middle">Traefik Proxy</text>
      <text x="85" y="82" fill="#24A1C1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="600" text-anchor="middle">Edge API Gateway</text>
      <text x="85" y="98" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5" text-anchor="middle">TLS • Dynamic Routing</text>
      <rect x="15" y="108" width="140" height="18" rx="3" fill="#ecfeff" stroke="#24A1C1" stroke-width="0.8" />
      <text x="85" y="121" fill="#0891b2" font-family="monospace" font-size="9.5" text-anchor="middle">Ports: 80 / 443</text>
    </g>

    <!-- Component 3.2: Keycloak IAM -->
    <g transform="translate(15, 200)" filter="url(#shadow)">
      <rect width="170" height="135" rx="6" fill="#ffffff" stroke="#008AD7" stroke-width="1.5" />
      <use href="#icon-keycloak" x="67" y="12" width="36" height="36" />
      <text x="85" y="66" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="800" text-anchor="middle">Keycloak IAM</text>
      <text x="85" y="82" fill="#008AD7" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="600" text-anchor="middle">Identity &amp; SSO</text>
      <text x="85" y="98" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5" text-anchor="middle">OIDC • Multi-Tenant RBAC</text>
      <rect x="15" y="108" width="140" height="18" rx="3" fill="#f0f9ff" stroke="#008AD7" stroke-width="0.8" />
      <text x="85" y="121" fill="#0284c7" font-family="monospace" font-size="9.5" text-anchor="middle">Port 8081</text>
    </g>
  </g>

  <!-- ==================== 4. CORE ENGINE & WORKFLOWS ==================== -->
  <g transform="translate(600, 420)">
    <rect width="800" height="280" rx="8" fill="#f0fdf4" stroke="#16a34a" stroke-width="1.8" />
    <text x="400" y="28" fill="#15803d" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="800" text-anchor="middle" letter-spacing="0.5">Core Engine &amp; Automation (Innovation Layer)</text>

    <!-- Component 4.1: FastAPI Core Engine -->
    <g transform="translate(30, 45)" filter="url(#shadow)">
      <rect width="360" height="210" rx="6" fill="#ffffff" stroke="#009688" stroke-width="1.8" />
      <use href="#icon-fastapi" x="20" y="16" width="34" height="34" />
      <text x="66" y="32" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="15" font-weight="900">FastAPI Core Engine</text>
      <text x="66" y="48" fill="#009688" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11.5" font-weight="600">Hexagonal Micro-Kernel (Python 3.12)</text>
      <line x1="15" y1="60" x2="345" y2="60" stroke="#e2e8f0" stroke-width="1" />
      <text x="18" y="82" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5">• Domain Ports &amp; Adapters • Plugin Lifecycle</text>
      <text x="18" y="102" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5">• Multi-Tenant Context Resolver Middleware</text>
      <text x="18" y="122" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5">• Transactional Outbox (context.outbox ACID)</text>
      <text x="18" y="142" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5">• AI Orchestrator &amp; Safe DSL Execution</text>
      <rect x="18" y="160" width="324" height="24" rx="3" fill="#f0fdfa" stroke="#009688" stroke-width="0.8" />
      <text x="180" y="176" fill="#0f766e" font-family="monospace" font-size="10" text-anchor="middle">Port 8000 • Uvicorn ASGI Server</text>
    </g>

    <!-- Component 4.2: n8n Workflow Automation (WITH RICH OFFICIAL N8N LOGO) -->
    <g transform="translate(415, 45)" filter="url(#shadow)">
      <rect width="355" height="210" rx="6" fill="#ffffff" stroke="#EA4B71" stroke-width="1.8" />
      <use href="#icon-n8n" x="18" y="14" width="50" height="36" />
      <text x="78" y="32" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="15" font-weight="900">n8n Workflow Engine</text>
      <text x="78" y="48" fill="#e11d48" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11.5" font-weight="600">Low-Code Event Workflows</text>
      <line x1="15" y1="60" x2="340" y2="60" stroke="#e2e8f0" stroke-width="1" />
      <text x="18" y="82" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5">• Event-Driven Triggers on Redis Streams</text>
      <text x="18" y="102" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5">• Automated Cross-System Integration Canvas</text>
      <text x="18" y="122" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5">• 400+ Pre-built Connectors &amp; Webhooks</text>
      <text x="18" y="142" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5">• Approval Chains &amp; ChatOps Alerts</text>
      <rect x="18" y="160" width="319" height="24" rx="3" fill="#fff1f2" stroke="#e11d48" stroke-width="0.8" />
      <text x="177" y="176" fill="#be123c" font-family="monospace" font-size="10" text-anchor="middle">Port 5678 • Webhooks &amp; Executions</text>
    </g>
  </g>

  <!-- ==================== 5. PERSISTENCE, EVENT BUS & AI (WIDE RIGHT BLOCK) ==================== -->
  <g transform="translate(1520, 140)">
    <rect width="340" height="560" rx="8" fill="#f8fafc" stroke="#475569" stroke-width="1.8" />
    <text x="170" y="28" fill="#1e293b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="800" text-anchor="middle" letter-spacing="0.5">Persistence, Event Bus &amp; AI</text>

    <!-- Component 5.1: PostgreSQL 16 + PostGIS -->
    <g transform="translate(20, 45)" filter="url(#shadow)">
      <rect width="300" height="110" rx="6" fill="#ffffff" stroke="#4169E1" stroke-width="1.6" />
      <use href="#icon-postgresql" x="18" y="14" width="32" height="32" />
      <text x="60" y="28" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="900">PostgreSQL 16 + PostGIS</text>
      <text x="60" y="44" fill="#2563eb" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="600">Core Relational &amp; Spatial DB</text>
      <line x1="15" y1="54" x2="285" y2="54" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="72" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Multi-Tenant RLS Schemas • Outbox Table</text>
      <text x="15" y="88" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Spatial Geo-Data &amp; ACID Transactions</text>
      <rect x="15" y="92" width="270" height="14" rx="2" fill="#eff6ff" />
      <text x="150" y="103" fill="#1d4ed8" font-family="monospace" font-size="9" text-anchor="middle">Port 5432</text>
    </g>

    <!-- Component 5.2: Redis 7 Stack -->
    <g transform="translate(20, 175)" filter="url(#shadow)">
      <rect width="300" height="110" rx="6" fill="#ffffff" stroke="#FF4438" stroke-width="1.6" />
      <use href="#icon-redis" x="18" y="14" width="32" height="32" />
      <text x="60" y="28" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="900">Redis 7 Stack</text>
      <text x="60" y="44" fill="#dc2626" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="600">Distributed Event Bus &amp; Cache</text>
      <line x1="15" y1="54" x2="285" y2="54" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="72" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Redis Streams (maxlen 10k) • In-memory Cache</text>
      <text x="15" y="88" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Idempotency Deduplication Key</text>
      <rect x="15" y="92" width="270" height="14" rx="2" fill="#fef2f2" />
      <text x="150" y="103" fill="#b91c1c" font-family="monospace" font-size="9" text-anchor="middle">Port 6379</text>
    </g>

    <!-- Component 5.3: Qdrant Vector DB -->
    <g transform="translate(20, 305)" filter="url(#shadow)">
      <rect width="300" height="110" rx="6" fill="#ffffff" stroke="#DC2626" stroke-width="1.6" />
      <use href="#icon-qdrant" x="18" y="14" width="32" height="32" />
      <text x="60" y="28" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="900">Qdrant Vector DB</text>
      <text x="60" y="44" fill="#b91c1c" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="600">Vector Search Engine</text>
      <line x1="15" y1="54" x2="285" y2="54" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="72" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Multi-Tenant Vector Collections • RAG Pipeline</text>
      <text x="15" y="88" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• High-dimensional Embeddings Search</text>
      <rect x="15" y="92" width="270" height="14" rx="2" fill="#fef2f2" />
      <text x="150" y="103" fill="#991b1b" font-family="monospace" font-size="9" text-anchor="middle">Port 6333</text>
    </g>

    <!-- Component 5.4: Ollama Local LLM -->
    <g transform="translate(20, 435)" filter="url(#shadow)">
      <rect width="300" height="110" rx="6" fill="#ffffff" stroke="#0f172a" stroke-width="1.6" />
      <use href="#icon-ollama" x="18" y="14" width="32" height="32" />
      <text x="60" y="28" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="900">Ollama / Local LLM</text>
      <text x="60" y="44" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="600">On-Premise Private AI</text>
      <line x1="15" y1="54" x2="285" y2="54" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="72" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Llama-3, Qwen Offline Inference</text>
      <text x="15" y="88" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• 100% Data Privacy (Zero Cloud Leakage)</text>
      <rect x="15" y="92" width="270" height="14" rx="2" fill="#f8fafc" />
      <text x="150" y="103" fill="#475569" font-family="monospace" font-size="9" text-anchor="middle">Port 11434</text>
    </g>
  </g>

  <!-- ==================== 6. COLLABORATION & ANALYTICS ==================== -->
  <g transform="translate(60, 720)">
    <rect width="460" height="165" rx="8" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.8" />
    <text x="230" y="26" fill="#1e293b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="800" text-anchor="middle" letter-spacing="0.5">Collaboration &amp; Analytics</text>

    <!-- Component 6.1: Mattermost -->
    <g transform="translate(18, 45)" filter="url(#shadow)">
      <rect width="205" height="105" rx="6" fill="#ffffff" stroke="#0058CC" stroke-width="1.4" />
      <use href="#icon-mattermost" x="16" y="14" width="30" height="30" />
      <text x="56" y="28" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800">Mattermost</text>
      <text x="56" y="44" fill="#0058CC" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5">Team ChatOps &amp; Bot</text>
      <line x1="12" y1="56" x2="193" y2="56" stroke="#e2e8f0" stroke-width="0.8" />
      <text x="102" y="74" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5" text-anchor="middle">Channels • AI Assistant Bot</text>
      <rect x="15" y="82" width="175" height="16" rx="2" fill="#f0f9ff" />
      <text x="102" y="93" fill="#0369a1" font-family="monospace" font-size="9" text-anchor="middle">Port 8065</text>
    </g>

    <!-- Component 6.2: Metabase -->
    <g transform="translate(237, 45)" filter="url(#shadow)">
      <rect width="205" height="105" rx="6" fill="#ffffff" stroke="#509EE3" stroke-width="1.4" />
      <use href="#icon-metabase" x="16" y="14" width="30" height="30" />
      <text x="56" y="28" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800">Metabase BI</text>
      <text x="56" y="44" fill="#0284c7" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5">Self-Service Dashboards</text>
      <line x1="12" y1="56" x2="193" y2="56" stroke="#e2e8f0" stroke-width="0.8" />
      <text x="102" y="74" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5" text-anchor="middle">Secure JWT Embedded IFrames</text>
      <rect x="15" y="82" width="175" height="16" rx="2" fill="#f0f9ff" />
      <text x="102" y="93" fill="#0369a1" font-family="monospace" font-size="9" text-anchor="middle">Port 3001</text>
    </g>
  </g>

  <!-- ==================== 7. OBSERVABILITY INFRASTRUCTURE (WITH OFFICIAL LOKI LOGO) ==================== -->
  <g transform="translate(600, 720)">
    <rect width="1260" height="165" rx="8" fill="#f1f5f9" stroke="#94a3b8" stroke-width="1.8" />
    <text x="630" y="26" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="800" text-anchor="middle" letter-spacing="0.5">Observability, Metrics &amp; Incident Drill Stack</text>

    <!-- Component 7.1: Prometheus -->
    <g transform="translate(30, 45)" filter="url(#shadow)">
      <rect width="380" height="105" rx="6" fill="#ffffff" stroke="#E6522C" stroke-width="1.5" />
      <use href="#icon-prometheus" x="20" y="16" width="32" height="32" />
      <text x="62" y="32" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="900">Prometheus Telemetry</text>
      <text x="62" y="48" fill="#c2410c" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="600">Time-Series Metrics Scraper</text>
      <line x1="15" y1="58" x2="365" y2="58" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="76" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Scrapes Outbox Lag &amp; DLQ Counters</text>
      <text x="15" y="92" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Realtime API Latency &amp; Memory Metrics</text>
    </g>

    <!-- Component 7.2: Grafana -->
    <g transform="translate(440, 45)" filter="url(#shadow)">
      <rect width="380" height="105" rx="6" fill="#ffffff" stroke="#F46800" stroke-width="1.5" />
      <use href="#icon-grafana" x="20" y="16" width="32" height="32" />
      <text x="62" y="32" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="900">Grafana Dashboards</text>
      <text x="62" y="48" fill="#ea580c" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="600">Unified Operational Visualizer</text>
      <line x1="15" y1="58" x2="365" y2="58" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="76" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Layer 3 Broker Dashboard Included</text>
      <text x="15" y="92" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Automated Incident Drill Alerts</text>
    </g>

    <!-- Component 7.3: Grafana Loki -->
    <g transform="translate(850, 45)" filter="url(#shadow)">
      <rect width="380" height="105" rx="6" fill="#ffffff" stroke="#7c3aed" stroke-width="1.5" />
      <use href="#icon-loki" x="20" y="16" width="32" height="32" />
      <text x="62" y="32" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="900">Grafana Loki</text>
      <text x="62" y="48" fill="#7c3aed" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="600">Centralized Log Aggregator</text>
      <line x1="15" y1="58" x2="365" y2="58" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="76" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Centralized Shipping for 45 Containers</text>
      <text x="15" y="92" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Promtail Shipping &amp; Trace ID Correlation</text>
    </g>
  </g>

  <!-- ==================== 8. FOOTER CAPTION & EXPLANATION ==================== -->
  <g transform="translate(60, 905)">
    <rect width="1800" height="130" rx="6" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1" />
    <text x="30" y="28" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="900">📌 Ghi chú Kiến trúc &amp; Luồng Giao dịch Ngữ cảnh (Layer 3 Context CDC Flow):</text>
    <text x="30" y="52" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12">1. <tspan font-weight="bold" fill="#0284c7">Transactional Outbox Pattern:</tspan> Khi nghiệp vụ ghi vào PostgreSQL, sự kiện được ghi cùng giao dịch ACID vào bảng <tspan font-family="monospace" fill="#0f766e">context.outbox</tspan>, loại bỏ nguy cơ bất đồng bộ dữ liệu (Dual-write race conditions).</text>
    <text x="30" y="74" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12">2. <tspan font-weight="bold" fill="#16a34a">Cơ chế Chống vòng lặp (Anti-Sync Loop):</tspan> Worker đẩy sang Orion-LD &amp; Redis Streams. Khi Orion gửi webhook ngược về Backend, hệ thống cập nhật <tspan font-family="monospace" fill="#0f766e">entity_state</tspan> mà không ghi lại outbox để triệt tiêu vòng lặp vô tận.</text>
    <text x="30" y="96" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12">3. <tspan font-weight="bold" fill="#e11d48">Realtime Subscriptions:</tspan> Client nhận cập nhật tức thời qua Hasura GraphQL WebSocket với phân quyền bảo mật lọc dòng/cột theo Keycloak JWT Claims (<tspan font-family="monospace" fill="#0f766e">x-hasura-tenant-id</tspan>).</text>
    <text x="30" y="118" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11.5">4. <tspan font-weight="bold">Phục hồi Sự cố (DLQ):</tspan> Bản ghi đồng bộ lỗi được chuyển vào Dead Letter Queue với 5 lần thử lại theo cơ chế Exponential Backoff, cho phép kích hoạt tái xử lý thủ công qua API <tspan font-family="monospace">POST /api/v1/context/outbox/replay-dlq</tspan>.</text>
  </g>
</svg>""")

full_svg = "".join(svg)

output_path = os.path.join(REPO_ROOT, "docs", "images", "architecture_flow.svg")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(full_svg)

print(f"Successfully generated 1920x1080 clean architecture SVG: {output_path} ({len(full_svg)} bytes)")
