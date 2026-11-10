// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { UserPlus, UserMinus, Loader2, AlertTriangle, CheckCircle2 } from "lucide-react";
import api, { extractErrorMessage } from "@/lib/api";
import { logger } from "@/lib/logger";

interface User {
  id: string;
  tenant_id: string;
  keycloak_id: string | null;
  email: string;
  full_name: string | null;
  roles: string[];
  is_active: boolean;
  last_login_at: string | null;
}


interface Role {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
}

export const UsersTab = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Invite modal state
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteFullName, setInviteFullName] = useState("");
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState(false);

  // Assign role modal state
  const [isRoleModalOpen, setIsRoleModalOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [initialRoleIds, setInitialRoleIds] = useState<string[]>([]);
  const [assigning, setAssigning] = useState(false);

  // Global action messages
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [resendingId, setResendingId] = useState<string | null>(null);

  const clearMessages = () => {
    setActionSuccess(null);
    setActionError(null);
  };

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [usersRes, rolesRes] = await Promise.all([
        api.get("/v1/users"),
        api.get("/v1/roles"),
      ]);
      setUsers(Array.isArray(usersRes.data) ? usersRes.data : []);
      setRoles(Array.isArray(rolesRes.data) ? rolesRes.data : []);
    } catch (err) {
      logger.error("Failed to fetch users/roles", err);
      setError(extractErrorMessage(err, "Không thể tải danh sách người dùng. Vui lòng thử lại."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleInvite = async () => {
    if (!inviteEmail || !inviteFullName) return;
    setInviting(true);
    setInviteError(null);
    clearMessages();
    try {
      const res = await api.post("/v1/users/invite", {
        email: inviteEmail,
        full_name: inviteFullName,
      });
      if (res.data?.email_sent === false) {
        setActionError("Người dùng đã được tạo, nhưng không thể gửi email kích hoạt (SMTP chưa cấu hình hoặc lỗi gửi mail). Hãy cấu hình SMTP hoặc gửi lại lời mời.");
      } else {
        setActionSuccess("Đã gửi email mời nhân viên thành công!");
      }
      setInviteSuccess(true);
      await fetchData(); // Refresh list
      setTimeout(() => {
        setIsInviteModalOpen(false);
        setInviteSuccess(false);
        setInviteEmail("");
        setInviteFullName("");
      }, 2000);
    } catch (err: any) {
      const detail = extractErrorMessage(err, "Có lỗi xảy ra khi gửi lời mời.");
      setInviteError(detail);
    } finally {
      setInviting(false);
    }
  };

  const handleResendInvite = async (userId: string) => {
    setResendingId(userId);
    clearMessages();
    try {
      const res = await api.post(`/v1/users/${userId}/resend-invite`);
      if (res.data?.email_sent === false) {
        setActionError("Gửi lại lời mời thất bại do lỗi SMTP.");
      } else {
        setActionSuccess("Đã gửi lại email kích hoạt thành công!");
      }
    } catch (err: any) {
      const detail = extractErrorMessage(err, "Không thể gửi lại email kích hoạt.");
      setActionError(detail);
    } finally {
      setResendingId(null);
    }
  };

  const handleDeactivate = async (userId: string) => {
    if (!confirm("Bạn có chắc muốn vô hiệu hóa tài khoản này? Họ sẽ mất quyền truy cập ngay lập tức.")) return;
    clearMessages();
    try {
      await api.patch(`/v1/users/${userId}/deactivate`);
      setUsers((prev) => prev.map((u) => u.id === userId ? { ...u, is_active: false } : u));
      setActionSuccess("Vô hiệu hóa tài khoản thành công!");
    } catch (err: any) {
      const detail = extractErrorMessage(err, "Không thể vô hiệu hóa tài khoản.");
      setActionError(detail);
    }
  };

  const openRoleModal = (user: User) => {
    setSelectedUser(user);
    const userRoleIds = roles
      .filter((r) => user.roles?.includes(r.name) || user.roles?.includes(r.display_name))
      .map((r) => r.id);
    setSelectedRoleIds(userRoleIds);
    setInitialRoleIds(userRoleIds);
    setIsRoleModalOpen(true);
  };

  const handleSaveRoles = async () => {
    if (!selectedUser) return;
    setAssigning(true);
    clearMessages();
    try {
      // Find roles to assign and roles to revoke
      const toAssign = selectedRoleIds.filter((id) => !initialRoleIds.includes(id));
      const toRevoke = initialRoleIds.filter((id) => !selectedRoleIds.includes(id));

      for (const roleId of toAssign) {
        await api.post(`/v1/roles/${roleId}/assign`, {
          user_id: selectedUser.id,
        });
      }
      for (const roleId of toRevoke) {
        await api.post(`/v1/roles/${roleId}/revoke`, {
          user_id: selectedUser.id,
        });
      }

      setIsRoleModalOpen(false);
      setActionSuccess(`Cập nhật Roles thành công cho ${selectedUser.full_name || selectedUser.email}!`);
      fetchData();
    } catch (err: any) {
      setActionError(extractErrorMessage(err, "Không thể cập nhật role."));
    } finally {
      setAssigning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-text-secondary mt-4">Đang tải danh sách người dùng...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <AlertTriangle className="w-10 h-10 text-error" />
        <p className="text-error">{error}</p>
        <Button variant="secondary" onClick={fetchData}>Thử lại</Button>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-xl font-semibold text-text-primary">Quản lý Người Dùng</h2>
          <p className="text-sm text-text-secondary">
            Danh sách tài khoản, phân quyền và trạng thái hoạt động trong Tenant của bạn.
          </p>
        </div>
        <Button onClick={() => setIsInviteModalOpen(true)} className="shrink-0 gap-2">
          <UserPlus className="w-4 h-4" />
          Mời nhân viên
        </Button>
      </div>

      {actionError && (
        <div className="bg-error/10 border border-error text-error px-4 py-3 rounded-lg flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 shrink-0" />
          <p className="text-sm">{actionError}</p>
        </div>
      )}
      
      {actionSuccess && (
        <div className="bg-success/10 border border-success text-success px-4 py-3 rounded-lg flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 shrink-0" />
          <p className="text-sm">{actionSuccess}</p>
        </div>
      )}

      <div className="bg-bg-surface/50 border border-border rounded-xl overflow-hidden backdrop-blur-glass">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-border bg-bg-surface/30">
                <th className="py-3 px-4 text-sm font-medium text-text-secondary">Tên & Email</th>
                <th className="py-3 px-4 text-sm font-medium text-text-secondary">Vai trò</th>
                <th className="py-3 px-4 text-sm font-medium text-text-secondary">Trạng thái</th>

                <th className="py-3 px-4 text-sm font-medium text-text-secondary text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {!Array.isArray(users) || users.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-12 text-center text-text-secondary">
                    Chưa có nhân viên nào. Bấm &quot;Mời nhân viên&quot; để bắt đầu.

                  </td>
                </tr>
              ) : (
                users.map((user) => (
                  <tr key={user.id} className="hover:bg-bg-hover/50 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-medium text-text-primary">{user.full_name || "(Chưa đặt tên)"}</div>
                      <div className="text-sm text-text-secondary">{user.email}</div>
                    </td>
                    <td className="py-3 px-4">
                      {user.roles && user.roles.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {user.roles.map((role, idx) => (
                            <span key={idx} className="px-2 py-0.5 text-xs rounded-full bg-primary/10 text-primary font-medium">
                              {role}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-sm text-text-secondary italic">Chưa có</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {user.is_active ? (
                        <span className="px-2 py-1 text-xs rounded-md font-medium bg-green-500/10 text-green-400">
                          Đang hoạt động
                        </span>
                      ) : !user.last_login_at ? (
                        <span className="px-2 py-1 text-xs rounded-md font-medium bg-amber-500/10 text-amber-400">
                          Chờ kích hoạt
                        </span>
                      ) : (
                        <span className="px-2 py-1 text-xs rounded-md font-medium bg-red-500/10 text-red-400">
                          Vô hiệu hóa
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right space-x-2">
                      {(user.is_active || !user.last_login_at) && (
                        <Button
                          variant="secondary"
                          className="px-3 py-1.5 text-sm"
                          onClick={() => openRoleModal(user)}
                        >
                          Gán Role
                        </Button>
                      )}
                      {!user.is_active && !user.last_login_at && (
                        <Button
                          variant="secondary"
                          className="px-3 py-1.5 text-sm"
                          disabled={resendingId === user.id}
                          onClick={() => handleResendInvite(user.id)}
                        >
                          {resendingId === user.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            "Gửi lại lời mời"
                          )}
                        </Button>
                      )}
                      {user.is_active && (
                        <Button
                          variant="danger"
                          className="px-3 py-1.5 text-sm"
                          onClick={() => handleDeactivate(user.id)}
                        >
                          <UserMinus className="w-4 h-4" />
                        </Button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Invite Modal */}
      <Modal 
        isOpen={isInviteModalOpen} 
        onClose={() => {
          setIsInviteModalOpen(false);
          setInviteError(null);
          setInviteSuccess(false);
          setInviteEmail("");
          setInviteFullName("");
        }} 
        title="Mời nhân viên mới"
        onConfirm={!inviteSuccess ? handleInvite : undefined}
        confirmLabel="Gửi lời mời"
        isConfirmLoading={inviting}
      >
        {inviteSuccess ? (
          <div className="flex flex-col items-center gap-4 py-6">
            <CheckCircle2 className="w-12 h-12 text-success" />
            <p className="text-center text-text-primary font-medium">
              Email mời đã được gửi!
            </p>
            <p className="text-center text-sm text-text-secondary">
              Nhân viên sẽ nhận được email để tự đặt mật khẩu và đăng nhập.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-text-secondary">
              Nhân viên sẽ nhận được email với đường link để tự đặt mật khẩu và kích hoạt tài khoản.
            </p>
            {inviteError && (
              <div className="p-3 bg-error/10 text-error rounded-lg border border-error/20 text-sm">
                {inviteError}
              </div>
            )}
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-text-primary mb-1">
                  Họ và tên
                </label>
                <input
                  type="text"
                  placeholder="Nguyễn Văn A"
                  value={inviteFullName}
                  onChange={(e) => setInviteFullName(e.target.value)}
                  className="w-full bg-bg-surface border border-border rounded-lg px-4 py-2 text-text-primary focus:outline-none focus:border-primary transition-colors"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-primary mb-1">
                  Email công ty
                </label>
                <input
                  type="email"
                  placeholder="email@example.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="w-full bg-bg-surface border border-border rounded-lg px-4 py-2 text-text-primary focus:outline-none focus:border-primary transition-colors"
                />
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Assign / Revoke Role Modal */}
      <Modal 
        isOpen={isRoleModalOpen} 
        onClose={() => setIsRoleModalOpen(false)} 
        title="Quản lý Roles của Người Dùng"
        onConfirm={handleSaveRoles}
        confirmLabel="Lưu thay đổi"
        isConfirmLoading={assigning}
      >
        <div className="space-y-4">
          <p className="text-sm text-text-secondary">
            Đang cấu hình phân quyền cho: <strong className="text-text-primary">{selectedUser?.full_name || selectedUser?.email}</strong>
          </p>
          {roles.length === 0 ? (
            <p className="text-text-secondary text-sm">Chưa có Role nào. Hãy tạo Role tại tab Roles trước.</p>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {roles.map((role) => {
                const isChecked = selectedRoleIds.includes(role.id);
                return (
                  <label key={role.id} className="flex items-center gap-3 p-3 rounded-lg border border-border bg-bg-surface/30 cursor-pointer hover:bg-bg-hover transition-colors">
                    <input
                      type="checkbox"
                      value={role.id}
                      checked={isChecked}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedRoleIds((prev) => [...prev, role.id]);
                        } else {
                          setSelectedRoleIds((prev) => prev.filter((id) => id !== role.id));
                        }
                      }}
                      className="w-4 h-4 rounded text-primary focus:ring-primary/20"
                    />
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="text-text-primary font-medium">{role.display_name || role.name}</span>
                        {isChecked && (
                          <span className="text-xs px-2 py-0.5 rounded bg-primary/10 text-primary font-mono">Đã gán</span>
                        )}
                      </div>
                      {role.description && (
                        <p className="text-xs text-text-secondary mt-0.5">{role.description}</p>
                      )}
                    </div>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};
