"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { getAccessToken, setAccessToken } from "@/lib/auth/session";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type MeResponse = {
  user: { id: number; email: string; full_name?: string; role: string; is_active: boolean };
  organization: { id: number | null };
};

export default function DashboardPage() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  // Tenant KPIs
  const [kpiClients, setKpiClients] = useState<number>(0);
  const [kpiAlertsOpen, setKpiAlertsOpen] = useState<number>(0);
  const [kpiScans, setKpiScans] = useState<number>(0);

  // Platform KPIs (SUPER_ADMIN)
  const [kpiOrgs, setKpiOrgs] = useState<number>(0);
  const [kpiUsers, setKpiUsers] = useState<number>(0);

  async function logout() {
    await fetch(`${API_BASE}/api/v1/auth/logout`, {
      method: "POST",
      credentials: "include",
    }).catch(() => null);

    setAccessToken(null);
    window.location.href = "/login";
  }

  useEffect(() => {
    async function run() {
      try {
        let token = getAccessToken();

        // 1) Ensure access token
        if (!token) {
          const r = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
            method: "POST",
            credentials: "include",
          });

          if (!r.ok) {
            window.location.href = "/login";
            return;
          }

          const refreshData = await r.json();
          token = refreshData.access_token ?? null;
          setAccessToken(token);
        }

        const headers: Record<string, string> = token
          ? { Authorization: `Bearer ${token}` }
          : {};

        // 2) Load /me
        const meRes = await fetch(`${API_BASE}/api/v1/auth/me`, {
          method: "GET",
          headers,
          credentials: "include",
        });

        if (!meRes.ok) {
          window.location.href = "/login";
          return;
        }

        const meData = (await meRes.json()) as MeResponse;
        setMe(meData);

        // 3) KPIs depending on role
        if (meData?.user?.role === "SUPER_ADMIN") {
          // Platform KPIs: organizations + total users across orgs
          const oRes = await fetch(`${API_BASE}/api/v1/organizations/`, {
            method: "GET",
            headers,
            credentials: "include",
          });

          if (oRes.ok) {
            const orgs = await oRes.json();
            setKpiOrgs(Array.isArray(orgs) ? orgs.length : 0);

            let totalUsers = 0;

            if (Array.isArray(orgs)) {
              await Promise.all(
                orgs.map(async (org: any) => {
                  const id = org?.id;
                  if (!id) return;

                  const uRes = await fetch(`${API_BASE}/api/v1/organizations/${id}/users`, {
                    method: "GET",
                    headers,
                    credentials: "include",
                  });

                  if (!uRes.ok) return;

                  const users = await uRes.json();
                  totalUsers += Array.isArray(users) ? users.length : 0;
                })
              );
            }

            setKpiUsers(totalUsers);
          }

          // On laisse les KPIs tenant à 0/— (pas utilisés côté SUPER_ADMIN)
          setKpiClients(0);
          setKpiAlertsOpen(0);
          setKpiScans(0);
        } else {
          // Tenant KPIs: clients + open alerts + scan history
          const [cRes, aRes, hRes] = await Promise.all([
            fetch(`${API_BASE}/api/v1/clients/`, { method: "GET", headers, credentials: "include" }),
            fetch(`${API_BASE}/api/v1/alerts/`, { method: "GET", headers, credentials: "include" }),
            fetch(`${API_BASE}/api/v1/history/`, { method: "GET", headers, credentials: "include" }),
          ]);

          if (cRes.ok) {
            const c = await cRes.json();
            setKpiClients(Array.isArray(c) ? c.length : 0);
          }

          if (aRes.ok) {
            const a = await aRes.json();
            const openCount = Array.isArray(a)
              ? a.filter((x) => String(x?.status ?? "").toUpperCase() === "OUVERT").length
              : 0;
            setKpiAlertsOpen(openCount);
          }

          if (hRes.ok) {
            const h = await hRes.json();
            setKpiScans(Array.isArray(h) ? h.length : 0);
          }

          // Platform KPIs not used for tenant
          setKpiOrgs(0);
          setKpiUsers(0);
        }
      } finally {
        setLoading(false);
      }
    }

    run();
  }, []);

  const isPlatform = me?.user.role === "SUPER_ADMIN";

  return (
    <AppShell userEmail={me?.user.email} userRole={me?.user.role} onLogout={logout}>
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
            <span className="rounded-full border px-2 py-0.5 text-xs">
              {isPlatform ? "Platform" : "Tenant"}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            {isPlatform
              ? "Pilotage plateforme — organisations, accès, conformité."
              : "Vue tenant — clients KYC, scans, alertes, activité."}
          </p>
        </div>

        {!isPlatform ? (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => (window.location.href = "/clients")}>
              Clients
            </Button>
            <Button variant="outline" onClick={() => (window.location.href = "/alerts")}>
              Alertes
            </Button>
          </div>
        ) : (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => (window.location.href = "/organizations")}>
              Organisations
            </Button>
          </div>
        )}
      </div>

      {/* KPIs */}
      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <Card className="rounded-2xl">
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">
              {isPlatform ? "Organisations" : "Organisation"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">
              {loading ? "…" : isPlatform ? kpiOrgs : (me?.organization.id ?? "N/A")}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {isPlatform ? "Tenants (plateforme)" : "Tenant actif"}
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-2xl">
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">
              {isPlatform ? "Utilisateurs" : "Clients"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">
              {loading ? "…" : isPlatform ? kpiUsers : kpiClients}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {isPlatform ? "Tous tenants confondus" : "Total KYC"}
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-2xl">
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">
              {isPlatform ? "Alertes (tenants)" : "Alertes ouvertes"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">
              {loading ? "…" : isPlatform ? "—" : kpiAlertsOpen}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {isPlatform ? "Case management (vue globale)" : "Case management"}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Secondary KPI */}
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <Card className="rounded-2xl md:col-span-1">
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">
              {isPlatform ? "Activité" : "Scans"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">
              {loading ? "…" : isPlatform ? "—" : kpiScans}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {isPlatform ? "Audit (à brancher)" : "Historique"}
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-2xl md:col-span-2">
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Role</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xl font-semibold">{loading ? "…" : (me?.user.role ?? "—")}</div>
            <div className="mt-1 text-xs text-muted-foreground">{isPlatform ? "Plateforme" : "Tenant"}</div>
          </CardContent>
        </Card>
      </div>

      {/* Actions */}
      <div className="mt-6">
        <Card className="rounded-2xl">
          <CardHeader>
            <CardTitle className="text-base">{isPlatform ? "Platform actions" : "Quick actions"}</CardTitle>
          </CardHeader>

          {isPlatform ? (
            <CardContent className="flex flex-wrap gap-2">
              <Button onClick={() => (window.location.href = "/organizations")}>
                Gérer les organisations
              </Button>
            </CardContent>
          ) : (
            <CardContent className="flex flex-wrap gap-2">
              <Button onClick={() => (window.location.href = "/clients")}>Créer / gérer clients</Button>
              <Button variant="outline" onClick={() => (window.location.href = "/alerts")}>
                Traiter les alertes
              </Button>
            </CardContent>
          )}
        </Card>
      </div>
    </AppShell>
  );
}