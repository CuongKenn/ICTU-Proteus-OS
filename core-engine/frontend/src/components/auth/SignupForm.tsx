// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Building2, Mail, Lock, User, ArrowRight, Loader2, AlertCircle } from "lucide-react";
import Link from "next/link";
import { useLang } from "@/components/i18n/LanguageContext";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { LanguageToggle } from "@/components/i18n/LanguageToggle";
import { extractErrorMessage } from "@/lib/api";

export function SignupForm() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { t } = useLang();

  const [formData, setFormData] = useState({
    companyName: "",
    adminFullName: "",
    email: "",
    password: "",
    confirmPassword: "",
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (formData.password !== formData.confirmPassword) {
      setError("Mật khẩu xác nhận không khớp.");
      return;
    }

    if (formData.password.length < 8) {
      setError("Mật khẩu phải có ít nhất 8 ký tự.");
      return;
    }

    if (!/[A-Z]/.test(formData.password)) {
      setError("Mật khẩu phải có ít nhất 1 chữ hoa.");
      return;
    }

    if (!/[a-z]/.test(formData.password)) {
      setError("Mật khẩu phải có ít nhất 1 chữ thường.");
      return;
    }

    if (!/[0-9]/.test(formData.password)) {
      setError("Mật khẩu phải có ít nhất 1 chữ số.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/onboarding/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company_name: formData.companyName,
          admin_full_name: formData.adminFullName,
          admin_email: formData.email,
          admin_password: formData.password,
        }),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(extractErrorMessage(data.error || data.detail || data, "Đăng ký thất bại"));
      }
      router.push("/login?signup_success=1");
    } catch (err: any) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
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

      {/* Centered Form */}
      <main className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-[460px]">
          <div className="card p-8 sm:p-9">
            <div className="mb-7">
              <h1 className="text-2xl font-heading font-bold tracking-tight text-ink">
                {t("auth.signup_title")}
              </h1>
              <p className="text-sm text-muted mt-1.5">
                Khởi tạo không gian làm việc đa thuê ước cho tổ chức của bạn.
              </p>
            </div>

            {error && (
              <div
                className="mb-5 p-3.5 rounded-lg text-sm flex items-start gap-2.5 border"
                style={{
                  background: "var(--rose-fill)",
                  borderColor: "rgba(190, 18, 60, 0.25)",
                  color: "var(--rose)",
                }}
              >
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="companyName" className="block text-[13px] font-medium text-ink-soft">
                  {t("auth.company")}
                </label>
                <div className="relative">
                  <Building2 className="h-4 w-4 text-dim absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <input
                    id="companyName"
                    type="text"
                    name="companyName"
                    value={formData.companyName}
                    onChange={handleChange}
                    required
                    className="input-field input-field-icon"
                    placeholder="VD: Công ty Cổ phần ICTU"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="adminFullName" className="block text-[13px] font-medium text-ink-soft">
                  {t("auth.admin_name")}
                </label>
                <div className="relative">
                  <User className="h-4 w-4 text-dim absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <input
                    id="adminFullName"
                    type="text"
                    name="adminFullName"
                    value={formData.adminFullName}
                    onChange={handleChange}
                    required
                    className="input-field input-field-icon"
                    placeholder="Nguyễn Văn A"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="email" className="block text-[13px] font-medium text-ink-soft">
                  {t("auth.email")}
                </label>
                <div className="relative">
                  <Mail className="h-4 w-4 text-dim absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <input
                    id="email"
                    type="email"
                    name="email"
                    value={formData.email}
                    onChange={handleChange}
                    required
                    className="input-field input-field-icon"
                    placeholder="admin@doanhnghiep.vn"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <div className="space-y-1.5">
                  <label htmlFor="password" className="block text-[13px] font-medium text-ink-soft">
                    {t("auth.password")}
                  </label>
                  <div className="relative">
                    <Lock className="h-4 w-4 text-dim absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      id="password"
                      type="password"
                      name="password"
                      value={formData.password}
                      onChange={handleChange}
                      required
                      minLength={8}
                      className="input-field input-field-icon"
                      placeholder="••••••••"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="confirmPassword" className="block text-[13px] font-medium text-ink-soft">
                    {t("auth.confirm_password")}
                  </label>
                  <div className="relative">
                    <Lock className="h-4 w-4 text-dim absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      id="confirmPassword"
                      type="password"
                      name="confirmPassword"
                      value={formData.confirmPassword}
                      onChange={handleChange}
                      required
                      minLength={8}
                      className="input-field input-field-icon"
                      placeholder="••••••••"
                    />
                  </div>
                </div>
              </div>

              <p className="text-xs text-dim">
                Mật khẩu cần tối thiểu 8 ký tự gồm chữ hoa, chữ thường và chữ số.
              </p>

              <button type="submit" disabled={loading} className="btn-accent btn-lg w-full mt-2 group">
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    {t("auth.signup_btn")}
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
                  </>
                )}
              </button>
            </form>

            <div className="mt-6 pt-5 border-t border-line text-center text-sm text-muted">
              {t("auth.has_account")}{" "}
              <Link href="/login" className="font-medium text-accent hover:underline">
                {t("nav.login")}
              </Link>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
