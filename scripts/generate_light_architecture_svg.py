# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Generator for Proteus OS Light-themed Clean System Architecture SVG.
Matches the clean, spacious, white-background style of professional engineering diagrams (like image 2).
Features:
- Wide canvas (1680x1060) with plenty of breathing room (no crowding).
- Official vector SVG icons for all technologies (including rich n8n, metabase, loki).
- Clear, orthogonal (straight 90-degree) connector lines with directional arrowheads.
- Descriptive protocol badges placed neatly on lines.
- Dedicated FIWARE Context & Realtime Platform pastel zone (matching image 2 style).
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

cache_file = os.path.join(SCRIPT_DIR, "icons_cache.json")
with open(cache_file, "r", encoding="utf-8") as f:
    icons = json.load(f)

svg = []

svg.append("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1680 1060" width="100%" height="100%">
  <defs>
    <!-- Arrowhead Markers -->
    <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#334155" />
    </marker>
    <marker id="arr-blue" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#0284c7" />
    </marker>
    <marker id="arr-teal" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#0d9488" />
    </marker>
    <marker id="arr-green" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#16a34a" />
    </marker>
    <marker id="arr-rose" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#e11d48" />
    </marker>
    <marker id="arr-purple" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#9333ea" />
    </marker>
    <marker id="arr-amber" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#d97706" />
    </marker>

    <!-- Subtle Drop Shadow for Cards -->
    <filter id="card-shadow" x="-6%" y="-6%" width="112%" height="112%">
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

  <!-- Outer White Canvas with Double Border -->
  <rect width="100%" height="100%" fill="#ffffff" />
  <rect x="18" y="18" width="1644" height="1024" fill="none" stroke="#0f172a" stroke-width="2.5" />
  <rect x="25" y="25" width="1630" height="1010" fill="none" stroke="#cbd5e1" stroke-width="1" />

  <!-- ==================== HEADER BAR ==================== -->
  <g transform="translate(55, 45)">
    <!-- Docker Containerized Tag -->
    <g transform="translate(0, 0)">
      <use href="#icon-docker" x="0" y="0" width="48" height="48" />
      <text x="58" y="22" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="16" font-weight="900">docker</text>
      <text x="58" y="38" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11.5" font-weight="600">Compose Stack (45 Services)</text>
    </g>

    <!-- Title & Subtitle -->
    <g transform="translate(430, 5)">
      <text x="0" y="22" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="22" font-weight="900" letter-spacing="1">PROTEUS OS — SYSTEM ARCHITECTURE</text>
      <text x="0" y="42" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="500">Universal Work OS • Hexagonal Micro-Kernel • FIWARE NGSI-LD &amp; Hasura Realtime • Multi-Tenant RLS</text>
    </g>

    <!-- Badges -->
    <g transform="translate(1310, 8)">
      <rect x="0" y="0" width="120" height="26" rx="4" fill="#f1f5f9" stroke="#94a3b8" stroke-width="1" />
      <text x="60" y="17" fill="#334155" font-family="monospace" font-size="11" font-weight="bold" text-anchor="middle">AGPL-3.0-or-later</text>
      <rect x="130" y="0" width="120" height="26" rx="4" fill="#e0f2fe" stroke="#38bdf8" stroke-width="1" />
      <text x="190" y="17" fill="#0369a1" font-family="monospace" font-size="11" font-weight="bold" text-anchor="middle">ETSI NGSI-LD</text>
    </g>
  </g>

  <!-- ==================== ORTHOGONAL CONNECTOR LINES (DASHED ARROWS) ==================== -->
  <g fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    
    <!-- 1. Client (Next.js) -> Traefik (Horizontal) -->
    <path d="M 230 435 L 290 435" stroke="#334155" stroke-dasharray="6,4" marker-end="url(#arr)" />

    <!-- 2. Traefik -> Keycloak (Vertical) -->
    <path d="M 370 495 L 370 525" stroke="#0284c7" stroke-dasharray="6,4" marker-end="url(#arr-blue)" />

    <!-- 3. Traefik -> FastAPI Core (Orthogonal: Right -> Down -> Right) -->
    <path d="M 450 435 L 500 435 L 500 495 L 565 495" stroke="#0d9488" stroke-dasharray="6,4" marker-end="url(#arr-teal)" />

    <!-- 4. Client (Next.js) -> Hasura GraphQL (Orthogonal Up & Over: Up -> Right -> Down) -->
    <path d="M 145 365 L 145 235 L 1045 235 L 1045 255" stroke="#e11d48" stroke-dasharray="6,4" marker-end="url(#arr-rose)" />

    <!-- 5. Keycloak -> Hasura (JWT Claims Sync: Right -> Up -> Right) -->
    <path d="M 450 585 L 500 585 L 500 340 L 1025 340 L 1045 340 L 1045 320" stroke="#9333ea" stroke-dasharray="6,4" marker-end="url(#arr-purple)" />

    <!-- 6. FastAPI Core -> PostgreSQL (Right -> Up -> Right) -->
    <path d="M 890 500 L 1285 500 L 1285 220 L 1335 220" stroke="#0284c7" stroke-dasharray="6,4" marker-end="url(#arr-blue)" />

    <!-- 7. PostgreSQL (Outbox) -> Context Sync Worker (Left direct) -->
    <path d="M 1335 245 L 1015 245" stroke="#d97706" stroke-dasharray="6,4" marker-end="url(#arr-amber)" />

    <!-- 8. Context Sync Worker -> FIWARE Orion-LD (Left horizontal inside platform) -->
    <path d="M 805 245 L 775 245" stroke="#0d9488" stroke-dasharray="6,4" marker-end="url(#arr-teal)" />

    <!-- 9. Context Sync Worker -> Redis Streams (Right -> Down -> Right) -->
    <path d="M 1015 280 L 1295 280 L 1295 340 L 1335 340" stroke="#e11d48" stroke-dasharray="6,4" marker-end="url(#arr-rose)" />

    <!-- 10. FIWARE Orion-LD -> FastAPI Core (Anti-Loop Webhook: Vertical Down) -->
    <path d="M 670 335 L 670 440" stroke="#16a34a" stroke-dasharray="6,4" marker-end="url(#arr-green)" />

    <!-- 11. Hasura GraphQL -> PostgreSQL (Right horizontal direct) -->
    <path d="M 1250 220 L 1335 220" stroke="#0284c7" stroke-dasharray="6,4" marker-end="url(#arr-blue)" />

    <!-- 12. FastAPI Core -> Redis 7 Stack (Right -> Up -> Right) -->
    <path d="M 890 535 L 1280 535 L 1280 360 L 1335 360" stroke="#e11d48" stroke-dasharray="6,4" marker-end="url(#arr-rose)" />

    <!-- 13. Redis Streams -> n8n Automation (Right -> Down -> Left) -->
    <path d="M 1335 380 L 1285 380 L 1285 520 L 1235 520" stroke="#d97706" stroke-dasharray="6,4" marker-end="url(#arr-amber)" />

    <!-- 14. FastAPI Core -> Qdrant Vector DB (Right -> Up -> Right) -->
    <path d="M 890 575 L 1290 575 L 1290 460 L 1335 460" stroke="#e11d48" stroke-dasharray="6,4" marker-end="url(#arr-rose)" />

    <!-- 15. FastAPI Core -> Ollama Local LLM (Right -> Horizontal) -->
    <path d="M 890 605 L 1335 605" stroke="#334155" stroke-dasharray="6,4" marker-end="url(#arr)" />

    <!-- 16. Traefik -> Collaboration Block (Mattermost & Metabase: Down -> Left) -->
    <path d="M 370 495 L 370 705 L 260 705" stroke="#334155" stroke-dasharray="6,4" marker-end="url(#arr)" />
  </g>

  <!-- ==================== FLOW LABELS (CLEAN BADGES) ==================== -->
  <g font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="700">
    <!-- Client to Traefik -->
    <rect x="235" y="423" width="50" height="22" rx="4" fill="#ffffff" stroke="#cbd5e1" stroke-width="1" />
    <text x="260" y="438" text-anchor="middle" fill="#0f172a">HTTPS</text>

    <!-- Traefik to Keycloak -->
    <rect x="380" y="500" width="76" height="22" rx="4" fill="#ffffff" stroke="#bae6fd" stroke-width="1" />
    <text x="418" y="515" text-anchor="middle" fill="#0284c7">OIDC Auth</text>

    <!-- Traefik to FastAPI -->
    <rect x="475" y="455" width="78" height="22" rx="4" fill="#ffffff" stroke="#99f6e4" stroke-width="1" />
    <text x="514" y="470" text-anchor="middle" fill="#0d9488">REST / API</text>

    <!-- Client to Hasura (Live Subscriptions) -->
    <rect x="420" y="223" width="135" height="22" rx="4" fill="#ffffff" stroke="#fecdd3" stroke-width="1" />
    <text x="487" y="238" text-anchor="middle" fill="#e11d48">GraphQL Sub (WS Live)</text>

    <!-- Keycloak to Hasura -->
    <rect x="530" y="328" width="90" height="22" rx="4" fill="#ffffff" stroke="#e9d5ff" stroke-width="1" />
    <text x="575" y="343" text-anchor="middle" fill="#9333ea">JWT Claims RLS</text>

    <!-- Worker to Orion-LD -->
    <rect x="765" y="215" width="74" height="22" rx="4" fill="#ffffff" stroke="#99f6e4" stroke-width="1" />
    <text x="802" y="230" text-anchor="middle" fill="#0d9488">NGSI-LD</text>

    <!-- Worker to Redis Streams -->
    <rect x="1055" y="268" width="105" height="22" rx="4" fill="#ffffff" stroke="#fecdd3" stroke-width="1" />
    <text x="1107" y="283" text-anchor="middle" fill="#e11d48">Redis Streams</text>

    <!-- Anti-Loop Webhook -->
    <rect x="680" y="375" width="130" height="22" rx="4" fill="#ffffff" stroke="#bbf7d0" stroke-width="1.2" />
    <text x="745" y="390" text-anchor="middle" fill="#16a34a">🛡️ Anti-Sync Webhook</text>

    <!-- Outbox CDC Polling -->
    <rect x="1055" y="233" width="105" height="22" rx="4" fill="#ffffff" stroke="#fed7aa" stroke-width="1" />
    <text x="1107" y="248" text-anchor="middle" fill="#d97706">CDC Polling (Outbox)</text>

    <!-- FastAPI to PostgreSQL -->
    <rect x="940" y="488" width="130" height="22" rx="4" fill="#ffffff" stroke="#bae6fd" stroke-width="1" />
    <text x="1005" y="503" text-anchor="middle" fill="#0284c7">SQL / Outbox ACID Tx</text>

    <!-- Redis Streams to n8n -->
    <rect x="1195" y="415" width="100" height="22" rx="4" fill="#ffffff" stroke="#fed7aa" stroke-width="1" />
    <text x="1245" y="430" text-anchor="middle" fill="#d97706">Event Triggers</text>

    <!-- FastAPI to Qdrant -->
    <rect x="940" y="563" width="115" height="22" rx="4" fill="#ffffff" stroke="#fecdd3" stroke-width="1" />
    <text x="997" y="578" text-anchor="middle" fill="#e11d48">Vector Similarity</text>

    <!-- FastAPI to Ollama -->
    <rect x="940" y="593" width="115" height="22" rx="4" fill="#ffffff" stroke="#cbd5e1" stroke-width="1" />
    <text x="997" y="608" text-anchor="middle" fill="#334155">Private Inference</text>
  </g>

  <!-- ==================== 1. FIWARE CONTEXT & REALTIME PLATFORM (TOP PASTEL BLOCK) ==================== -->
  <g transform="translate(540, 130)">
    <!-- Main Pastel Box (Clean Light-Teal, exactly like Image 2 style) -->
    <rect width="730" height="235" rx="8" fill="#d4ede6" stroke="#0d9488" stroke-width="2" />
    
    <!-- Header with FIWARE Logo -->
    <g transform="translate(25, 16)">
      <use href="#icon-fiware" x="0" y="2" width="125" height="26" />
      <text x="140" y="22" fill="#002E6D" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14.5" font-weight="900" letter-spacing="0.5">FIWARE CONTEXT &amp; REALTIME PLATFORM (LAYER 3)</text>
    </g>

    <!-- Box 1.1: FIWARE Orion-LD -->
    <g transform="translate(25, 58)" filter="url(#card-shadow)">
      <rect width="210" height="155" rx="6" fill="#ffffff" stroke="#002E6D" stroke-width="1.6" />
      <rect x="45" y="14" width="120" height="28" rx="4" fill="#f8fafc" stroke="#e2e8f0" stroke-width="0.8" />
      <use href="#icon-fiware" x="50" y="17" width="110" height="22" />
      <text x="105" y="58" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800" text-anchor="middle">Orion-LD Broker</text>
      <text x="105" y="73" fill="#0284c7" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600" text-anchor="middle">NGSI-LD Context Broker</text>
      <line x1="15" y1="83" x2="195" y2="83" stroke="#e2e8f0" stroke-width="1" />
      <text x="105" y="99" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5" text-anchor="middle">• Digital Twin Entity States</text>
      <text x="105" y="114" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5" text-anchor="middle">• Geo-Spatial &amp; Temporal</text>
      <rect x="25" y="125" width="160" height="18" rx="3" fill="#f0f9ff" stroke="#0284c7" stroke-width="0.8" />
      <text x="105" y="138" fill="#0369a1" font-family="monospace" font-size="9.5" text-anchor="middle">Port 1026</text>
    </g>

    <!-- Box 1.2: Context Sync Worker (Anti-Loop) -->
    <g transform="translate(260, 58)" filter="url(#card-shadow)">
      <rect width="210" height="155" rx="6" fill="#ffffff" stroke="#d97706" stroke-width="1.6" />
      <circle cx="105" cy="28" r="16" fill="#fef3c7" stroke="#d97706" stroke-width="1.2" />
      <path d="M 98 28 C 98 24 101 21 105 21 C 109 21 112 24 112 28 L 114 28 M 113 35 C 110 38 100 38 98 31" stroke="#d97706" stroke-width="2" stroke-linecap="round" fill="none" />
      <text x="105" y="58" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="800" text-anchor="middle">Context Sync Worker</text>
      <text x="105" y="73" fill="#d97706" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600" text-anchor="middle">CDC &amp; Anti-Loop Engine</text>
      <line x1="15" y1="83" x2="195" y2="83" stroke="#e2e8f0" stroke-width="1" />
      <text x="105" y="99" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5" text-anchor="middle">• Polling context.outbox</text>
      <text x="105" y="114" fill="#16a34a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5" font-weight="bold" text-anchor="middle">🛡️ Anti-Sync Loop Guard</text>
      <rect x="25" y="125" width="160" height="18" rx="3" fill="#fef3c7" stroke="#d97706" stroke-width="0.8" />
      <text x="105" y="138" fill="#92400e" font-family="monospace" font-size="9" text-anchor="middle">DLQ Max 5 Retries</text>
    </g>

    <!-- Box 1.3: Hasura GraphQL Engine -->
    <g transform="translate(495, 58)" filter="url(#card-shadow)">
      <rect width="210" height="155" rx="6" fill="#ffffff" stroke="#1EB4D4" stroke-width="1.6" />
      <use href="#icon-hasura" x="75" y="14" width="26" height="26" />
      <use href="#icon-graphql" x="110" y="14" width="26" height="26" />
      <text x="105" y="58" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800" text-anchor="middle">Hasura GraphQL</text>
      <text x="105" y="73" fill="#0891b2" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600" text-anchor="middle">Instant Realtime Engine</text>
      <line x1="15" y1="83" x2="195" y2="83" stroke="#e2e8f0" stroke-width="1" />
      <text x="105" y="99" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5" text-anchor="middle">• Live Queries (WebSocket)</text>
      <text x="105" y="114" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5" text-anchor="middle">• Keycloak JWT Claims RLS</text>
      <rect x="25" y="125" width="160" height="18" rx="3" fill="#ecfeff" stroke="#0891b2" stroke-width="0.8" />
      <text x="105" y="138" fill="#0e7490" font-family="monospace" font-size="9.5" text-anchor="middle">Port 8080</text>
    </g>
  </g>

  <!-- ==================== 2. CLIENT BLOCK ==================== -->
  <g transform="translate(50, 320)">
    <rect width="180" height="340" rx="8" fill="#e0f2fe" stroke="#38bdf8" stroke-width="1.8" />
    <text x="90" y="28" fill="#0369a1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800" text-anchor="middle" letter-spacing="0.5">Client</text>

    <!-- Component 2.1: Next.js Launchpad -->
    <g transform="translate(15, 45)" filter="url(#card-shadow)">
      <rect width="150" height="125" rx="6" fill="#ffffff" stroke="#0f172a" stroke-width="1.4" />
      <use href="#icon-nextjs" x="58" y="14" width="34" height="34" />
      <text x="75" y="64" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="800" text-anchor="middle">Next.js 14</text>
      <text x="75" y="79" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" text-anchor="middle">Core Launchpad</text>
      <text x="75" y="93" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">React 18 • Tailwind</text>
      <rect x="15" y="100" width="120" height="16" rx="3" fill="#f0f9ff" stroke="#0284c7" stroke-width="0.7" />
      <text x="75" y="112" fill="#0284c7" font-family="monospace" font-size="9" text-anchor="middle">Port 3000</text>
    </g>

    <!-- Component 2.2: Plugins Micro-Frontend -->
    <g transform="translate(15, 190)" filter="url(#card-shadow)">
      <rect width="150" height="125" rx="6" fill="#ffffff" stroke="#6366f1" stroke-width="1.4" />
      <circle cx="75" cy="30" r="16" fill="#ede9fe" stroke="#6366f1" stroke-width="1.2" />
      <path d="M 67 24 L 75 24 C 75 21 79 21 79 24 L 83 24 L 83 28 C 86 28 86 32 83 32 L 83 36 L 67 36 Z" fill="#6366f1" />
      <text x="75" y="64" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12.5" font-weight="700" text-anchor="middle">Plugins MFE</text>
      <text x="75" y="79" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" text-anchor="middle">Dynamic UI Loader</text>
      <text x="75" y="93" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">Module Federation</text>
      <rect x="15" y="100" width="120" height="16" rx="3" fill="#faf5ff" stroke="#6366f1" stroke-width="0.7" />
      <text x="75" y="112" fill="#7c3aed" font-family="monospace" font-size="8.5" text-anchor="middle">Sandboxed MFE</text>
    </g>
  </g>

  <!-- ==================== 3. INGRESS & IAM BLOCK ==================== -->
  <g transform="translate(270, 320)">
    <rect width="190" height="340" rx="8" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.8" />
    <text x="95" y="28" fill="#1e293b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800" text-anchor="middle" letter-spacing="0.5">Ingress &amp; IAM</text>

    <!-- Component 3.1: Traefik Proxy -->
    <g transform="translate(15, 45)" filter="url(#card-shadow)">
      <rect width="160" height="125" rx="6" fill="#ffffff" stroke="#24A1C1" stroke-width="1.5" />
      <use href="#icon-traefik" x="63" y="12" width="34" height="34" />
      <text x="80" y="62" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800" text-anchor="middle">Traefik Proxy</text>
      <text x="80" y="77" fill="#24A1C1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600" text-anchor="middle">Edge API Gateway</text>
      <text x="80" y="92" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">TLS • Dynamic Routing</text>
      <rect x="15" y="100" width="130" height="16" rx="3" fill="#ecfeff" stroke="#24A1C1" stroke-width="0.7" />
      <text x="80" y="112" fill="#0891b2" font-family="monospace" font-size="9" text-anchor="middle">Ports: 80 / 443</text>
    </g>

    <!-- Component 3.2: Keycloak IAM -->
    <g transform="translate(15, 190)" filter="url(#card-shadow)">
      <rect width="160" height="125" rx="6" fill="#ffffff" stroke="#008AD7" stroke-width="1.5" />
      <use href="#icon-keycloak" x="63" y="12" width="34" height="34" />
      <text x="80" y="62" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800" text-anchor="middle">Keycloak IAM</text>
      <text x="80" y="77" fill="#008AD7" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600" text-anchor="middle">Identity &amp; SSO</text>
      <text x="80" y="92" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">OIDC • Multi-Tenant RBAC</text>
      <rect x="15" y="100" width="130" height="16" rx="3" fill="#f0f9ff" stroke="#008AD7" stroke-width="0.7" />
      <text x="80" y="112" fill="#0284c7" font-family="monospace" font-size="9" text-anchor="middle">Port 8081</text>
    </g>
  </g>

  <!-- ==================== 4. CORE ENGINE & WORKFLOWS ==================== -->
  <g transform="translate(540, 400)">
    <rect width="730" height="260" rx="8" fill="#f0fdf4" stroke="#16a34a" stroke-width="1.8" />
    <text x="365" y="26" fill="#15803d" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800" text-anchor="middle" letter-spacing="0.5">Core Engine &amp; Automation (Innovation Layer)</text>

    <!-- Component 4.1: FastAPI Core Engine -->
    <g transform="translate(25, 45)" filter="url(#card-shadow)">
      <rect width="320" height="195" rx="6" fill="#ffffff" stroke="#009688" stroke-width="1.8" />
      <use href="#icon-fastapi" x="20" y="16" width="32" height="32" />
      <text x="62" y="32" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14.5" font-weight="900">FastAPI Core Engine</text>
      <text x="62" y="47" fill="#009688" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="600">Hexagonal Micro-Kernel (Python 3.12)</text>
      <line x1="15" y1="58" x2="305" y2="58" stroke="#e2e8f0" stroke-width="1" />
      <text x="18" y="78" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Domain Ports &amp; Adapters • Plugin Lifecycle</text>
      <text x="18" y="96" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Multi-Tenant Context Resolver Middleware</text>
      <text x="18" y="114" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Transactional Outbox (context.outbox ACID)</text>
      <text x="18" y="132" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• AI Orchestrator &amp; Safe DSL Execution</text>
      <rect x="18" y="146" width="284" height="20" rx="3" fill="#f0fdfa" stroke="#009688" stroke-width="0.8" />
      <text x="160" y="160" fill="#0f766e" font-family="monospace" font-size="9.5" text-anchor="middle">Port 8000 • Uvicorn ASGI Server</text>
    </g>

    <!-- Component 4.2: n8n Workflow Automation (WITH RICH OFFICIAL N8N LOGO) -->
    <g transform="translate(370, 45)" filter="url(#card-shadow)">
      <rect width="335" height="195" rx="6" fill="#ffffff" stroke="#EA4B71" stroke-width="1.8" />
      <!-- Rich Official n8n Logo -->
      <use href="#icon-n8n" x="18" y="14" width="46" height="34" />
      <text x="74" y="32" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14.5" font-weight="900">n8n Workflow Engine</text>
      <text x="74" y="47" fill="#e11d48" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="600">Low-Code Event Workflows</text>
      <line x1="15" y1="58" x2="320" y2="58" stroke="#e2e8f0" stroke-width="1" />
      <text x="18" y="78" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Event-Driven Triggers on Redis Streams</text>
      <text x="18" y="96" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Automated Cross-System Integration Canvas</text>
      <text x="18" y="114" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• 400+ Pre-built Connectors &amp; Webhooks</text>
      <text x="18" y="132" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Approval Chains &amp; ChatOps Alerts</text>
      <rect x="18" y="146" width="299" height="20" rx="3" fill="#fff1f2" stroke="#e11d48" stroke-width="0.8" />
      <text x="167" y="160" fill="#be123c" font-family="monospace" font-size="9.5" text-anchor="middle">Port 5678 • Webhooks &amp; Executions</text>
    </g>
  </g>

  <!-- ==================== 5. PERSISTENCE, EVENT BUS & AI (RIGHT BLOCK) ==================== -->
  <g transform="translate(1320, 130)">
    <rect width="310" height="530" rx="8" fill="#f8fafc" stroke="#475569" stroke-width="1.8" />
    <text x="155" y="26" fill="#1e293b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800" text-anchor="middle" letter-spacing="0.5">Persistence, Event Bus &amp; AI</text>

    <!-- Component 5.1: PostgreSQL 16 + PostGIS -->
    <g transform="translate(15, 45)" filter="url(#card-shadow)">
      <rect width="280" height="105" rx="6" fill="#ffffff" stroke="#4169E1" stroke-width="1.6" />
      <use href="#icon-postgresql" x="18" y="14" width="30" height="30" />
      <text x="56" y="28" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="900">PostgreSQL 16 + PostGIS</text>
      <text x="56" y="42" fill="#2563eb" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">Core Relational &amp; Spatial DB</text>
      <line x1="15" y1="52" x2="265" y2="52" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="68" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Multi-Tenant RLS Schemas • Outbox Table</text>
      <text x="15" y="82" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Spatial Geo-Data &amp; ACID Transactions</text>
      <rect x="15" y="86" width="250" height="14" rx="2" fill="#eff6ff" />
      <text x="140" y="96" fill="#1d4ed8" font-family="monospace" font-size="8.5" text-anchor="middle">Port 5432</text>
    </g>

    <!-- Component 5.2: Redis 7 Stack -->
    <g transform="translate(15, 165)" filter="url(#card-shadow)">
      <rect width="280" height="105" rx="6" fill="#ffffff" stroke="#FF4438" stroke-width="1.6" />
      <use href="#icon-redis" x="18" y="14" width="30" height="30" />
      <text x="56" y="28" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="900">Redis 7 Stack</text>
      <text x="56" y="42" fill="#dc2626" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">Distributed Event Bus &amp; Cache</text>
      <line x1="15" y1="52" x2="265" y2="52" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="68" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Redis Streams (maxlen 10k) • In-memory Cache</text>
      <text x="15" y="82" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Idempotency Deduplication Key</text>
      <rect x="15" y="86" width="250" height="14" rx="2" fill="#fef2f2" />
      <text x="140" y="96" fill="#b91c1c" font-family="monospace" font-size="8.5" text-anchor="middle">Port 6379</text>
    </g>

    <!-- Component 5.3: Qdrant Vector DB -->
    <g transform="translate(15, 285)" filter="url(#card-shadow)">
      <rect width="280" height="105" rx="6" fill="#ffffff" stroke="#DC2626" stroke-width="1.6" />
      <use href="#icon-qdrant" x="18" y="14" width="30" height="30" />
      <text x="56" y="28" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="900">Qdrant Vector DB</text>
      <text x="56" y="42" fill="#b91c1c" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">Vector Search Engine</text>
      <line x1="15" y1="52" x2="265" y2="52" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="68" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Multi-Tenant Vector Collections • RAG Pipeline</text>
      <text x="15" y="82" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• High-dimensional Embeddings Search</text>
      <rect x="15" y="86" width="250" height="14" rx="2" fill="#fef2f2" />
      <text x="140" y="96" fill="#991b1b" font-family="monospace" font-size="8.5" text-anchor="middle">Port 6333</text>
    </g>

    <!-- Component 5.4: Ollama Local LLM -->
    <g transform="translate(15, 405)" filter="url(#card-shadow)">
      <rect width="280" height="105" rx="6" fill="#ffffff" stroke="#0f172a" stroke-width="1.6" />
      <use href="#icon-ollama" x="18" y="14" width="30" height="30" />
      <text x="56" y="28" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="900">Ollama / Local LLM</text>
      <text x="56" y="42" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">On-Premise Private AI</text>
      <line x1="15" y1="52" x2="265" y2="52" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="68" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Llama-3, Qwen Offline Inference</text>
      <text x="15" y="82" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• 100% Data Privacy (Zero Cloud Leakage)</text>
      <rect x="15" y="86" width="250" height="14" rx="2" fill="#f8fafc" />
      <text x="140" y="96" fill="#475569" font-family="monospace" font-size="8.5" text-anchor="middle">Port 11434</text>
    </g>
  </g>

  <!-- ==================== 6. COLLABORATION & ANALYTICS ==================== -->
  <g transform="translate(50, 690)">
    <rect width="430" height="155" rx="8" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.8" />
    <text x="215" y="26" fill="#1e293b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800" text-anchor="middle" letter-spacing="0.5">Collaboration &amp; Analytics</text>

    <!-- Component 6.1: Mattermost -->
    <g transform="translate(15, 42)" filter="url(#card-shadow)">
      <rect width="190" height="98" rx="6" fill="#ffffff" stroke="#0058CC" stroke-width="1.4" />
      <use href="#icon-mattermost" x="16" y="14" width="28" height="28" />
      <text x="52" y="28" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="800">Mattermost</text>
      <text x="52" y="42" fill="#0058CC" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">Team ChatOps &amp; Bot</text>
      <line x1="12" y1="52" x2="178" y2="52" stroke="#e2e8f0" stroke-width="0.8" />
      <text x="95" y="68" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">Channels • AI Assistant Bot</text>
      <rect x="15" y="74" width="160" height="15" rx="2" fill="#f0f9ff" />
      <text x="95" y="85" fill="#0369a1" font-family="monospace" font-size="8.5" text-anchor="middle">Port 8065</text>
    </g>

    <!-- Component 6.2: Metabase (WITH OFFICIAL LOGO) -->
    <g transform="translate(225, 42)" filter="url(#card-shadow)">
      <rect width="190" height="98" rx="6" fill="#ffffff" stroke="#509EE3" stroke-width="1.4" />
      <use href="#icon-metabase" x="16" y="14" width="28" height="28" />
      <text x="52" y="28" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="800">Metabase BI</text>
      <text x="52" y="42" fill="#0284c7" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">Self-Service Dashboards</text>
      <line x1="12" y1="52" x2="178" y2="52" stroke="#e2e8f0" stroke-width="0.8" />
      <text x="95" y="68" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" text-anchor="middle">Secure JWT Embedded IFrames</text>
      <rect x="15" y="74" width="160" height="15" rx="2" fill="#f0f9ff" />
      <text x="95" y="85" fill="#0369a1" font-family="monospace" font-size="8.5" text-anchor="middle">Port 3001</text>
    </g>
  </g>

  <!-- ==================== 7. OBSERVABILITY INFRASTRUCTURE (WITH OFFICIAL LOKI LOGO) ==================== -->
  <g transform="translate(540, 690)">
    <rect width="1090" height="155" rx="8" fill="#f1f5f9" stroke="#94a3b8" stroke-width="1.8" />
    <text x="545" y="26" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="800" text-anchor="middle" letter-spacing="0.5">Observability, Metrics &amp; Incident Drill Stack</text>

    <!-- Component 7.1: Prometheus -->
    <g transform="translate(25, 42)" filter="url(#card-shadow)">
      <rect width="325" height="98" rx="6" fill="#ffffff" stroke="#E6522C" stroke-width="1.5" />
      <use href="#icon-prometheus" x="18" y="14" width="30" height="30" />
      <text x="58" y="30" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="900">Prometheus Telemetry</text>
      <text x="58" y="44" fill="#c2410c" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">Time-Series Metrics Scraper</text>
      <line x1="15" y1="52" x2="310" y2="52" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="68" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Scrapes Outbox Lag &amp; DLQ Counters</text>
      <text x="15" y="82" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Realtime API Latency &amp; Memory Metrics</text>
      <rect x="15" y="86" width="295" height="10" rx="2" fill="#fff7ed" />
    </g>

    <!-- Component 7.2: Grafana -->
    <g transform="translate(380, 42)" filter="url(#card-shadow)">
      <rect width="325" height="98" rx="6" fill="#ffffff" stroke="#F46800" stroke-width="1.5" />
      <use href="#icon-grafana" x="18" y="14" width="30" height="30" />
      <text x="58" y="30" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="900">Grafana Dashboards</text>
      <text x="58" y="44" fill="#ea580c" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">Unified Operational Visualizer</text>
      <line x1="15" y1="52" x2="310" y2="52" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="68" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Layer 3 Broker Dashboard Included</text>
      <text x="15" y="82" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Automated Incident Drill Alerts</text>
      <rect x="15" y="86" width="295" height="10" rx="2" fill="#fff7ed" />
    </g>

    <!-- Component 7.3: Grafana Loki (WITH OFFICIAL LOKI LOGO) -->
    <g transform="translate(735, 42)" filter="url(#card-shadow)">
      <rect width="330" height="98" rx="6" fill="#ffffff" stroke="#7c3aed" stroke-width="1.5" />
      <use href="#icon-loki" x="18" y="14" width="30" height="30" />
      <text x="58" y="30" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="900">Grafana Loki</text>
      <text x="58" y="44" fill="#7c3aed" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">Centralized Log Aggregator</text>
      <line x1="15" y1="52" x2="315" y2="52" stroke="#e2e8f0" stroke-width="1" />
      <text x="15" y="68" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Centralized Shipping for 45 Containers</text>
      <text x="15" y="82" fill="#475569" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Promtail Shipping &amp; Trace ID Correlation</text>
      <rect x="15" y="86" width="300" height="10" rx="2" fill="#faf5ff" />
    </g>
  </g>

  <!-- ==================== 8. FOOTER CAPTION & EXPLANATION ==================== -->
  <g transform="translate(50, 865)">
    <rect width="1580" height="135" rx="6" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1" />
    <text x="25" y="28" fill="#0f172a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="900">📌 Ghi chú Kiến trúc &amp; Luồng Giao dịch Ngữ cảnh (Layer 3 Context CDC Flow):</text>
    <text x="25" y="54" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12">1. <tspan font-weight="bold" fill="#0284c7">Transactional Outbox Pattern:</tspan> Khi nghiệp vụ ghi vào PostgreSQL, sự kiện được ghi cùng giao dịch ACID vào bảng <tspan font-family="monospace" fill="#0f766e">context.outbox</tspan>, loại bỏ nguy cơ bất đồng bộ dữ liệu (Dual-write race conditions).</text>
    <text x="25" y="78" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12">2. <tspan font-weight="bold" fill="#16a34a">Cơ chế Chống vòng lặp (Anti-Sync Loop):</tspan> Worker đẩy sang Orion-LD &amp; Redis Streams. Khi Orion gửi webhook ngược về Backend, hệ thống cập nhật <tspan font-family="monospace" fill="#0f766e">entity_state</tspan> mà không ghi lại outbox để triệt tiêu vòng lặp vô tận.</text>
    <text x="25" y="102" fill="#334155" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12">3. <tspan font-weight="bold" fill="#e11d48">Realtime Subscriptions:</tspan> Client nhận cập nhật tức thời qua Hasura GraphQL WebSocket với phân quyền bảo mật lọc dòng/cột theo Keycloak JWT Claims (<tspan font-family="monospace" fill="#0f766e">x-hasura-tenant-id</tspan>).</text>
    <text x="25" y="124" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11">4. <tspan font-weight="bold">Phục hồi Sự cố (DLQ):</tspan> Bản ghi đồng bộ lỗi được chuyển vào Dead Letter Queue với 5 lần thử lại theo cơ chế Exponential Backoff, cho phép kích hoạt tái xử lý thủ công qua API <tspan font-family="monospace">POST /api/v1/context/outbox/replay-dlq</tspan>.</text>
  </g>
</svg>""")

full_svg = "".join(svg)

output_path = os.path.join(REPO_ROOT, "docs", "images", "architecture_flow.svg")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(full_svg)

print(f"Successfully generated clean spacious architecture SVG: {output_path} ({len(full_svg)} bytes)")
