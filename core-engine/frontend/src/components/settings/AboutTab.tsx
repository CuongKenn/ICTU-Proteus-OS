// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React, { useEffect, useState } from "react";
import { Server, CheckCircle2, XCircle, ExternalLink } from "lucide-react";

interface ServiceHealth {
  name: string;
  status: "healthy" | "unhealthy" | "checking";
}

export const AboutTab = () => {
  const [services, setServices] = useState<ServiceHealth[]>([
    { name: "Frontend (Next.js BFF)", status: "checking" },
    { name: "Backend (FastAPI Core Engine)", status: "checking" },
  ]);

  useEffect(() => {
    setServices((prev) =>
      prev.map((s) => (s.name.startsWith("Frontend") ? { ...s, status: "healthy" } : s))
    );

    fetch("/api/proxy/health")
      .then((res) => {
        setServices((prev) =>
          prev.map((s) =>
            s.name.startsWith("Backend")
              ? { ...s, status: res.ok ? "healthy" : "unhealthy" }
              : s
          )
        );
      })
      .catch(() => {
        setServices((prev) =>
          prev.map((s) => (s.name.startsWith("Backend") ? { ...s, status: "unhealthy" } : s))
        );
      });
  }, []);

  return (
    <div className="space-y-7 animate-fade-in">
      <div className="pb-5 border-b border-line">
        <h2 className="text-lg font-heading font-semibold text-ink">Thông tin hệ thống</h2>
        <p className="text-sm text-muted mt-1">
          Phiên bản nền tảng, giấy phép nguồn mở và trạng thái các dịch vụ lõi.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-5 p-5 border border-line bg-paper-subtle/50 rounded-xl">
        <div className="flex items-center gap-4">
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center text-white font-heading font-bold text-xl shrink-0"
            style={{ background: "var(--accent-solid)" }}
          >
            P
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h3 className="text-base font-heading font-bold text-ink">Proteus OS</h3>
              <span className="font-mono text-xs font-medium px-2 py-0.5 rounded bg-accent/10 text-accent">
                v1.0.3
              </span>
            </div>
            <p className="mt-1 text-xs text-muted max-w-md leading-relaxed">
              Hệ điều hành Chuyển đổi số Lõi mở (DX-OS Open-Core) tích hợp Keycloak, PostgreSQL RLS, n8n, Metabase, Mattermost và Agentic AI.
            </p>
          </div>
        </div>
        <a
          href="https://github.com/CuongKenn/ICTU_Proteus-os"
          target="_blank"
          rel="noreferrer"
          className="btn-ghost btn-sm shrink-0"
        >
          Mã nguồn GitHub
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-ink mb-3 flex items-center gap-2">
          <Server className="w-4 h-4 text-accent" /> Trạng thái dịch vụ lõi
        </h3>
        <div className="divide-y divide-line border border-line rounded-xl overflow-hidden bg-paper-white">
          {services.map((service) => (
            <div
              key={service.name}
              className="flex items-center justify-between px-4 py-3"
            >
              <span className="text-sm font-medium text-ink">{service.name}</span>
              <div>
                {service.status === "checking" && (
                  <span className="text-xs text-dim animate-pulse">Đang kiểm tra...</span>
                )}
                {service.status === "healthy" && (
                  <span className="status-badge status-badge--active">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Hoạt động ổn định
                  </span>
                )}
                {service.status === "unhealthy" && (
                  <span className="status-badge status-badge--failed">
                    <XCircle className="w-3.5 h-3.5" /> Mất kết nối
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="pt-4 border-t border-line">
        <h3 className="text-sm font-semibold text-ink mb-1.5">Giấy phép &amp; Bản quyền</h3>
        <p className="text-xs text-muted leading-relaxed">
          Phát hành theo giấy phép nguồn mở <strong className="text-ink">GNU AGPL-3.0-or-later</strong>.
          <br />
          Copyright © 2026 CuongKenn &amp; ICTU Team.
        </p>
      </div>
    </div>
  );
};
