"use client";

import { useEffect, useState } from "react";
import AppShell from "../../components/layout/AppShell";
import RoleGate from "../../components/auth/RoleGate";
import { getAccessToken, setAccessToken } from "../../lib/auth/session";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type Org = { id: number; name: string; created_at?: string };

export default function OrganizationsPage() {
  const [userEmail, setUserEmail] = useState<string>();
  const [role, setRole] = useState<string>("");
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [newName, setNewName] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(true);

  const [adminOrgId, setAdminOrgId] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [adminFullName, setAdminFullName] = useState("");

  async function logout() {
    await fetch(`${API_BASE}/api/v1/auth/logout`, {
      method: "POST",
      credentials: "include",
    }).catch(() => null);

    setAccessToken(null);
    window.location.href = "/login";
  }

  async function ensureToken(): Promise<string | null> {
    let token = getAccessToken();

    // Tente refresh d'abord (cookie HTTPOnly)
    const r = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });

    if (r.ok) {
      const data = await r.json();
      token = data.access_token ?? null;
      setAccessToken(token);
      return token;
    }

    // sinon, utilise le token existant (si présent)
    return token ?? null;
  }

  async function loadAll() {
    setLoading(true);
    setMsg("");

    const token = await ensureToken();
    if (!token) {
      window.location.href = "/login";
      return;
    }

    // 1) /me
    const meRes = await fetch(`${API_BASE}/api/v1/auth/me`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    });

    if (!meRes.ok) {
      window.location.href = "/login";
      return;
    }

    const me = await meRes.json();
    const currentRole = me?.user?.role ?? "";
    setUserEmail(me?.user?.email);
    setRole(currentRole);

    // 2) Si pas SUPER_ADMIN, on ne charge pas les orgs
    if (currentRole !== "SUPER_ADMIN") {
      setOrgs([]);
      setLoading(false);
      return;
    }

    // 3) Load organizations (API v1)
    const res = await fetch(`${API_BASE}/api/v1/organizations/`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    });

    if (!res.ok) {
      const text = await res.text();
      setMsg(`Erreur /api/v1/organizations: ${res.status} ${text}`);
      setOrgs([]);
      setLoading(false);
      return;
    }

    const data = await res.json();
    setOrgs(Array.isArray(data) ? data : []);
    setLoading(false);
  }

  async function createOrg() {
    setMsg("...");
    const token = await ensureToken();
    if (!token) return;

    const res = await fetch(`${API_BASE}/api/v1/organizations/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      credentials: "include",
      body: JSON.stringify({ name: newName }),
    });

    const text = await res.text();
    if (!res.ok) {
      setMsg(`Erreur create org: ${res.status} ${text}`);
      return;
    }

    setNewName("");
    setMsg("Organisation créée.");
    await loadAll();
  }

  async function createTenantAdmin() {
    setMsg("...");
    const token = await ensureToken();
    if (!token) return;

    const res = await fetch(`${API_BASE}/api/v1/organizations/create-admin`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      credentials: "include",
      body: JSON.stringify({
        organization_id: Number(adminOrgId),
        admin_email: adminEmail,
        password: adminPassword,
        full_name: adminFullName,
      }),
    });

    const text = await res.text();
    if (!res.ok) {
      setMsg(`Erreur create admin: ${res.status} ${text}`);
      return;
    }

    setMsg("Admin du tenant créé.");
    setAdminOrgId("");
    setAdminEmail("");
    setAdminPassword("");
    setAdminFullName("");

    // optionnel: reload pour mettre à jour stats
    await loadAll();
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AppShell userEmail={userEmail} userRole={role} onLogout={logout}>
      {/* ✅ Bloque l'accès UI si pas SUPER_ADMIN */}
      <RoleGate role={role} allow={["SUPER_ADMIN"]}>
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Organisations</h1>
            <p className="text-sm text-muted-foreground">Plateforme — gestion des tenants.</p>
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => (window.location.href = "/dashboard")}>
              Dashboard
            </Button>
          </div>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <Card className="rounded-2xl md:col-span-1">
            <CardHeader>
              <CardTitle className="text-base">Créer une organisation</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2">
              <Input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Ex: SGI CI / Fintech CA / Cabinet X"
              />
              <Button onClick={createOrg} disabled={!newName.trim()}>
                Créer
              </Button>
              {msg ? <div className="rounded-xl bg-muted p-3 text-sm">{msg}</div> : null}
            </CardContent>
          </Card>

          <Card className="rounded-2xl md:col-span-1">
            <CardHeader>
              <CardTitle className="text-base">Créer un admin de tenant</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2">
              <Input
                value={adminOrgId}
                onChange={(e) => setAdminOrgId(e.target.value)}
                placeholder="Organization ID (ex: 1)"
              />
              <Input
                value={adminFullName}
                onChange={(e) => setAdminFullName(e.target.value)}
                placeholder="Nom complet"
              />
              <Input value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} placeholder="Email" />
              <Input
                type="password"
                value={adminPassword}
                onChange={(e) => setAdminPassword(e.target.value)}
                placeholder="Mot de passe"
              />
              <Button
                onClick={createTenantAdmin}
                disabled={!adminOrgId || !adminEmail || !adminPassword || !adminFullName}
              >
                Créer admin
              </Button>
            </CardContent>
          </Card>

          <Card className="rounded-2xl md:col-span-1">
            <CardHeader>
              <CardTitle className="text-base">Stats</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Organisations: <span className="font-medium text-foreground">{orgs.length}</span>
            </CardContent>
          </Card>
        </div>

        <Card className="mt-4 rounded-2xl">
          <CardHeader>
            <CardTitle className="text-base">Liste</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-auto rounded-xl border">
              <table className="w-full text-sm">
                <thead className="bg-muted/40 text-left">
                  <tr>
                    <th className="px-3 py-2">ID</th>
                    <th className="px-3 py-2">Nom</th>
                    <th className="px-3 py-2">Créée</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td className="px-3 py-3" colSpan={3}>
                        Chargement…
                      </td>
                    </tr>
                  ) : orgs.length === 0 ? (
                    <tr>
                      <td className="px-3 py-3 text-muted-foreground" colSpan={3}>
                        Aucune organisation.
                      </td>
                    </tr>
                  ) : (
                    orgs.map((o) => (
                      <tr key={o.id} className="border-t">
                        <td className="px-3 py-2 font-medium">{o.id}</td>
                        <td className="px-3 py-2">{o.name}</td>
                        <td className="px-3 py-2">{o.created_at ?? "—"}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </RoleGate>
    </AppShell>
  );
}