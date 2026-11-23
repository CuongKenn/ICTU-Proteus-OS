// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React, { useEffect, useRef } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Users,
  Workflow,
  Database,
  Cpu,
  ShieldCheck,
  BarChart3,
  Activity,
  Lock,
  Check,
  ExternalLink,
} from "lucide-react";
import { useLang } from "@/components/i18n/LanguageContext";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { LanguageToggle } from "@/components/i18n/LanguageToggle";

/* ===== Subtle reveal on scroll (respects reduced motion) ===== */
function useFadeUp() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const targets = el.querySelectorAll(".fade-up");
    const observer = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("visible");
            observer.unobserve(e.target);
          }
        }),
      { threshold: 0.05, rootMargin: "40px 0px" }
    );
    targets.forEach((t) => observer.observe(t));
    const fallback = setTimeout(
      () => targets.forEach((t) => t.classList.add("visible")),
      400
    );
    return () => {
      observer.disconnect();
      clearTimeout(fallback);
    };
  }, []);
  return ref;
}

export function LandingPage() {
  const { t } = useLang();
  const containerRef = useFadeUp();

  const pillars = [
    {
      code: "H",
      tag: "Human · Con người số",
      title: t("features.h.title"),
      desc: t("features.h.desc"),
      icon: Users,
      chips: ["Keycloak SSO", "Mattermost", "Outline Wiki"],
      accentText: "var(--accent)",
      accentBg: "var(--accent-soft)",
    },
    {
      code: "P",
      tag: "Process · Quy trình số",
      title: t("features.p.title"),
      desc: t("features.p.desc"),
      icon: Workflow,
      chips: ["n8n Workflow", "Appsmith Low-code", "Poka-yoke"],
      accentText: "var(--emerald)",
      accentBg: "var(--emerald-fill)",
    },
    {
      code: "D",
      tag: "Data · Dữ liệu thực chứng",
      title: t("features.d.title"),
      desc: t("features.d.desc"),
      icon: Database,
      chips: ["PostgreSQL RLS", "Metabase BI", "Qdrant Vector"],
      accentText: "var(--amber)",
      accentBg: "var(--amber-fill)",
    },
    {
      code: "I",
      tag: "Intelligence · Trí tuệ tự hành",
      title: t("features.i.title"),
      desc: t("features.i.desc"),
      icon: Cpu,
      chips: ["RAG Hybrid Search", "DX-DSL + Z3", "Human-in-the-loop"],
      accentText: "var(--violet)",
      accentBg: "var(--violet-fill)",
    },
  ];

  const aiModes = [
    {
      icon: BarChart3,
      title: t("ai.rag.title"),
      desc: "Hỏi-đáp dựa trên tài liệu nội bộ thông qua Qdrant Hybrid Search (Dense + BM25), trả lời có trích dẫn nguồn gốc rõ ràng.",
      badge: "Chỉ đọc (Read-only)",
      badgeClass: "status-badge status-badge--active",
    },
    {
      icon: Activity,
      title: t("ai.monitor.title"),
      desc: "Giám sát 24/7 dữ liệu vận hành trên PostgreSQL, tự động phát hiện điểm nghẽn SLA và gửi cảnh báo về kênh quản lý.",
      badge: "Báo cáo chủ động",
      badgeClass: "status-badge status-badge--warning",
    },
    {
      icon: ShieldCheck,
      title: t("ai.exec.title"),
      desc: "Chuyển đổi yêu cầu ngôn ngữ tự nhiên thành lệnh chuẩn DX-DSL, kiểm chứng tĩnh bằng Z3 và trình phê duyệt trước khi thực thi.",
      badge: "Yêu cầu phê duyệt",
      badgeClass: "status-badge status-badge--failed",
    },
  ];

  return (
    <div ref={containerRef} className="min-h-screen bg-paper text-ink overflow-x-hidden">
      {/* ===== NAVBAR ===== */}
      <nav className="sticky top-0 z-50 bg-paper-raised/90 border-b border-line backdrop-blur-md">
        <div className="w-full max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Brand + Nav Links */}
            <div className="flex items-center gap-8">
              <Link href="/" className="flex items-center gap-2.5">
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center font-heading font-bold text-white text-sm shadow-sm"
                  style={{ background: "var(--accent-solid)" }}
                >
                  P
                </div>
                <span className="font-heading text-[17px] font-bold tracking-tight text-ink">
                  Proteus <span className="text-accent">OS</span>
                </span>
              </Link>

              <div className="hidden md:flex items-center gap-6">
                <a
                  href="#features"
                  className="text-sm font-medium text-muted hover:text-ink transition-colors"
                >
                  {t("nav.features")}
                </a>
                <a
                  href="#ai"
                  className="text-sm font-medium text-muted hover:text-ink transition-colors"
                >
                  {t("nav.ai")}
                </a>
                <a
                  href="https://github.com/CuongKenn/ICTU_Proteus-os/tree/main/docs"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm font-medium text-muted hover:text-ink transition-colors"
                >
                  {t("nav.docs")}
                  <ExternalLink className="w-3.5 h-3.5 opacity-60" />
                </a>
              </div>
            </div>

            {/* Right Controls */}
            <div className="flex items-center gap-2.5">
              <LanguageToggle />
              <ThemeToggle />
              <Link href="/login" className="btn-ghost hidden sm:inline-flex">
                {t("nav.login")}
              </Link>
              <Link href="/signup" className="btn-accent hidden sm:inline-flex">
                {t("nav.signup")}
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* ===== HERO SECTION ===== */}
      <section className="relative pt-14 md:pt-20 pb-16 md:pb-24 px-4 sm:px-6 lg:px-8">
        <div className="grid-bg" />

        <div className="relative max-w-[1200px] mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-center">
            {/* Left Copy */}
            <div className="lg:col-span-7 flex flex-col items-start">
              <div className="fade-up mono-tag mb-6">
                <span className="pulse-dot" />
                <span>{t("hero.badge")}</span>
              </div>

              <h1 className="fade-up d1 font-heading font-bold text-hero text-ink mb-5">
                {t("hero.title1")}{" "}
                <span className="text-accent">{t("hero.title2")}</span>{" "}
                {t("hero.title3")}
              </h1>

              <p className="fade-up d2 text-base leading-relaxed text-muted max-w-xl mb-8">
                {t("hero.desc")}
              </p>

              <div className="fade-up d3 flex flex-wrap items-center gap-3">
                <Link href="/signup" className="btn-accent btn-lg">
                  {t("hero.cta1")}
                  <ArrowRight className="w-4 h-4" />
                </Link>
                <a
                  href="https://github.com/CuongKenn/ICTU_Proteus-os"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-ghost btn-lg"
                >
                  {t("hero.cta2")}
                </a>
              </div>

              {/* Compact Trust Capabilities */}
              <div className="fade-up d4 mt-8 pt-6 border-t border-line flex flex-wrap items-center gap-x-6 gap-y-2 text-xs font-medium text-muted">
                <span className="inline-flex items-center gap-1.5">
                  <Check className="w-3.5 h-3.5 text-success" /> GNU AGPLv3 Open-Core
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <Check className="w-3.5 h-3.5 text-success" /> Multi-Tenant PostgreSQL RLS
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <Check className="w-3.5 h-3.5 text-success" /> Zero-Trust Keycloak SSO
                </span>
              </div>
            </div>

            {/* Right: Provisioning Console Preview */}
            <div className="lg:col-span-5 fade-up d2 hidden md:block">
              <div
                className="rounded-xl overflow-hidden border shadow-elevated"
                style={{ background: "var(--plate)", borderColor: "var(--plate-border)" }}
              >
                <div
                  className="flex items-center justify-between px-4 py-3 border-b"
                  style={{ background: "var(--plate-soft)", borderColor: "var(--plate-border)" }}
                >
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-slate-500/50" />
                    <span className="w-2.5 h-2.5 rounded-full bg-slate-500/50" />
                    <span className="w-2.5 h-2.5 rounded-full bg-slate-500/50" />
                  </div>
                  <span className="font-mono text-xs text-slate-400">
                    proteus-cli · tenant-provision
                  </span>
                  <span className="text-[11px] font-mono text-emerald-400">ready</span>
                </div>

                <div className="p-5 font-mono text-[12.5px] leading-7 text-slate-300 space-y-1">
                  <div>
                    <span className="text-slate-500 select-none">$ </span>
                    <span className="text-sky-400">proteus</span>{" "}
                    <span>deploy --tenant acme-corp --profile enterprise</span>
                  </div>
                  <div className="pt-1 text-emerald-400">
                    [ok] Keycloak SSO realm &amp; RBAC synced
                  </div>
                  <div className="text-emerald-400">
                    [ok] PostgreSQL schema &amp; FORCE RLS active
                  </div>
                  <div className="text-emerald-400">
                    [ok] Mattermost workspace &amp; Outline KB ready
                  </div>
                  <div className="text-emerald-400">
                    [ok] n8n workflows &amp; Metabase BI mounted
                  </div>
                  <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs">
                    <span className="inline-flex items-center gap-2 text-amber-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      AI Orchestrator (Z3 Verified): online
                    </span>
                  </div>
                  <div className="text-sky-400 text-xs">
                    Endpoint: https://acme.proteus.local/launchpad
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===== METRICS BAR ===== */}
      <div className="border-y border-line bg-paper-raised">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-6 md:gap-8">
            {[
              { number: "18+", label: t("stats.api") },
              { number: "9", label: "Phân hệ nghiệp vụ" },
              { number: "10+", label: t("stats.tools") },
              { number: "3", label: t("stats.modes") },
              { number: "100%", label: t("stats.docker") },
            ].map((stat, i) => (
              <div key={i} className="text-center md:text-left md:border-l md:first:border-l-0 md:pl-6 md:first:pl-0 border-line">
                <div className="text-2xl font-heading font-bold text-ink tabular-nums">
                  {stat.number}
                </div>
                <div className="text-xs font-medium text-muted mt-1">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ===== H-P-D-I ARCHITECTURE SECTION ===== */}
      <section
        id="features"
        className="px-4 sm:px-6 lg:px-8"
        style={{ paddingTop: "var(--section-pad)", paddingBottom: "var(--section-pad)" }}
      >
        <div className="max-w-[1200px] mx-auto">
          <div className="max-w-2xl mb-12 fade-up">
            <h2 className="text-2xl md:text-3xl font-heading font-bold tracking-tight text-ink mb-3">
              {t("features.title")}
            </h2>
            <p className="text-[15px] leading-relaxed text-muted">{t("features.desc")}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {pillars.map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.code} className="card p-6 md:p-7 fade-up">
                  <div className="flex items-center justify-between mb-4">
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center border border-line"
                      style={{ background: item.accentBg, color: item.accentText }}
                    >
                      <Icon className="w-5 h-5" strokeWidth={1.75} />
                    </div>
                    <span
                      className="text-xs font-semibold px-2.5 py-1 rounded-md"
                      style={{ background: item.accentBg, color: item.accentText }}
                    >
                      {item.tag}
                    </span>
                  </div>

                  <h3 className="text-lg font-heading font-semibold text-ink mb-2">
                    {item.title}
                  </h3>
                  <p className="text-sm leading-relaxed text-muted mb-5 flex-1">
                    {item.desc}
                  </p>

                  <div className="flex flex-wrap gap-2 pt-4 border-t border-line">
                    {item.chips.map((chip) => (
                      <span key={chip} className="tag-chip">
                        {chip}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ===== AI GOVERNANCE SECTION ===== */}
      <section
        id="ai"
        className="border-t border-line bg-paper-raised px-4 sm:px-6 lg:px-8"
        style={{ paddingTop: "var(--section-pad)", paddingBottom: "var(--section-pad)" }}
      >
        <div className="max-w-[1200px] mx-auto">
          <div className="max-w-2xl mb-12 fade-up">
            <h2 className="text-2xl md:text-3xl font-heading font-bold tracking-tight text-ink mb-3">
              {t("ai.title")}
            </h2>
            <p className="text-[15px] leading-relaxed text-muted">{t("ai.desc")}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 fade-up">
            {aiModes.map((mode) => {
              const Icon = mode.icon;
              return (
                <div key={mode.title} className="card p-6 fade-up">
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center mb-4 border border-line"
                    style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
                  >
                    <Icon className="w-5 h-5" strokeWidth={1.75} />
                  </div>
                  <h3 className="text-base font-heading font-semibold text-ink mb-2">
                    {mode.title}
                  </h3>
                  <p className="text-sm leading-relaxed text-muted mb-5 flex-1">
                    {mode.desc}
                  </p>
                  <div>
                    <span className={mode.badgeClass}>{mode.badge}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Human-in-the-Loop Governance Notice */}
          <div className="card p-5 mt-6 flex flex-row items-start gap-3.5 bg-paper border-line-hi fade-up">
            <div
              className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
              style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
            >
              <Lock className="w-4 h-4" />
            </div>
            <div className="text-sm leading-relaxed text-muted">
              <strong className="text-ink font-semibold">
                Cơ chế kiểm soát Human-in-the-Loop:{" "}
              </strong>
              {t("ai.hitl")}
            </div>
          </div>
        </div>
      </section>

      {/* ===== FOOTER ===== */}
      <footer className="border-t border-line bg-paper">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-dim">
          <div className="flex items-center gap-2.5">
            <div
              className="w-6 h-6 rounded-md flex items-center justify-center text-white text-[11px] font-bold font-heading"
              style={{ background: "var(--accent-solid)" }}
            >
              P
            </div>
            <span>© 2026 CuongKenn &amp; ICTU Team · Giấy phép GNU AGPL-3.0-or-later</span>
          </div>
          <div className="flex items-center gap-6">
            <a
              href="https://github.com/CuongKenn/ICTU_Proteus-os/blob/main/LICENSE"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-ink transition-colors"
            >
              {t("footer.terms")}
            </a>
            <a
              href="https://github.com/CuongKenn/ICTU_Proteus-os/blob/main/docs/LICENSE_NOTICE.md"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-ink transition-colors"
            >
              {t("footer.privacy")}
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
