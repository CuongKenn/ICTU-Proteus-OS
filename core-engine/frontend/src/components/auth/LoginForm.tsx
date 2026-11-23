// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React, { useState } from "react";
import { signIn } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import { ShieldCheck, AlertCircle, ArrowRight, Lock } from "lucide-react";
import { useNotificationStore } from "@/store/notificationStore";
import { useLang } from "@/components/i18n/LanguageContext";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { LanguageToggle } from "@/components/i18n/LanguageToggle";
import Link from "next/link";

export const LoginForm: React.FC = () => {
  const searchParams = useSearchParams();
  const error = searchParams.get("error");
  const callbackUrl = searchParams.get("callbackUrl") || "/launchpad";
  const [isLoading, setIsLoading] = useState(false);
  const addToast = useNotificationStore((state) => state.addToast);
  const { t } = useLang();

  React.useEffect(() => {
    if (error === "RefreshAccessTokenError") {
      addToast("error", "Phiên làm việc hết hạn. Vui lòng đăng nhập lại.", 10000);
    } else if (error === "InvalidEmailDomain") {
      addToast("error", "Đăng nhập thất bại. Vui lòng sử dụng email @ictu.edu.vn.", 10000);
    } else if (error) {
      addToast("error", "Đăng nhập không thành công. Vui lòng thử lại.");
    }
  }, [error, addToast]);

  const handleLogin = async () => {
    setIsLoading(true);
    await signIn("keycloak", { callbackUrl });
  };

  return (
    <div className="min-h-screen flex flex-col bg-paper text-ink">
      {/* Header */}
      <header className="h-16 flex items-center justify-between px-6 border-b border-line bg-paper-raised">
        <Link href="/" className="flex items-center gap-2.5">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center font-heading font-bold text-white text-xs"
            style={{ background: "var(--accent-solid)" }}
          >
            P
          </div>
          <span className="font-heading text-base font-bold tracking-tight text-ink">
            Proteus <span className="text-accent">OS</span>
          </span>
        </Link>
        <div className="flex items-center gap-2">
          <LanguageToggle />
          <ThemeToggle />
        </div>
      </header>

      {/* Centered Enterprise SSO Card */}
      <main className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-[420px]">
          <div className="card p-8 sm:p-9">
            <div className="mb-7">
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center mb-5 border border-line"
                style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
              >
                <Lock className="w-5 h-5" />
              </div>
              <h1 className="text-2xl font-heading font-bold tracking-tight text-ink">
                {t("auth.welcome")}
              </h1>
              <p className="text-sm text-muted mt-1.5 leading-relaxed">
                {t("auth.login_desc")}
              </p>
            </div>

            {error === "RefreshAccessTokenError" && (
              <div
                className="mb-6 p-3.5 rounded-lg flex items-start gap-2.5 border"
                style={{
                  background: "var(--rose-fill)",
                  borderColor: "rgba(190, 18, 60, 0.25)",
                }}
              >
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-error" />
                <p className="text-xs leading-relaxed text-error font-medium">
                  Phiên làm việc đã hết hạn. Dữ liệu đang nhập dở sẽ được tự động khôi phục sau khi đăng nhập lại.
                </p>
              </div>
            )}

            <div className="space-y-4">
              <button
                type="button"
                onClick={handleLogin}
                disabled={isLoading}
                className="btn-accent btn-lg w-full justify-between group"
              >
                <span className="flex items-center gap-2.5">
                  <ShieldCheck className="w-4 h-4" />
                  {t("auth.login_sso")}
                </span>
                {isLoading ? (
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
                )}
              </button>

              <p className="text-center text-xs text-dim pt-1">
                {t("auth.protected")}
              </p>
            </div>

            <div className="mt-7 pt-5 border-t border-line text-center text-sm text-muted">
              Chưa có không gian tổ chức?{" "}
              <Link href="/signup" className="font-medium text-accent hover:underline">
                {t("nav.signup")}
              </Link>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};
