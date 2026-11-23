# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Generator for Proteus OS System Architecture SVG Diagram.
Embeds official vector SVG icons and modern enterprise layout.
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

cache_file = os.path.join(SCRIPT_DIR, "icons_cache.json")
with open(cache_file, "r", encoding="utf-8") as f:
    icons = json.load(f)

svg_parts = []

# SVG Header
svg_parts.append("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1060" width="100%" height="100%">
  <defs>
    <!-- Background Gradient -->
    <linearGradient id="bg-grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#070b14" />
      <stop offset="40%" stop-color="#0c1222" />
      <stop offset="80%" stop-color="#0a101d" />
      <stop offset="100%" stop-color="#060911" />
    </linearGradient>

    <!-- Subtle Grid Pattern -->
    <pattern id="grid-pattern" width="40" height="40" patternUnits="userSpaceOnUse">
      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" stroke-width="0.75" stroke-opacity="0.35" />
    </pattern>

    <!-- Zone Backgrounds -->
    <linearGradient id="zone-bg" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#1e293b" stop-opacity="0.25" />
      <stop offset="100%" stop-color="#0f172a" stop-opacity="0.45" />
    </linearGradient>

    <!-- Card Background Gradient -->
    <linearGradient id="card-bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e293b" stop-opacity="0.65" />
      <stop offset="100%" stop-color="#0f172a" stop-opacity="0.85" />
    </linearGradient>

    <!-- Highlighted Card Background -->
    <linearGradient id="card-highlight" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e3a5f" stop-opacity="0.4" />
      <stop offset="100%" stop-color="#0d1f38" stop-opacity="0.7" />
    </linearGradient>

    <!-- Shadows -->
    <filter id="shadow-soft" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="6" stdDeviation="10" flood-color="#000000" flood-opacity="0.5" />
    </filter>
    <filter id="shadow-card" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#020617" flood-opacity="0.6" />
    </filter>

    <!-- Glows -->
    <filter id="glow-cyan" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="3" result="blur" />
      <feFlood flood-color="#06b6d4" result="color" />
      <feComposite in="color" in2="blur" operator="in" result="glow" />
      <feMerge>
        <feMergeNode in="glow" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
    <filter id="glow-emerald" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="3" result="blur" />
      <feFlood flood-color="#10b981" result="color" />
      <feComposite in="color" in2="blur" operator="in" result="glow" />
      <feMerge>
        <feMergeNode in="glow" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
    <filter id="glow-rose" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="3" result="blur" />
      <feFlood flood-color="#f43f5e" result="color" />
      <feComposite in="color" in2="blur" operator="in" result="glow" />
      <feMerge>
        <feMergeNode in="glow" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
    <filter id="glow-amber" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="3" result="blur" />
      <feFlood flood-color="#f59e0b" result="color" />
      <feComposite in="color" in2="blur" operator="in" result="glow" />
      <feMerge>
        <feMergeNode in="glow" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
    <filter id="glow-purple" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="3" result="blur" />
      <feFlood flood-color="#a855f7" result="color" />
      <feComposite in="color" in2="blur" operator="in" result="glow" />
      <feMerge>
        <feMergeNode in="glow" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
""")

# Embed SVG Symbols
for name, data in icons.items():
    viewBox = data.get("viewBox", "0 0 24 24")
    color = data.get("color", "#FFFFFF")
    svg_parts.append(f'    <symbol id="icon-{name}" viewBox="{viewBox}">')
    if data.get("raw_fiware"):
        # Multiple colored paths for FIWARE
        for p in data["paths"]:
            svg_parts.append(f'      <path d="{p["d"]}" fill="{p.get("fill", "#002E6D")}" />')
    else:
        for p in data["paths"]:
            svg_parts.append(f'      <path d="{p}" fill="{color}" />')
    svg_parts.append("    </symbol>")

svg_parts.append("""  </defs>

  <!-- Canvas Background -->
  <rect width="100%" height="100%" fill="url(#bg-grad)" />
  <rect width="100%" height="100%" fill="url(#grid-pattern)" />

  <!-- ==================== HEADER BAR ==================== -->
  <g transform="translate(40, 20)">
    <!-- Title and Subtitle -->
    <text x="0" y="32" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="24" font-weight="800" letter-spacing="1">⚡ PROTEUS OS — SYSTEM ARCHITECTURE</text>
    <text x="0" y="54" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="13" font-weight="500">Enterprise Universal OS • Multi-Tenant Micro-Kernel • FIWARE NGSI-LD &amp; Hasura Realtime Context • Event-Driven AI</text>

    <!-- Badges -->
    <g transform="translate(980, 10)">
      <!-- Badge 1: AGPL-3.0 -->
      <rect x="0" y="5" width="130" height="26" rx="6" fill="#1e1b4b" stroke="#6366f1" stroke-width="1" />
      <text x="65" y="22" fill="#a5b4fc" font-family="monospace" font-size="11" font-weight="bold" text-anchor="middle">AGPL-3.0-or-later</text>
      
      <!-- Badge 2: Multi-Tenancy RLS -->
      <rect x="140" y="5" width="150" height="26" rx="6" fill="#064e3b" stroke="#10b981" stroke-width="1" />
      <text x="215" y="22" fill="#6ee7b7" font-family="monospace" font-size="11" font-weight="bold" text-anchor="middle">Multi-Tenant RLS</text>

      <!-- Badge 3: Event-Driven -->
      <rect x="300" y="5" width="130" height="26" rx="6" fill="#4c0519" stroke="#f43f5e" stroke-width="1" />
      <text x="365" y="22" fill="#fda4af" font-family="monospace" font-size="11" font-weight="bold" text-anchor="middle">Event-Driven Core</text>

      <!-- Badge 4: Zero-Bundling -->
      <rect x="440" y="5" width="100" height="26" rx="6" fill="#1e293b" stroke="#475569" stroke-width="1" />
      <text x="490" y="22" fill="#cbd5e1" font-family="monospace" font-size="11" font-weight="bold" text-anchor="middle">Zero-Bundling</text>
    </g>
  </g>

  <!-- ==================== FLOW CONNECTIONS (UNDERLAY) ==================== -->
  <g fill="none" stroke-linecap="round" stroke-linejoin="round">
    <!-- Path 1: Client -> Traefik -->
    <path id="flow-client-traefik" d="M 170 240 L 170 300" stroke="#38bdf8" stroke-width="2" stroke-dasharray="4,4" />

    <!-- Path 2: Traefik -> Keycloak (Auth OIDC) -->
    <path id="flow-traefik-keycloak" d="M 170 415 L 170 480" stroke="#0ea5e9" stroke-width="2" />

    <!-- Path 3: Traefik -> Next.js Launchpad -->
    <path id="flow-traefik-nextjs" d="M 285 355 C 320 355, 320 220, 355 220" stroke="#38bdf8" stroke-width="2" />

    <!-- Path 4: Traefik -> FastAPI Core -->
    <path id="flow-traefik-fastapi" d="M 285 355 C 450 355, 520 270, 645 270" stroke="#2dd4bf" stroke-width="2.5" />

    <!-- Path 5: Traefik -> Hasura GraphQL -->
    <path id="flow-traefik-hasura" d="M 285 355 C 500 355, 750 440, 985 440" stroke="#f43f5e" stroke-width="2" />

    <!-- Path 6: Next.js -> FastAPI Core (REST / OpenAPI) -->
    <path id="flow-nextjs-fastapi" d="M 590 220 C 615 220, 615 270, 645 270" stroke="#38bdf8" stroke-width="2" />

    <!-- Path 7: Next.js -> Hasura (GraphQL Live Queries / WS) -->
    <path id="flow-nextjs-hasura" d="M 590 240 C 780 240, 850 420, 985 420" stroke="#e10098" stroke-width="1.8" stroke-dasharray="5,3" />

    <!-- Path 8: Keycloak -> Hasura (JWT Claims Sync & Verification) -->
    <path id="flow-keycloak-hasura" d="M 285 540 C 600 540, 800 460, 985 460" stroke="#a855f7" stroke-width="1.8" stroke-dasharray="4,4" />

    <!-- Path 9: FastAPI -> PostgreSQL (SQLAlchemy + Outbox Table) -->
    <path id="flow-fastapi-db" d="M 945 270 C 1100 270, 1180 230, 1305 230" stroke="#60a5fa" stroke-width="2.5" />

    <!-- Path 10: PostgreSQL Outbox -> Context Sync Worker -->
    <path id="flow-db-worker" d="M 1305 260 C 1180 260, 1160 630, 1245 630" stroke="#f59e0b" stroke-width="2" />

    <!-- Path 11: Context Sync Worker -> FIWARE Orion-LD -->
    <path id="flow-worker-orion" d="M 1115 600 C 1115 400, 1115 320, 1115 300" stroke="#10b981" stroke-width="2.5" />

    <!-- Path 12: Context Sync Worker -> Redis Streams -->
    <path id="flow-worker-redis" d="M 1245 660 C 1275 660, 1275 420, 1305 420" stroke="#f43f5e" stroke-width="2.5" />

    <!-- Path 13: Orion-LD -> Subscriptions Webhook (Anti-Loop) -->
    <path id="flow-orion-webhook" d="M 985 240 C 850 240, 850 360, 945 360" stroke="#10b981" stroke-width="1.8" stroke-dasharray="4,4" />

    <!-- Path 14: FastAPI -> Redis (Event Bus & Cache) -->
    <path id="flow-fastapi-redis" d="M 945 330 C 1120 330, 1180 400, 1305 400" stroke="#f43f5e" stroke-width="2" />

    <!-- Path 15: Redis Streams -> n8n Workflow Automation -->
    <path id="flow-redis-n8n" d="M 1305 440 C 1150 440, 850 630, 945 630" stroke="#ea580c" stroke-width="2" />

    <!-- Path 16: Hasura -> PostgreSQL (Direct GraphQL Read/Write + RLS) -->
    <path id="flow-hasura-db" d="M 1245 440 C 1275 440, 1275 250, 1305 250" stroke="#38bdf8" stroke-width="2" />

    <!-- Path 17: FastAPI -> Qdrant (Embeddings & Semantic Search) -->
    <path id="flow-fastapi-qdrant" d="M 945 450 C 1120 450, 1180 570, 1305 570" stroke="#ef4444" stroke-width="2" />

    <!-- Path 18: FastAPI -> Ollama (Local AI Inference) -->
    <path id="flow-fastapi-ollama" d="M 945 490 C 1120 490, 1180 740, 1305 740" stroke="#e2e8f0" stroke-width="2" />
  </g>

  <!-- ==================== ZONE 1: INGRESS & SECURITY ==================== -->
  <g transform="translate(40, 90)">
    <!-- Zone Box -->
    <rect width="250" height="740" rx="14" fill="url(#zone-bg)" stroke="#334155" stroke-width="1" />
    <rect x="0" y="0" width="250" height="36" rx="14" fill="#1e293b" fill-opacity="0.6" />
    <text x="125" y="23" fill="#38bdf8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="bold" letter-spacing="1" text-anchor="middle">🛡️ 1. INGRESS &amp; SECURITY</text>

    <!-- Client Card -->
    <g transform="translate(15, 50)" filter="url(#shadow-soft)">
      <rect width="220" height="95" rx="10" fill="url(#card-bg)" stroke="#38bdf8" stroke-opacity="0.4" stroke-width="1.2" />
      <circle cx="35" cy="35" r="16" fill="#0284c7" fill-opacity="0.2" stroke="#38bdf8" stroke-width="1" />
      <!-- Browser Icon SVG Path -->
      <path d="M 27 30 L 43 30 M 27 35 L 43 35 M 27 40 L 37 40" stroke="#38bdf8" stroke-width="2" stroke-linecap="round" fill="none" />
      <text x="65" y="32" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="bold">External Clients</text>
      <text x="65" y="47" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5">Browsers, Mobile, Webhooks</text>
      <line x1="15" y1="65" x2="205" y2="65" stroke="#334155" stroke-width="0.8" />
      <text x="25" y="81" fill="#38bdf8" font-family="monospace" font-size="9.5">HTTPS / WSS • Port 443, 80</text>
    </g>

    <!-- Traefik Card -->
    <g transform="translate(15, 160)" filter="url(#shadow-soft)">
      <rect width="220" height="150" rx="10" fill="url(#card-bg)" stroke="#24A1C1" stroke-opacity="0.6" stroke-width="1.5" />
      <rect x="22" y="20" width="30" height="30" rx="6" fill="#24A1C1" fill-opacity="0.15" />
      <use href="#icon-traefik" x="25" y="23" width="24" height="24" />
      <text x="62" y="34" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="bold">Traefik Proxy</text>
      <text x="62" y="49" fill="#24A1C1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">Edge Gateway &amp; Ingress</text>
      <line x1="15" y1="62" x2="205" y2="62" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="80" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Dynamic Path Prefix Routing</text>
      <text x="20" y="98" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Auto TLS (Let's Encrypt)</text>
      <text x="20" y="116" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Rate Limiting &amp; Health Checks</text>
      <rect x="18" y="125" width="184" height="18" rx="4" fill="#0f172a" stroke="#24A1C1" stroke-width="0.7" />
      <text x="110" y="137" fill="#67e8f9" font-family="monospace" font-size="9" text-anchor="middle">Priority-based Routing Rules</text>
    </g>

    <!-- Keycloak IAM Card -->
    <g transform="translate(15, 330)" filter="url(#shadow-soft)">
      <rect width="220" height="170" rx="10" fill="url(#card-bg)" stroke="#008AD7" stroke-opacity="0.6" stroke-width="1.5" />
      <rect x="22" y="20" width="30" height="30" rx="6" fill="#008AD7" fill-opacity="0.15" />
      <use href="#icon-keycloak" x="25" y="23" width="24" height="24" />
      <text x="62" y="34" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="bold">Keycloak IAM</text>
      <text x="62" y="49" fill="#38bdf8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">Auth &amp; Tenant Identity</text>
      <line x1="15" y1="62" x2="205" y2="62" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="80" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• OpenID Connect (OIDC) / OAuth2</text>
      <text x="20" y="98" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Multi-Tenant Realms &amp; RBAC</text>
      <text x="20" y="116" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• JWT Claims Mapping</text>
      <rect x="18" y="128" width="184" height="28" rx="4" fill="#0b1e3b" stroke="#008AD7" stroke-width="0.8" />
      <text x="110" y="140" fill="#7dd3fc" font-family="monospace" font-size="8.5" text-anchor="middle">x-hasura-tenant-id</text>
      <text x="110" y="151" fill="#7dd3fc" font-family="monospace" font-size="8.5" text-anchor="middle">x-hasura-default-role</text>
    </g>

    <!-- Network Security Boundary Box -->
    <g transform="translate(15, 520)">
      <rect width="220" height="205" rx="8" fill="#0b1329" stroke="#1e3a8a" stroke-dasharray="4,4" stroke-width="1.2" />
      <text x="110" y="24" fill="#93c5fd" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="bold" text-anchor="middle">🔒 Zero-Trust Boundary</text>
      <text x="20" y="48" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Strict Multi-Tenant Isolation</text>
      <text x="20" y="66" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Row-Level Security (RLS)</text>
      <text x="20" y="84" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Cap-Drop &amp; Non-Root Users</text>
      <text x="20" y="102" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Internal Bridge Network</text>
      <line x1="20" y1="116" x2="200" y2="116" stroke="#1e293b" stroke-width="1" />
      <text x="20" y="136" fill="#64748b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">Compliant with:</text>
      <text x="20" y="154" fill="#38bdf8" font-family="monospace" font-size="9.5">OWASP Top 10 • RBAC Matrix</text>
      <text x="20" y="172" fill="#38bdf8" font-family="monospace" font-size="9.5">Audit Logging • CORS Strict</text>
      <rect x="20" y="182" width="180" height="15" rx="3" fill="#1e293b" />
      <text x="110" y="193" fill="#cbd5e1" font-family="monospace" font-size="8.5" text-anchor="middle">Proteus Core Security Guard</text>
    </g>
  </g>

  <!-- ==================== ZONE 2: PRESENTATION & APPS ==================== -->
  <g transform="translate(310, 90)">
    <!-- Zone Box -->
    <rect width="280" height="740" rx="14" fill="url(#zone-bg)" stroke="#334155" stroke-width="1" />
    <rect x="0" y="0" width="280" height="36" rx="14" fill="#1e293b" fill-opacity="0.6" />
    <text x="140" y="23" fill="#67e8f9" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="bold" letter-spacing="1" text-anchor="middle">💻 2. FRONTEND &amp; COLLABORATION</text>

    <!-- Next.js Core Frontend Card -->
    <g transform="translate(15, 50)" filter="url(#shadow-soft)">
      <rect width="250" height="175" rx="10" fill="url(#card-bg)" stroke="#cbd5e1" stroke-opacity="0.5" stroke-width="1.5" />
      <rect x="20" y="20" width="32" height="32" rx="6" fill="#000000" />
      <use href="#icon-nextjs" x="24" y="24" width="24" height="24" />
      <text x="62" y="34" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="bold">Next.js 14 Launchpad</text>
      <text x="62" y="49" fill="#e2e8f0" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">Unified Work OS Frontend</text>
      <line x1="15" y1="62" x2="235" y2="62" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="80" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• App Router &amp; Server Components</text>
      <text x="20" y="98" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Zustand State &amp; Custom Hooks</text>
      <text x="20" y="116" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• TailwindCSS &amp; Glassmorphism</text>
      <text x="20" y="134" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Dynamic Plugin App Store</text>
      <rect x="18" y="145" width="214" height="20" rx="4" fill="#0f172a" stroke="#475569" stroke-width="0.8" />
      <text x="125" y="159" fill="#38bdf8" font-family="monospace" font-size="9" text-anchor="middle">Next.js BFF • Port 3000</text>
    </g>

    <!-- Plugins Micro-Frontend Card -->
    <g transform="translate(15, 240)" filter="url(#shadow-soft)">
      <rect width="250" height="135" rx="10" fill="url(#card-bg)" stroke="#818cf8" stroke-opacity="0.5" stroke-width="1.2" />
      <circle cx="36" cy="35" r="16" fill="#4338ca" fill-opacity="0.3" stroke="#818cf8" stroke-width="1" />
      <!-- MFE Puzzle Icon -->
      <path d="M 28 32 L 34 32 C 34 29 38 29 38 32 L 44 32 L 44 38 C 47 38 47 42 44 42 L 44 48 L 28 48 Z" fill="#818cf8" fill-opacity="0.8" />
      <text x="62" y="34" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="bold">Plugin Micro-Frontend</text>
      <text x="62" y="49" fill="#a5b4fc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5">MFE Gateway Container</text>
      <line x1="15" y1="60" x2="235" y2="60" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="78" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Independent Frontend Bundles</text>
      <text x="20" y="96" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Sandboxed Module Federation</text>
      <text x="20" y="114" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Injected at /plugins/&lt;code&gt;/fe</text>
    </g>

    <!-- Mattermost Card -->
    <g transform="translate(15, 390)" filter="url(#shadow-soft)">
      <rect width="250" height="145" rx="10" fill="url(#card-bg)" stroke="#0058CC" stroke-opacity="0.6" stroke-width="1.2" />
      <rect x="20" y="20" width="32" height="32" rx="6" fill="#0058CC" fill-opacity="0.2" />
      <use href="#icon-mattermost" x="24" y="24" width="24" height="24" />
      <text x="62" y="34" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="bold">Mattermost Chat</text>
      <text x="62" y="49" fill="#60a5fa" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">Team Collaboration</text>
      <line x1="15" y1="60" x2="235" y2="60" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="78" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Channels, Direct Messages</text>
      <text x="20" y="96" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Bot Webhooks &amp; ChatOps</text>
      <text x="20" y="114" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Keycloak SSO Integration</text>
      <rect x="18" y="122" width="214" height="16" rx="3" fill="#0c1b38" />
      <text x="125" y="133" fill="#93c5fd" font-family="monospace" font-size="8.5" text-anchor="middle">Port 8065 • ChatOps Interactivity</text>
    </g>

    <!-- Metabase BI Card -->
    <g transform="translate(15, 550)" filter="url(#shadow-soft)">
      <rect width="250" height="175" rx="10" fill="url(#card-bg)" stroke="#509EE3" stroke-opacity="0.6" stroke-width="1.2" />
      <rect x="20" y="20" width="32" height="32" rx="6" fill="#509EE3" fill-opacity="0.2" />
      <!-- Chart Icon SVG Path -->
      <path d="M 26 44 L 26 34 M 32 44 L 32 26 M 38 44 L 38 30 M 44 44 L 44 22 M 24 46 L 46 46" stroke="#509EE3" stroke-width="2" stroke-linecap="round" fill="none" />
      <text x="62" y="34" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="bold">Metabase OSS BI</text>
      <text x="62" y="49" fill="#93c5fd" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">Analytics &amp; Dashboards</text>
      <line x1="15" y1="60" x2="235" y2="60" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="78" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Self-service Visual Analytics</text>
      <text x="20" y="96" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Secure JWT Embedded IFrames</text>
      <text x="20" y="114" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Direct PostgreSQL Sync</text>
      <text x="20" y="132" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Automated KPI Alerting</text>
      <rect x="18" y="145" width="214" height="18" rx="3" fill="#0d2342" />
      <text x="125" y="157" fill="#67e8f9" font-family="monospace" font-size="8.5" text-anchor="middle">Port 3001 • Embedded Analytics</text>
    </g>
  </g>

  <!-- ==================== ZONE 3: CORE ENGINE & WORKFLOWS ==================== -->
  <g transform="translate(610, 90)">
    <!-- Zone Box -->
    <rect width="335" height="740" rx="14" fill="url(#zone-bg)" stroke="#334155" stroke-width="1" />
    <rect x="0" y="0" width="335" height="36" rx="14" fill="#1e293b" fill-opacity="0.6" />
    <text x="167" y="23" fill="#34d399" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="bold" letter-spacing="1" text-anchor="middle">⚙️ 3. CORE ENGINE (INNOVATION LAYER)</text>

    <!-- FastAPI Core Engine Main Card -->
    <g transform="translate(15, 50)" filter="url(#shadow-card)">
      <rect width="305" height="460" rx="12" fill="url(#card-highlight)" stroke="#009688" stroke-width="1.8" />
      <rect x="20" y="18" width="36" height="36" rx="8" fill="#009688" fill-opacity="0.25" />
      <use href="#icon-fastapi" x="26" y="24" width="24" height="24" />
      <text x="68" y="34" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="16" font-weight="800">FastAPI Core Engine</text>
      <text x="68" y="50" fill="#2dd4bf" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="600">Hexagonal Micro-Kernel (Python 3.12)</text>
      <line x1="15" y1="65" x2="290" y2="65" stroke="#334155" stroke-width="1" />

      <!-- Layer 3.1: Domain & Ports -->
      <g transform="translate(15, 75)">
        <rect width="275" height="60" rx="6" fill="#0b1e2a" stroke="#134e4a" stroke-width="1" />
        <text x="12" y="18" fill="#5eead4" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="bold">Core Domain &amp; Use Cases</text>
        <text x="12" y="34" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Hexagonal Ports &amp; Adapters Pattern</text>
        <text x="12" y="48" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Multi-Tenant Context Resolver Middleware</text>
      </g>

      <!-- Layer 3.2: Dynamic Plugin Lifecycle -->
      <g transform="translate(15, 145)">
        <rect width="275" height="75" rx="6" fill="#0b1e2a" stroke="#134e4a" stroke-width="1" />
        <text x="12" y="18" fill="#5eead4" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="bold">Plugin Lifecycle Engine</text>
        <text x="12" y="34" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Hot-Install, Enable, Disable, Uninstall</text>
        <text x="12" y="48" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Automated Migration Scripts Execution</text>
        <text x="12" y="62" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Context Sync Hooks &amp; State Handlers</text>
      </g>

      <!-- Layer 3.3: Transactional Outbox Engine -->
      <g transform="translate(15, 230)">
        <rect width="275" height="75" rx="6" fill="#0f2937" stroke="#009688" stroke-width="1" />
        <text x="12" y="18" fill="#2dd4bf" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="bold">Transactional Outbox Pattern</text>
        <text x="12" y="34" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Writes to context.outbox in same ACID Tx</text>
        <text x="12" y="48" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Eliminates Dual-Write Race Conditions</text>
        <text x="12" y="62" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Dead Letter Queue (DLQ) &amp; Replay API</text>
      </g>

      <!-- Layer 3.4: AI Agent Orchestrator -->
      <g transform="translate(15, 315)">
        <rect width="275" height="80" rx="6" fill="#0b1e2a" stroke="#134e4a" stroke-width="1" />
        <text x="12" y="18" fill="#5eead4" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="bold">AI Orchestrator &amp; DX-DSL</text>
        <text x="12" y="34" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Agent Tool-Calling with Guardrails</text>
        <text x="12" y="48" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• DX-DSL Verification &amp; Dry-run Sandbox</text>
        <text x="12" y="62" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• RAG Ingestion Pipeline (Qdrant &amp; FastEmbed)</text>
      </g>

      <!-- Port & Info Bar -->
      <rect x="15" y="415" width="275" height="30" rx="4" fill="#042f2e" stroke="#0d9488" stroke-width="1" />
      <text x="152" y="434" fill="#99f6e4" font-family="monospace" font-size="10.5" font-weight="bold" text-anchor="middle">FastAPI Core • Port 8000 • Uvicorn</text>
    </g>

    <!-- n8n Workflow Automation Card -->
    <g transform="translate(15, 530)" filter="url(#shadow-soft)">
      <rect width="305" height="185" rx="10" fill="url(#card-bg)" stroke="#EA4B71" stroke-opacity="0.6" stroke-width="1.3" />
      <rect x="20" y="20" width="32" height="32" rx="6" fill="#EA4B71" fill-opacity="0.2" />
      <use href="#icon-n8n" x="24" y="24" width="24" height="24" />
      <text x="64" y="34" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="bold">n8n Workflow Automation</text>
      <text x="64" y="50" fill="#f43f5e" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">Low-Code Event Workflows</text>
      <line x1="15" y1="62" x2="290" y2="62" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="82" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Visual Cross-System Integration Canvas</text>
      <text x="20" y="100" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Triggers on Redis Streams &amp; Context Events</text>
      <text x="20" y="118" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Automated Approval &amp; Notification Flows</text>
      <text x="20" y="136" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• 400+ Pre-built Connectors</text>
      <rect x="18" y="148" width="269" height="22" rx="4" fill="#2d0b16" stroke="#9f1239" stroke-width="0.8" />
      <text x="152" y="163" fill="#fca5a5" font-family="monospace" font-size="9" text-anchor="middle">Port 5678 • Webhooks &amp; Executions</text>
    </g>
  </g>

  <!-- ==================== ZONE 4: CONTEXT BROKER & REALTIME ==================== -->
  <g transform="translate(965, 90)">
    <!-- Zone Box -->
    <rect width="305" height="740" rx="14" fill="url(#zone-bg)" stroke="#334155" stroke-width="1" />
    <rect x="0" y="0" width="305" height="36" rx="14" fill="#1e293b" fill-opacity="0.6" />
    <text x="152" y="23" fill="#38bdf8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="bold" letter-spacing="1" text-anchor="middle">🌐 4. CONTEXT BROKER &amp; REALTIME (LAYER 3)</text>

    <!-- FIWARE Orion-LD Card -->
    <g transform="translate(15, 50)" filter="url(#shadow-soft)">
      <rect width="275" height="175" rx="10" fill="url(#card-bg)" stroke="#002E6D" stroke-opacity="0.8" stroke-width="1.5" />
      <rect x="20" y="16" width="100" height="26" rx="4" fill="#ffffff" fill-opacity="0.9" />
      <use href="#icon-fiware" x="24" y="19" width="92" height="20" />
      <text x="130" y="28" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="bold">Orion-LD Broker</text>
      <text x="130" y="42" fill="#38bdf8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">NGSI-LD Standard</text>
      <line x1="15" y1="52" x2="260" y2="52" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="70" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Digital Twin Entity State Management</text>
      <text x="20" y="88" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• NGSI-LD Linked Data Graph Model</text>
      <text x="20" y="106" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Geo-Spatial &amp; Temporal Query Engine</text>
      <text x="20" y="124" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Webhook Subscriptions (Entity Changes)</text>
      <rect x="18" y="136" width="239" height="26" rx="4" fill="#041b38" stroke="#0284c7" stroke-width="0.8" />
      <text x="137" y="152" fill="#7dd3fc" font-family="monospace" font-size="9" text-anchor="middle">Port 1026 • Context Broker Standard</text>
    </g>

    <!-- Hasura GraphQL Engine Card -->
    <g transform="translate(15, 245)" filter="url(#shadow-soft)">
      <rect width="275" height="195" rx="10" fill="url(#card-bg)" stroke="#1EB4D4" stroke-opacity="0.6" stroke-width="1.5" />
      <rect x="20" y="18" width="30" height="30" rx="6" fill="#1EB4D4" fill-opacity="0.2" />
      <use href="#icon-hasura" x="23" y="21" width="24" height="24" />
      <rect x="58" y="18" width="30" height="30" rx="6" fill="#E10098" fill-opacity="0.2" />
      <use href="#icon-graphql" x="61" y="21" width="24" height="24" />
      <text x="96" y="32" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13.5" font-weight="bold">Hasura GraphQL</text>
      <text x="96" y="47" fill="#67e8f9" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">Instant Realtime Engine</text>
      <line x1="15" y1="58" x2="260" y2="58" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="76" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Realtime Live Queries via WebSocket</text>
      <text x="20" y="94" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Keycloak JWT Claims-based Security</text>
      <text x="20" y="112" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Multi-Tenant Column &amp; Row Filtering</text>
      <text x="20" y="130" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Metadata v3 with Automated CI/CD Script</text>
      <rect x="18" y="145" width="239" height="38" rx="4" fill="#082936" stroke="#0891b2" stroke-width="0.8" />
      <text x="137" y="159" fill="#a5f3fc" font-family="monospace" font-size="8.5" text-anchor="middle">Port 8080 • GraphQL Endpoint</text>
      <text x="137" y="173" fill="#a5f3fc" font-family="monospace" font-size="8.5" text-anchor="middle">v_hr_employees_sanitized View</text>
    </g>

    <!-- Context Sync Worker & Anti-Loop Engine Card -->
    <g transform="translate(15, 460)" filter="url(#shadow-card)">
      <rect width="275" height="255" rx="10" fill="url(#card-highlight)" stroke="#f59e0b" stroke-width="1.6" />
      <circle cx="36" cy="35" r="16" fill="#78350f" fill-opacity="0.4" stroke="#f59e0b" stroke-width="1.2" />
      <!-- Sync Loop Icon -->
      <path d="M 28 35 C 28 31 31 28 36 28 C 40 28 43 31 43 35 L 45 35 M 44 42 C 41 45 31 45 28 38" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" fill="none" />
      <text x="64" y="32" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="bold">Context Sync Worker</text>
      <text x="64" y="47" fill="#fbbf24" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" font-weight="600">Transactional CDC &amp; Anti-Loop</text>
      <line x1="15" y1="58" x2="260" y2="58" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="76" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Polling &amp; Consuming context.outbox</text>
      <text x="20" y="93" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Transforms records to NGSI-LD Entities</text>
      <text x="20" y="110" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Dispatches to Redis Streams (maxlen 10k)</text>
      
      <!-- Anti-Loop Highlight Subcard -->
      <rect x="18" y="122" width="239" height="74" rx="6" fill="#1e1805" stroke="#d97706" stroke-width="1" />
      <text x="28" y="139" fill="#fde047" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10" font-weight="bold">🛡️ Anti-Sync Loop Protection</text>
      <text x="28" y="155" fill="#fef08a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9">• Webhook notifications update entity_state</text>
      <text x="28" y="170" fill="#fef08a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9">• Bypasses outbox write to break cycles</text>
      <text x="28" y="185" fill="#fef08a" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9">• Verified by end-to-end integration tests</text>

      <!-- DLQ & Resilience Bar -->
      <rect x="18" y="204" width="239" height="38" rx="4" fill="#0f172a" stroke="#f59e0b" stroke-width="0.8" />
      <text x="137" y="219" fill="#fed7aa" font-family="monospace" font-size="8.5" text-anchor="middle">DLQ Max 5 Retries • Exponential Backoff</text>
      <text x="137" y="233" fill="#fed7aa" font-family="monospace" font-size="8.5" text-anchor="middle">POST /api/v1/context/outbox/replay-dlq</text>
    </g>
  </g>

  <!-- ==================== ZONE 5: DATA, AI & PERSISTENCE ==================== -->
  <g transform="translate(1290, 90)">
    <!-- Zone Box -->
    <rect width="270" height="740" rx="14" fill="url(#zone-bg)" stroke="#334155" stroke-width="1" />
    <rect x="0" y="0" width="270" height="36" rx="14" fill="#1e293b" fill-opacity="0.6" />
    <text x="135" y="23" fill="#818cf8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="bold" letter-spacing="1" text-anchor="middle">💾 5. DATA, AI &amp; STORAGE</text>

    <!-- PostgreSQL Card -->
    <g transform="translate(15, 50)" filter="url(#shadow-soft)">
      <rect width="240" height="155" rx="10" fill="url(#card-bg)" stroke="#4169E1" stroke-opacity="0.6" stroke-width="1.5" />
      <rect x="20" y="18" width="32" height="32" rx="6" fill="#4169E1" fill-opacity="0.2" />
      <use href="#icon-postgresql" x="24" y="22" width="24" height="24" />
      <text x="62" y="34" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="bold">PostgreSQL 16</text>
      <text x="62" y="49" fill="#93c5fd" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">PostGIS Extension</text>
      <line x1="15" y1="60" x2="225" y2="60" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="78" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Multi-Tenant Schema RLS</text>
      <text x="20" y="96" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• context.outbox &amp; subscriptions</text>
      <text x="20" y="114" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Spatial Indices &amp; Geometry Data</text>
      <rect x="18" y="125" width="204" height="18" rx="3" fill="#081838" />
      <text x="120" y="137" fill="#bfdbfe" font-family="monospace" font-size="8.5" text-anchor="middle">Port 5432 • ACID Relational Core</text>
    </g>

    <!-- Redis 7 Stack Card -->
    <g transform="translate(15, 220)" filter="url(#shadow-soft)">
      <rect width="240" height="150" rx="10" fill="url(#card-bg)" stroke="#FF4438" stroke-opacity="0.6" stroke-width="1.3" />
      <rect x="20" y="18" width="32" height="32" rx="6" fill="#FF4438" fill-opacity="0.2" />
      <use href="#icon-redis" x="24" y="22" width="24" height="24" />
      <text x="62" y="34" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="bold">Redis 7 Stack</text>
      <text x="62" y="49" fill="#f87171" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">Event Bus &amp; Caching</text>
      <line x1="15" y1="60" x2="225" y2="60" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="78" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Redis Streams (maxlen 10,000)</text>
      <text x="20" y="96" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Distributed Pub/Sub Messaging</text>
      <text x="20" y="114" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• In-memory Cache &amp; Idempotency</text>
      <rect x="18" y="122" width="204" height="18" rx="3" fill="#2d0a0b" />
      <text x="120" y="134" fill="#fecaca" font-family="monospace" font-size="8.5" text-anchor="middle">Port 6379 • In-Memory Speed</text>
    </g>

    <!-- Qdrant Vector DB Card -->
    <g transform="translate(15, 385)" filter="url(#shadow-soft)">
      <rect width="240" height="150" rx="10" fill="url(#card-bg)" stroke="#DC2626" stroke-opacity="0.6" stroke-width="1.3" />
      <rect x="20" y="18" width="32" height="32" rx="6" fill="#DC2626" fill-opacity="0.2" />
      <use href="#icon-qdrant" x="24" y="22" width="24" height="24" />
      <text x="62" y="34" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="bold">Qdrant Vector DB</text>
      <text x="62" y="49" fill="#fca5a5" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">Vector Search Engine</text>
      <line x1="15" y1="60" x2="225" y2="60" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="78" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• High-dimensional Embeddings</text>
      <text x="20" y="96" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• RAG Knowledge Base Retrieval</text>
      <text x="20" y="114" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Multi-tenant Vector Collections</text>
      <rect x="18" y="122" width="204" height="18" rx="3" fill="#2d0d0d" />
      <text x="120" y="134" fill="#fee2e2" font-family="monospace" font-size="8.5" text-anchor="middle">Port 6333 • Semantic RAG</text>
    </g>

    <!-- Ollama Local LLM Card -->
    <g transform="translate(15, 550)" filter="url(#shadow-soft)">
      <rect width="240" height="175" rx="10" fill="url(#card-bg)" stroke="#cbd5e1" stroke-opacity="0.5" stroke-width="1.3" />
      <rect x="20" y="18" width="32" height="32" rx="6" fill="#000000" />
      <use href="#icon-ollama" x="24" y="22" width="24" height="24" />
      <text x="62" y="34" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="bold">Ollama / Local LLM</text>
      <text x="62" y="49" fill="#e2e8f0" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="600">On-Premise AI Models</text>
      <line x1="15" y1="60" x2="225" y2="60" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="78" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Llama-3, Qwen, Mistral Inference</text>
      <text x="20" y="96" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• 100% Offline / Data Sovereignty</text>
      <text x="20" y="114" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• OpenAI-compatible Local API</text>
      <text x="20" y="132" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">• Zero Cloud Data Leakage</text>
      <rect x="18" y="145" width="204" height="18" rx="3" fill="#1e293b" />
      <text x="120" y="157" fill="#f1f5f9" font-family="monospace" font-size="8.5" text-anchor="middle">Port 11434 • Private Inference</text>
    </g>
  </g>

  <!-- ==================== ZONE 6: OBSERVABILITY & DEPLOYMENT ==================== -->
  <g transform="translate(40, 850)">
    <!-- Zone Container -->
    <rect width="1520" height="150" rx="14" fill="url(#zone-bg)" stroke="#334155" stroke-width="1" />
    <rect x="0" y="0" width="1520" height="30" rx="14" fill="#1e293b" fill-opacity="0.6" />
    <text x="760" y="20" fill="#f59e0b" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="bold" letter-spacing="1" text-anchor="middle">📊 6. OBSERVABILITY, MONITORING &amp; DEPLOYMENT INFRASTRUCTURE</text>

    <!-- Card 6.1: Docker Compose -->
    <g transform="translate(25, 42)" filter="url(#shadow-soft)">
      <rect width="345" height="92" rx="8" fill="url(#card-bg)" stroke="#2496ED" stroke-opacity="0.6" stroke-width="1.2" />
      <rect x="15" y="16" width="30" height="30" rx="6" fill="#2496ED" fill-opacity="0.2" />
      <use href="#icon-docker" x="18" y="19" width="24" height="24" />
      <text x="56" y="30" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="bold">Docker Compose Orchestration</text>
      <text x="56" y="44" fill="#60a5fa" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">Multi-Service Container Runtime</text>
      <line x1="15" y1="52" x2="330" y2="52" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="68" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• 45 Orchestrated Microservices • Healthchecks</text>
      <text x="20" y="82" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Profiles: core, context, ai, monitoring • Dev/Prod</text>
    </g>

    <!-- Card 6.2: Prometheus -->
    <g transform="translate(395, 42)" filter="url(#shadow-soft)">
      <rect width="345" height="92" rx="8" fill="url(#card-bg)" stroke="#E6522C" stroke-opacity="0.6" stroke-width="1.2" />
      <rect x="15" y="16" width="30" height="30" rx="6" fill="#E6522C" fill-opacity="0.2" />
      <use href="#icon-prometheus" x="18" y="19" width="24" height="24" />
      <text x="56" y="30" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="bold">Prometheus Telemetry</text>
      <text x="56" y="44" fill="#fb923c" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">Time-Series Metrics Collection</text>
      <line x1="15" y1="52" x2="330" y2="52" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="68" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Scrapes FastAPI, Orion, Hasura &amp; Redis Metrics</text>
      <text x="20" y="82" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Tracks Outbox Lag, DLQ Counts &amp; API Latency</text>
    </g>

    <!-- Card 6.3: Grafana -->
    <g transform="translate(765, 42)" filter="url(#shadow-soft)">
      <rect width="345" height="92" rx="8" fill="url(#card-bg)" stroke="#F46800" stroke-opacity="0.6" stroke-width="1.2" />
      <rect x="15" y="16" width="30" height="30" rx="6" fill="#F46800" fill-opacity="0.2" />
      <use href="#icon-grafana" x="18" y="19" width="24" height="24" />
      <text x="56" y="30" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="bold">Grafana Dashboards</text>
      <text x="56" y="44" fill="#fdba74" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">Unified Real-time Visualization</text>
      <line x1="15" y1="52" x2="330" y2="52" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="68" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Layer 3 Context Broker Dashboard Included</text>
      <text x="20" y="82" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Real-time Alerting Rules &amp; Health Monitoring</text>
    </g>

    <!-- Card 6.4: Loki & Logging -->
    <g transform="translate(1135, 42)" filter="url(#shadow-soft)">
      <rect width="360" height="92" rx="8" fill="url(#card-bg)" stroke="#a855f7" stroke-opacity="0.6" stroke-width="1.2" />
      <circle cx="30" cy="31" r="15" fill="#581c87" fill-opacity="0.4" stroke="#c084fc" stroke-width="1" />
      <!-- Log Icon -->
      <path d="M 24 25 L 36 25 M 24 31 L 36 31 M 24 37 L 31 37" stroke="#c084fc" stroke-width="2" stroke-linecap="round" fill="none" />
      <text x="56" y="30" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="bold">Grafana Loki &amp; Promtail</text>
      <text x="56" y="44" fill="#d8b4fe" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10">Centralized Log Aggregation</text>
      <line x1="15" y1="52" x2="345" y2="52" stroke="#334155" stroke-width="0.8" />
      <text x="20" y="68" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Structured Log Shipping across all 45 containers</text>
      <text x="20" y="82" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9.5">• Correlated Trace IDs &amp; Incident Drill Runbooks</text>
    </g>
  </g>

  <!-- ==================== ANIMATED PACKETS (DATA FLOWS) ==================== -->
  <!-- Client -> Traefik -->
  <circle r="4" fill="#38bdf8" filter="url(#glow-cyan)">
    <animateMotion dur="1.8s" repeatCount="indefinite" path="M 170 240 L 170 300" />
  </circle>

  <!-- Traefik -> Next.js -->
  <circle r="4" fill="#38bdf8" filter="url(#glow-cyan)">
    <animateMotion dur="2.2s" repeatCount="indefinite" begin="0.3s" path="M 285 355 C 320 355, 320 220, 355 220" />
  </circle>

  <!-- Traefik -> FastAPI Core -->
  <circle r="4" fill="#2dd4bf" filter="url(#glow-emerald)">
    <animateMotion dur="2.5s" repeatCount="indefinite" begin="0.6s" path="M 285 355 C 450 355, 520 270, 645 270" />
  </circle>

  <!-- Next.js -> FastAPI Core -->
  <circle r="4" fill="#38bdf8" filter="url(#glow-cyan)">
    <animateMotion dur="1.5s" repeatCount="indefinite" begin="0.5s" path="M 590 220 C 615 220, 615 270, 645 270" />
  </circle>

  <!-- FastAPI -> PostgreSQL -->
  <circle r="4" fill="#60a5fa" filter="url(#glow-cyan)">
    <animateMotion dur="2s" repeatCount="indefinite" begin="0.2s" path="M 945 270 C 1100 270, 1180 230, 1305 230" />
  </circle>

  <!-- Outbox -> Context Sync Worker -->
  <circle r="4" fill="#f59e0b" filter="url(#glow-amber)">
    <animateMotion dur="2.2s" repeatCount="indefinite" begin="0.4s" path="M 1305 260 C 1180 260, 1160 630, 1245 630" />
  </circle>

  <!-- Context Sync Worker -> Orion-LD -->
  <circle r="4" fill="#10b981" filter="url(#glow-emerald)">
    <animateMotion dur="2s" repeatCount="indefinite" begin="0.8s" path="M 1115 600 C 1115 400, 1115 320, 1115 300" />
  </circle>

  <!-- Context Sync Worker -> Redis Streams -->
  <circle r="4" fill="#f43f5e" filter="url(#glow-rose)">
    <animateMotion dur="1.8s" repeatCount="indefinite" begin="1s" path="M 1245 660 C 1275 660, 1275 420, 1305 420" />
  </circle>

  <!-- Hasura -> PostgreSQL -->
  <circle r="4" fill="#38bdf8" filter="url(#glow-cyan)">
    <animateMotion dur="2.2s" repeatCount="indefinite" begin="0.7s" path="M 1245 440 C 1275 440, 1275 250, 1305 250" />
  </circle>

  <!-- FastAPI -> Qdrant -->
  <circle r="4" fill="#ef4444" filter="url(#glow-rose)">
    <animateMotion dur="2.4s" repeatCount="indefinite" begin="0.9s" path="M 945 450 C 1120 450, 1180 570, 1305 570" />
  </circle>

  <!-- FastAPI -> Ollama -->
  <circle r="4" fill="#ffffff" filter="url(#glow-purple)">
    <animateMotion dur="2.6s" repeatCount="indefinite" begin="1.2s" path="M 945 490 C 1120 490, 1180 740, 1305 740" />
  </circle>

  <!-- Keycloak -> Hasura Token Verification -->
  <circle r="3.5" fill="#a855f7" filter="url(#glow-purple)">
    <animateMotion dur="3s" repeatCount="indefinite" begin="0.5s" path="M 285 540 C 600 540, 800 460, 985 460" />
  </circle>
</svg>""")

full_svg = "".join(svg_parts)

output_path = os.path.join(REPO_ROOT, "docs", "images", "architecture_flow.svg")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(full_svg)

print(f"Successfully generated {output_path} ({len(full_svg)} bytes)")
