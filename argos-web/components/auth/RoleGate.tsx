"use client";

import { useEffect } from "react";

type Role = "SUPER_ADMIN" | "ADMIN" | "AGENT";

export default function RoleGate({
  role,
  allow,
  children,
  redirectTo = "/dashboard",
}: {
  role?: string;
  allow: Role[];
  children: React.ReactNode;
  redirectTo?: string;
}) {
  useEffect(() => {
    if (!role) return;
    const r = role as Role;
    if (!allow.includes(r)) window.location.href = redirectTo;
  }, [role, allow, redirectTo]);

  if (!role) return null;
  const r = role as Role;
  if (!allow.includes(r)) return null;

  return <>{children}</>;
}