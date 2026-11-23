# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Generator for Proteus OS Light-themed Clean System Architecture SVG.
Matches the clean, spacious, white-background style of professional engineering diagrams (like image 2).
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

cache_file = os.path.join(SCRIPT_DIR, "icons_cache.json")
with open(cache_file, "r", encoding="utf-8") as f:
    icons = json.load(f)

svg = []

svg.append("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1480 940" width="100%" height="100%">
  <defs>
    <!-- Markers for Arrows -->
    <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#334155" />
    </marker>
    <marker id="arrow-blue" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#0284c7" />
    </marker>
    <marker id="arrow-teal" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#0d9488" />
    </marker>
    <marker id="arrow-emerald" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#16a34a" />
    </marker>
    <marker id="arrow-purple" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#9333ea" />
    </marker>
    <marker id="arrow-rose" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#e11d48" />
    </marker>

    <!-- Subtle Drop Shadow -->
    <filter id="soft-shadow" x="-5%" y="-5%" width="110%" height="110%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#0f172a" flood-opacity="0.08" />
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

  <!-- Outer White Canvas with Crisp Double Border (Clean Professional Style) -->
  <rect width="100%" height="100%" fill="#ffffff" />
  <rect x="18" y="18" width="1444" height="904" fill="none" stroke="#0f172a" stroke-width="2.5" />
  <rect x="25" y="25" width="1430" height="890" fill="none" stroke="#cbd5e1" stroke-width="1" />

  <!-- ==================== HEADER BAR ==================== -->
  <g transform="translate(50, 45)">
    <!-- Docker Containerized Tag -->
    <g transform="translate(0, 0)">
      <use href="#icon-docker" x="0" y="0" width="46" height="46" />
      <text x="56" y="22" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="16" font-weight="800">docker</text>
      <text x="56" y="38" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="600">Compose Stack (45 Services)</text>
    </g>

    <!-- Title & Subtitle -->
    <g transform="translate(360, 5)">
      <text x="0" y="22" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="22" font-weight="900" letter-spacing="1">PROTEUS OS — SYSTEM ARCHITECTURE</text>
      <text x="0" y="40" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12.5" font-weight="500">Universal Work OS • Hexagonal Micro-Kernel • FIWARE NGSI-LD &amp; Hasura Realtime • Multi-Tenant RLS</text>
    </g>

    <!-- Standards Badges -->
    <g transform="translate(1120, 8)">
      <rect x="0" y="0" width="120" height="24" rx="4" fill="#f1f5f9" stroke="#94a3b8" stroke-width="1" />
      <text x="60" y="16" fill="#334155" font-family="monospace" font-size="11" font-weight="bold" text-anchor="middle">AGPL-3.0-or-later</text>
      <rect x="130" y="0" width="120" height="24" rx="4" fill="#e0f2fe" stroke="#38bdf8" stroke-width="1" />
      <text x="190" y="16" fill="#0369a1" font-family="monospace" font-size="11" font-weight="bold" text-anchor="middle">ETSI NGSI-LD</text>
    </g>
  </g>

  <!-- ==================== FLOW CONNECTORS (DASHED ARROWS) ==================== -->
  <g fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
    <!-- Client -> Traefik -->
    <path d="M 190 230 L 255 230" stroke="#334155" stroke-dasharray="5,4" marker-end="url(#arrow)" />

    <!-- Traefik -> Keycloak -->
    <path d="M 335 275 L 335 340" stroke="#0284c7" stroke-dasharray="5,4" marker-end="url(#arrow-blue)" />

    <!-- Traefik -> Next.js Launchpad -->
    <path d="M 255 250 C 220 250, 220 310, 190 310" stroke="#334155" stroke-dasharray="5,4" marker-end="url(#arrow)" />

    <!-- Next.js -> FastAPI Core -->
    <path d="M 190 340 C 230 340, 230 460, 480 460" stroke="#0284c7" stroke-dasharray="5,4" marker-end="url(#arrow-blue)" />

    <!-- Next.js -> Hasura GraphQL (WS Subscriptions) -->
    <path d="M 190 325 C 240 325, 400 230, 880 230" stroke="#e11d48" stroke-dasharray="5,4" marker-end="url(#arrow-rose)" />

    <!-- Traefik -> FastAPI Core -->
    <path d="M 405 230 C 440 230, 440 440, 480 440" stroke="#0d9488" stroke-dasharray="5,4" marker-end="url(#arrow-teal)" />

    <!-- Traefik -> Hasura GraphQL -->
    <path d="M 405 215 C 550 215, 700 215, 880 215" stroke="#0284c7" stroke-dasharray="5,4" marker-end="url(#arrow-blue)" />

    <!-- Keycloak -> Hasura (JWT Claims Verification) -->
    <path d="M 405 380 C 600 380, 750 270, 880 270" stroke="#9333ea" stroke-dasharray="5,4" marker-end="url(#arrow-purple)" />

    <!-- FastAPI -> PostgreSQL -->
    <path d="M 760 450 C 950 450, 1050 200, 1135 200" stroke="#0284c7" stroke-dasharray="5,4" marker-end="url(#arrow-blue)" />

    <!-- Outbox CDC -> Context Sync Worker -->
    <path d="M 1135 220 C 1050 220, 900 310, 850 310" stroke="#d97706" stroke-dasharray="5,4" marker-end="url(#arrow)" />

    <!-- Context Sync Worker -> FIWARE Orion-LD -->
    <path d="M 700 310 C 640 310, 640 270, 640 260" stroke="#0d9488" stroke-dasharray="5,4" marker-end="url(#arrow-teal)" />

    <!-- Context Sync Worker -> Redis Streams -->
    <path d="M 850 330 C 1000 330, 1060 300, 1135 300" stroke="#e11d48" stroke-dasharray="5,4" marker-end="url(#arrow-rose)" />

    <!-- Orion-LD -> Subscriptions Webhook (Anti-Loop) -> FastAPI Core -->
    <path d="M 540 260 C 540 350, 540 380, 540 410" stroke="#16a34a" stroke-dasharray="5,4" marker-end="url(#arrow-emerald)" />

    <!-- Hasura -> PostgreSQL (Direct SQL with RLS) -->
    <path d="M 1060 230 C 1080 230, 1080 180, 1135 180" stroke="#0284c7" stroke-dasharray="5,4" marker-end="url(#arrow-blue)" />

    <!-- FastAPI -> Redis (Event Bus & Cache) -->
    <path d="M 760 480 C 950 480, 1050 320, 1135 320" stroke="#e11d48" stroke-dasharray="5,4" marker-end="url(#arrow-rose)" />

    <!-- Redis Streams -> n8n Workflow -->
    <path d="M 1135 340 C 1060 340, 950 470, 850 470" stroke="#d97706" stroke-dasharray="5,4" marker-end="url(#arrow)" />

    <!-- FastAPI -> Qdrant (Vector Embeddings) -->
    <path d="M 760 510 C 950 510, 1050 420, 1135 420" stroke="#e11d48" stroke-dasharray="5,4" marker-end="url(#arrow-rose)" />

    <!-- FastAPI -> Ollama (Local AI Inference) -->
    <path d="M 760 540 C 950 540, 1050 540, 1135 540" stroke="#334155" stroke-dasharray="5,4" marker-end="url(#arrow)" />

    <!-- Traefik -> Mattermost -->
    <path d="M 335 275 C 335 520, 190 620, 190 640" stroke="#334155" stroke-dasharray="5,4" marker-end="url(#arrow)" />

    <!-- Traefik -> Metabase -->
    <path d="M 350 275 C 350 520, 350 580, 350 640" stroke="#334155" stroke-dasharray="5,4" marker-end="url(#arrow)" />
  </g>

  <!-- ==================== FLOW LABELS ==================== -->
  <g font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" font-weight="700">
    <!-- Client to Traefik -->
    <rect x="200" y="218" width="46" height="18" rx="3" fill="#ffffff" stroke="#cbd5e1" stroke-width="0.8" />
    <text x="223" y="231" text-anchor="middle" fill="#0f172a">HTTPS</text>

    <!-- Traefik to Keycloak -->
    <rect x="340" y="295" width="68" height="18" rx="3" fill="#ffffff" stroke="#bae6fd" stroke-width="0.8" />
    <text x="374" y="308" text-anchor="middle" fill="#0284c7">OIDC Auth</text>

    <!-- Next.js to FastAPI -->
    <rect x="320" y="440" width="70" height="18" rx="3" fill="#ffffff" stroke="#bae6fd" stroke-width="0.8" />
    <text x="355" y="453" text-anchor="middle" fill="#0284c7">REST / BFF</text>

    <!-- Next.js to Hasura -->
    <rect x="420" y="250" width="94" height="18" rx="3" fill="#ffffff" stroke="#fecdd3" stroke-width="0.8" />
    <text x="467" y="263" text-anchor="middle" fill="#e11d48">GraphQL Sub (WS)</text>

    <!-- Keycloak to Hasura -->
    <rect x="620" y="300" width="76" height="18" rx="3" fill="#ffffff" stroke="#e9d5ff" stroke-width="0.8" />
    <text x="658" y="313" text-anchor="middle" fill="#9333ea">JWT Claims</text>

    <!-- Worker to Orion -->
    <rect x="650" y="275" width="56" height="18" rx="3" fill="#ffffff" stroke="#99f6e4" stroke-width="0.8" />
    <text x="678" y="288" text-anchor="middle" fill="#0d9488">NGSI-LD</text>

    <!-- Worker to Redis -->
    <rect x="980" y="300" width="84" height="18" rx="3" fill="#ffffff" stroke="#fecdd3" stroke-width="0.8" />
    <text x="1022" y="313" text-anchor="middle" fill="#e11d48">Redis Streams</text>

    <!-- Anti-Loop Webhook -->
    <rect x="490" y="340" width="100" height="18" rx="3" fill="#ffffff" stroke="#bbf7d0" stroke-width="0.8" />
    <text x="540" y="353" text-anchor="middle" fill="#16a34a">Anti-Loop Webhook</text>

    <!-- FastAPI to DB -->
    <rect x="990" y="415" width="88" height="18" rx="3" fill="#ffffff" stroke="#bae6fd" stroke-width="0.8" />
    <text x="1034" y="428" text-anchor="middle" fill="#0284c7">SQL / Outbox CDC</text>
  </g>

  <!-- ==================== 1. CLIENT BLOCK ==================== -->
  <g transform="translate(50, 120)">
    <!-- Main Pastel Box (Clean Blue) -->
    <rect width="150" height="460" rx="8" fill="#e0f2fe" stroke="#38bdf8" stroke-width="1.5" />
    <text x="75" y="26" fill="#0369a1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="800" text-anchor="middle" letter-spacing="0.5">Client</text>

    <!-- Component 1.1: Web / Mobile Browser -->
    <g transform="translate(15, 45)" filter="url(#soft-shadow)">
      <rect width="120" height="85" rx="6" fill="#ffffff" stroke="#94a3b8" stroke-width="1" />
      <path d="M 46 22 L 74 22 C 76 22 78 24 78 26 L 78 48 C 78 50 76 52 74 52 L 46 52 C 44 52 42 50 42 48 L 42 26 C 42 24 44 22 46 22 Z M 42 29 L 78 29 M 48 26 L 50 26 M 53 26 L 55 26" stroke="#0284c7" stroke-width="1.8" fill="none" />
      <text x="60" y="66" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="700" text-anchor="middle">Web / Mobile</text>
      <text x="60" y="78" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">External Users</text>
    </g>

    <!-- Component 1.2: Next.js Launchpad -->
    <g transform="translate(15, 150)" filter="url(#soft-shadow)">
      <rect width="120" height="95" rx="6" fill="#ffffff" stroke="#0f172a" stroke-width="1.2" />
      <use href="#icon-nextjs" x="46" y="14" width="28" height="28" />
      <text x="60" y="58" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="800" text-anchor="middle">Next.js 14</text>
      <text x="60" y="71" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5" text-anchor="middle">Core Launchpad</text>
      <text x="60" y="83" fill="#0284c7" font-family="monospace" font-size="8.5" text-anchor="middle">Port 3000</text>
    </g>

    <!-- Component 1.3: Plugin Micro-Frontend -->
    <g transform="translate(15, 265)" filter="url(#soft-shadow)">
      <rect width="120" height="85" rx="6" fill="#ffffff" stroke="#6366f1" stroke-width="1" />
      <path d="M 52 24 L 62 24 C 62 21 66 21 66 24 L 72 24 L 72 30 C 75 30 75 34 72 34 L 72 40 L 52 40 Z" fill="#6366f1" />
      <text x="60" y="56" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11.5" font-weight="700" text-anchor="middle">Plugins MFE</text>
      <text x="60" y="69" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">Dynamic UI Loader</text>
      <text x="60" y="80" fill="#6366f1" font-family="monospace" font-size="8" text-anchor="middle">Module Federation</text>
    </g>

    <!-- Security Isolation Tag -->
    <g transform="translate(15, 370)">
      <rect width="120" height="75" rx="4" fill="#f0f9ff" stroke="#bae6fd" stroke-width="1" />
      <text x="60" y="24" fill="#0369a1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="bold" text-anchor="middle">🔒 Zero-Trust UI</text>
      <text x="60" y="42" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="8.5" text-anchor="middle">CORS Strict</text>
      <text x="60" y="56" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="8.5" text-anchor="middle">JWT Context Aware</text>
    </g>
  </g>

  <!-- ==================== 2. INGRESS & IAM BLOCK ==================== -->
  <g transform="translate(245, 120)">
    <!-- Container Box -->
    <rect width="175" height="460" rx="8" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.5" />
    <text x="87" y="26" fill="#1e293b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="800" text-anchor="middle" letter-spacing="0.5">Ingress &amp; IAM</text>

    <!-- Component 2.1: Traefik Proxy -->
    <g transform="translate(15, 45)" filter="url(#soft-shadow)">
      <rect width="145" height="120" rx="6" fill="#ffffff" stroke="#24A1C1" stroke-width="1.5" />
      <use href="#icon-traefik" x="58" y="14" width="30" height="30" />
      <text x="72" y="60" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="800" text-anchor="middle">Traefik Proxy</text>
      <text x="72" y="74" fill="#24A1C1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" font-weight="600" text-anchor="middle">Edge API Gateway</text>
      <line x1="12" y1="84" x2="133" y2="84" stroke="#e2e8f0" stroke-width="1" />
      <text x="72" y="98" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">TLS • Path Routing</text>
      <text x="72" y="110" fill="#0369a1" font-family="monospace" font-size="8.5" text-anchor="middle">Ports: 80 / 443</text>
    </g>

    <!-- Component 2.2: Keycloak IAM -->
    <g transform="translate(15, 200)" filter="url(#soft-shadow)">
      <rect width="145" height="145" rx="6" fill="#ffffff" stroke="#008AD7" stroke-width="1.5" />
      <use href="#icon-keycloak" x="58" y="14" width="30" height="30" />
      <text x="72" y="60" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="800" text-anchor="middle">Keycloak IAM</text>
      <text x="72" y="74" fill="#008AD7" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" font-weight="600" text-anchor="middle">Identity &amp; SSO</text>
      <line x1="12" y1="84" x2="133" y2="84" stroke="#e2e8f0" stroke-width="1" />
      <text x="72" y="98" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">OIDC / OAuth2</text>
      <text x="72" y="112" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">Multi-Tenant RBAC</text>
      <rect x="12" y="122" width="121" height="16" rx="3" fill="#f0f9ff" stroke="#008AD7" stroke-width="0.7" />
      <text x="72" y="133" fill="#0369a1" font-family="monospace" font-size="8" text-anchor="middle">x-hasura-tenant-id</text>
    </g>

    <!-- Security Gateway Tag -->
    <g transform="translate(15, 370)">
      <rect width="145" height="75" rx="4" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1" />
      <text x="72" y="24" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="bold" text-anchor="middle">🛡️ Access Guard</text>
      <text x="72" y="42" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="8.5" text-anchor="middle">Rate Limiting</text>
      <text x="72" y="56" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="8.5" text-anchor="middle">Strict Tenant Claim RLS</text>
    </g>
  </g>

  <!-- ==================== 3. FIWARE CONTEXT & REALTIME PLATFORM ==================== -->
  <g transform="translate(460, 120)">
    <!-- Main Pastel Box (Clean Light-Teal, exactly like Image 2 style) -->
    <rect width="630" height="260" rx="8" fill="#d5ede7" stroke="#0d9488" stroke-width="2" />
    
    <!-- Header with FIWARE Logo -->
    <g transform="translate(20, 16)">
      <use href="#icon-fiware" x="0" y="2" width="110" height="24" />
      <text x="125" y="20" fill="#002E6D" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="900" letter-spacing="0.5">CONTEXT &amp; REALTIME PLATFORM (LAYER 3)</text>
    </g>

    <!-- Component 3.1: FIWARE Orion-LD -->
    <g transform="translate(30, 60)" filter="url(#soft-shadow)">
      <rect width="180" height="175" rx="6" fill="#ffffff" stroke="#002E6D" stroke-width="1.5" />
      <rect x="35" y="16" width="110" height="26" rx="4" fill="#f8fafc" stroke="#e2e8f0" stroke-width="0.8" />
      <use href="#icon-fiware" x="40" y="19" width="100" height="20" />
      <text x="90" y="60" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="800" text-anchor="middle">Orion-LD Broker</text>
      <text x="90" y="74" fill="#0284c7" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" font-weight="600" text-anchor="middle">NGSI-LD Context Broker</text>
      <line x1="12" y1="84" x2="168" y2="84" stroke="#e2e8f0" stroke-width="1" />
      <text x="90" y="100" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">• Digital Twin Entity States</text>
      <text x="90" y="116" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">• Geo-Spatial &amp; Temporal</text>
      <text x="90" y="132" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">• Entity Subscriptions</text>
      <rect x="18" y="146" width="144" height="18" rx="3" fill="#f0f9ff" stroke="#0284c7" stroke-width="0.8" />
      <text x="90" y="159" fill="#0369a1" font-family="monospace" font-size="9" text-anchor="middle">Port 1026</text>
    </g>

    <!-- Component 3.2: Context Sync Worker (Anti-Loop) -->
    <g transform="translate(225, 60)" filter="url(#soft-shadow)">
      <rect width="180" height="175" rx="6" fill="#ffffff" stroke="#d97706" stroke-width="1.5" />
      <circle cx="90" cy="30" r="16" fill="#fef3c7" stroke="#d97706" stroke-width="1.2" />
      <path d="M 83 30 C 83 26 86 23 90 23 C 94 23 97 26 97 30 L 99 30 M 98 37 C 95 40 85 40 83 33" stroke="#d97706" stroke-width="2" stroke-linecap="round" fill="none" />
      <text x="90" y="60" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12.5" font-weight="800" text-anchor="middle">Context Sync Worker</text>
      <text x="90" y="74" fill="#d97706" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" font-weight="600" text-anchor="middle">CDC &amp; Anti-Loop Engine</text>
      <line x1="12" y1="84" x2="168" y2="84" stroke="#e2e8f0" stroke-width="1" />
      <text x="90" y="100" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">• Polling context.outbox</text>
      <text x="90" y="116" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">• NGSI-LD Payload Transform</text>
      <text x="90" y="132" fill="#16a34a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" font-weight="bold" text-anchor="middle">🛡️ Anti-Sync Loop Guard</text>
      <rect x="18" y="146" width="144" height="18" rx="3" fill="#fef3c7" stroke="#d97706" stroke-width="0.8" />
      <text x="90" y="159" fill="#92400e" font-family="monospace" font-size="8.5" text-anchor="middle">DLQ Max 5 Retries</text>
    </g>

    <!-- Component 3.3: Hasura GraphQL Engine -->
    <g transform="translate(420, 60)" filter="url(#soft-shadow)">
      <rect width="180" height="175" rx="6" fill="#ffffff" stroke="#1EB4D4" stroke-width="1.5" />
      <use href="#icon-hasura" x="65" y="14" width="24" height="24" />
      <use href="#icon-graphql" x="95" y="14" width="24" height="24" />
      <text x="90" y="60" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="800" text-anchor="middle">Hasura GraphQL</text>
      <text x="90" y="74" fill="#0891b2" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" font-weight="600" text-anchor="middle">Instant Realtime Engine</text>
      <line x1="12" y1="84" x2="168" y2="84" stroke="#e2e8f0" stroke-width="1" />
      <text x="90" y="100" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">• Live Queries (WebSocket)</text>
      <text x="90" y="116" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">• Keycloak JWT Claim RLS</text>
      <text x="90" y="132" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">• Sanitized Data Views</text>
      <rect x="18" y="146" width="144" height="18" rx="3" fill="#ecfeff" stroke="#0891b2" stroke-width="0.8" />
      <text x="90" y="159" fill="#0e7490" font-family="monospace" font-size="9" text-anchor="middle">Port 8080</text>
    </g>
  </g>

  <!-- ==================== 4. CORE ENGINE & WORKFLOWS BLOCK ==================== -->
  <g transform="translate(460, 400)">
    <!-- Container Box -->
    <rect width="630" height="180" rx="8" fill="#f8fafc" stroke="#0ea5e9" stroke-width="1.5" />
    <text x="315" y="24" fill="#0284c7" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="800" text-anchor="middle" letter-spacing="0.5">Core Engine &amp; Automation (Innovation Layer)</text>

    <!-- Component 4.1: FastAPI Core Engine -->
    <g transform="translate(25, 40)" filter="url(#soft-shadow)">
      <rect width="280" height="120" rx="6" fill="#ffffff" stroke="#009688" stroke-width="1.8" />
      <use href="#icon-fastapi" x="20" y="16" width="28" height="28" />
      <text x="58" y="32" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="800">FastAPI Core Engine</text>
      <text x="58" y="46" fill="#009688" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">Hexagonal Micro-Kernel (Python 3.12)</text>
      <line x1="15" y1="56" x2="265" y2="56" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="74" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Domain Ports &amp; Adapters • Plugin Lifecycle</text>
      <text x="15" y="90" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Transactional Outbox (context.outbox ACID)</text>
      <rect x="15" y="98" width="250" height="16" rx="3" fill="#f0fdfa" stroke="#009688" stroke-width="0.8" />
      <text x="140" y="110" fill="#0f766e" font-family="monospace" font-size="8.5" text-anchor="middle">Port 8000 • Uvicorn ASGI</text>
    </g>

    <!-- Component 4.2: n8n Workflow Automation -->
    <g transform="translate(325, 40)" filter="url(#soft-shadow)">
      <rect width="280" height="120" rx="6" fill="#ffffff" stroke="#EA4B71" stroke-width="1.5" />
      <use href="#icon-n8n" x="20" y="16" width="28" height="28" />
      <text x="58" y="32" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="800">n8n Workflow Automation</text>
      <text x="58" y="46" fill="#e11d48" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">Low-Code Event Workflows</text>
      <line x1="15" y1="56" x2="265" y2="56" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="74" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Event-Driven Triggers on Redis Streams</text>
      <text x="15" y="90" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Automated Cross-System Integration</text>
      <rect x="15" y="98" width="250" height="16" rx="3" fill="#fff1f2" stroke="#e11d48" stroke-width="0.8" />
      <text x="140" y="110" fill="#be123c" font-family="monospace" font-size="8.5" text-anchor="middle">Port 5678 • Webhooks Engine</text>
    </g>
  </g>

  <!-- ==================== 5. STORAGE, EVENT BUS & AI ==================== -->
  <g transform="translate(1120, 120)">
    <!-- Container Box -->
    <rect width="310" height="460" rx="8" fill="#f8fafc" stroke="#64748b" stroke-width="1.5" />
    <text x="155" y="26" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="800" text-anchor="middle" letter-spacing="0.5">Storage, Event Bus &amp; AI</text>

    <!-- Component 5.1: PostgreSQL + PostGIS -->
    <g transform="translate(15, 45)" filter="url(#soft-shadow)">
      <rect width="280" height="90" rx="6" fill="#ffffff" stroke="#4169E1" stroke-width="1.5" />
      <use href="#icon-postgresql" x="18" y="16" width="28" height="28" />
      <text x="56" y="32" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800">PostgreSQL 16 + PostGIS</text>
      <text x="56" y="46" fill="#2563eb" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" font-weight="600">Core Relational &amp; Spatial DB</text>
      <line x1="15" y1="54" x2="265" y2="54" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="70" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9">• Multi-Tenant RLS Schemas • Outbox Table</text>
      <rect x="15" y="74" width="250" height="12" rx="2" fill="#eff6ff" />
      <text x="140" y="83" fill="#1d4ed8" font-family="monospace" font-size="8" text-anchor="middle">Port 5432 • ACID Consistency</text>
    </g>

    <!-- Component 5.2: Redis 7 Stack -->
    <g transform="translate(15, 145)" filter="url(#soft-shadow)">
      <rect width="280" height="90" rx="6" fill="#ffffff" stroke="#FF4438" stroke-width="1.5" />
      <use href="#icon-redis" x="18" y="16" width="28" height="28" />
      <text x="56" y="32" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800">Redis 7 Stack</text>
      <text x="56" y="46" fill="#dc2626" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" font-weight="600">Distributed Event Bus &amp; Cache</text>
      <line x1="15" y1="54" x2="265" y2="54" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="70" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9">• Redis Streams (maxlen 10k) • In-memory Cache</text>
      <rect x="15" y="74" width="250" height="12" rx="2" fill="#fef2f2" />
      <text x="140" y="83" fill="#b91c1c" font-family="monospace" font-size="8" text-anchor="middle">Port 6379 • Pub/Sub Stream Engine</text>
    </g>

    <!-- Component 5.3: Qdrant Vector DB -->
    <g transform="translate(15, 245)" filter="url(#soft-shadow)">
      <rect width="280" height="90" rx="6" fill="#ffffff" stroke="#DC2626" stroke-width="1.5" />
      <use href="#icon-qdrant" x="18" y="16" width="28" height="28" />
      <text x="56" y="32" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800">Qdrant Vector DB</text>
      <text x="56" y="46" fill="#b91c1c" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" font-weight="600">Vector Search Engine</text>
      <line x1="15" y1="54" x2="265" y2="54" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="70" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9">• Multi-Tenant Vector Collections • RAG Pipeline</text>
      <rect x="15" y="74" width="250" height="12" rx="2" fill="#fef2f2" />
      <text x="140" y="83" fill="#991b1b" font-family="monospace" font-size="8" text-anchor="middle">Port 6333 • Semantic Similarity</text>
    </g>

    <!-- Component 5.4: Ollama Local LLM -->
    <g transform="translate(15, 345)" filter="url(#soft-shadow)">
      <rect width="280" height="100" rx="6" fill="#ffffff" stroke="#0f172a" stroke-width="1.5" />
      <use href="#icon-ollama" x="18" y="16" width="28" height="28" />
      <text x="56" y="32" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800">Ollama / Local LLM</text>
      <text x="56" y="46" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" font-weight="600">On-Premise Private AI</text>
      <line x1="15" y1="54" x2="265" y2="54" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="70" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9">• Llama-3, Qwen Offline Inference</text>
      <text x="15" y="84" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9">• 100% Data Privacy (Zero Cloud Leakage)</text>
      <rect x="15" y="88" width="250" height="10" rx="2" fill="#f8fafc" />
    </g>
  </g>

  <!-- ==================== 6. COLLABORATION & ANALYTICS BLOCK ==================== -->
  <g transform="translate(50, 600)">
    <!-- Container Box -->
    <rect width="370" height="165" rx="8" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.5" />
    <text x="185" y="24" fill="#1e293b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12.5" font-weight="800" text-anchor="middle" letter-spacing="0.5">Collaboration &amp; Analytics</text>

    <!-- Component 6.1: Mattermost -->
    <g transform="translate(15, 40)" filter="url(#soft-shadow)">
      <rect width="160" height="110" rx="6" fill="#ffffff" stroke="#0058CC" stroke-width="1.3" />
      <use href="#icon-mattermost" x="66" y="14" width="28" height="28" />
      <text x="80" y="58" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12.5" font-weight="800" text-anchor="middle">Mattermost</text>
      <text x="80" y="72" fill="#0058CC" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5" text-anchor="middle">Team ChatOps &amp; Bot</text>
      <line x1="12" y1="80" x2="148" y2="80" stroke="#e2e8f0" stroke-width="0.8" />
      <text x="80" y="96" fill="#0369a1" font-family="monospace" font-size="8.5" text-anchor="middle">Port 8065</text>
    </g>

    <!-- Component 6.2: Metabase -->
    <g transform="translate(195, 40)" filter="url(#soft-shadow)">
      <rect width="160" height="110" rx="6" fill="#ffffff" stroke="#509EE3" stroke-width="1.3" />
      <path d="M 68 38 L 68 28 M 74 38 L 74 20 M 80 38 L 80 24 M 86 38 L 86 16 M 66 40 L 88 40" stroke="#509EE3" stroke-width="2" stroke-linecap="round" fill="none" />
      <text x="80" y="58" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12.5" font-weight="800" text-anchor="middle">Metabase BI</text>
      <text x="80" y="72" fill="#0284c7" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5" text-anchor="middle">Embedded Dashboards</text>
      <line x1="12" y1="80" x2="148" y2="80" stroke="#e2e8f0" stroke-width="0.8" />
      <text x="80" y="96" fill="#0369a1" font-family="monospace" font-size="8.5" text-anchor="middle">Port 3001</text>
    </g>
  </g>

  <!-- ==================== 7. OBSERVABILITY & MONITORING INFRASTRUCTURE ==================== -->
  <g transform="translate(460, 600)">
    <!-- Container Box -->
    <rect width="970" height="165" rx="8" fill="#f1f5f9" stroke="#94a3b8" stroke-width="1.5" />
    <text x="485" y="24" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12.5" font-weight="800" text-anchor="middle" letter-spacing="0.5">Observability, Metrics &amp; Incident Drill Stack</text>

    <!-- Component 7.1: Prometheus -->
    <g transform="translate(20, 40)" filter="url(#soft-shadow)">
      <rect width="290" height="110" rx="6" fill="#ffffff" stroke="#E6522C" stroke-width="1.4" />
      <use href="#icon-prometheus" x="20" y="16" width="28" height="28" />
      <text x="58" y="32" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="800">Prometheus Telemetry</text>
      <text x="58" y="46" fill="#c2410c" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" font-weight="600">Time-Series Metrics Scraper</text>
      <line x1="15" y1="56" x2="275" y2="56" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="74" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9">• Scrapes FastAPI, Orion, Hasura &amp; Redis</text>
      <text x="15" y="88" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9">• Outbox Lag Tracking &amp; DLQ Counters</text>
      <rect x="15" y="94" width="260" height="12" rx="2" fill="#fff7ed" />
      <text x="145" y="103" fill="#9a3412" font-family="monospace" font-size="8" text-anchor="middle">Port 9090</text>
    </g>

    <!-- Component 7.2: Grafana -->
    <g transform="translate(340, 40)" filter="url(#soft-shadow)">
      <rect width="290" height="110" rx="6" fill="#ffffff" stroke="#F46800" stroke-width="1.4" />
      <use href="#icon-grafana" x="20" y="16" width="28" height="28" />
      <text x="58" y="32" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="800">Grafana Dashboards</text>
      <text x="58" y="46" fill="#ea580c" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" font-weight="600">Realtime Operational Telemetry</text>
      <line x1="15" y1="56" x2="275" y2="56" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="74" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9">• Layer 3 Broker Dashboard Included</text>
      <text x="15" y="88" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9">• Automated Incident Drill Alerts</text>
      <rect x="15" y="94" width="260" height="12" rx="2" fill="#fff7ed" />
      <text x="145" y="103" fill="#c2410c" font-family="monospace" font-size="8" text-anchor="middle">Port 3002</text>
    </g>

    <!-- Component 7.3: Grafana Loki -->
    <g transform="translate(660, 40)" filter="url(#soft-shadow)">
      <rect width="290" height="110" rx="6" fill="#ffffff" stroke="#7c3aed" stroke-width="1.4" />
      <circle cx="34" cy="30" r="14" fill="#f3e8ff" stroke="#7c3aed" stroke-width="1" />
      <path d="M 28 24 L 40 24 M 28 30 L 40 30 M 28 36 L 35 36" stroke="#7c3aed" stroke-width="2" stroke-linecap="round" fill="none" />
      <text x="58" y="32" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="800">Grafana Loki</text>
      <text x="58" y="46" fill="#7c3aed" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" font-weight="600">Centralized Log Aggregation</text>
      <line x1="15" y1="56" x2="275" y2="56" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="74" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9">• Centralized Logs Across 45 Containers</text>
      <text x="15" y="88" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9">• Promtail Log Shipping &amp; Trace ID Correlation</text>
      <rect x="15" y="94" width="260" height="12" rx="2" fill="#faf5ff" />
      <text x="145" y="103" fill="#6b21a8" font-family="monospace" font-size="8" text-anchor="middle">Port 3100</text>
    </g>
  </g>

  <!-- ==================== FOOTER CAPTION ==================== -->
  <g transform="translate(50, 785)">
    <rect width="1380" height="100" rx="6" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1" />
    <text x="25" y="30" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12.5" font-weight="bold">📌 Ghi chú Kiến trúc &amp; Luồng Giao dịch Ngữ cảnh (Layer 3 Context CDC Flow):</text>
    <text x="25" y="52" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11">1. <tspan font-weight="bold">Transactional Outbox Pattern:</tspan> Khi nghiệp vụ ghi vào PostgreSQL, sự kiện được ghi cùng giao dịch ACID vào <tspan font-family="monospace">context.outbox</tspan>, loại bỏ nguy cơ mất mát dữ liệu.</text>
    <text x="25" y="70" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11">2. <tspan font-weight="bold">Cơ chế Chống vòng lặp (Anti-Sync Loop):</tspan> Worker đẩy sang Orion-LD &amp; Redis Streams. Khi Orion gửi webhook ngược về Backend, hệ thống cập nhật <tspan font-family="monospace">entity_state</tspan> mà không ghi lại outbox.</text>
    <text x="25" y="88" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11">3. <tspan font-weight="bold">Realtime Subscriptions:</tspan> Client nhận cập nhật tức thời qua Hasura GraphQL WebSocket với phân quyền bảo mật lọc dòng/cột theo Keycloak JWT Claims.</text>
  </g>
</svg>""")

full_svg = "".join(svg)

output_path = os.path.join(REPO_ROOT, "docs", "images", "architecture_flow.svg")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(full_svg)

print(f"Successfully generated light-theme architecture SVG: {output_path} ({len(full_svg)} bytes)")
