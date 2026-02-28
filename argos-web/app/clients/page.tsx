"use client";

import { useEffect, useState } from "react";
import AppShell from "../../components/layout/AppShell";
import RoleGate from "../../components/auth/RoleGate";
import { getAccessToken, setAccessToken } from "../../lib/auth/session";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type ClientRow = {
  id: string;
  full_name: string;
  national_id: string;
  risk_score?: string;
};

export default function ClientsPage() {
  const [userEmail, setUserEmail] = useState<string>();
  const [role, setRole] = useState<string>("");

  const [rows, setRows] = useState<ClientRow[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");

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
    if (token) return token;

    const r = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!r.ok) return null;

    const data = await r.json();
    token = data.access_token ?? null;
    setAccessToken(token);
    return token;
  }

  useEffect(() => {
    async function load() {
      setLoading(true);
      setMsg("");

      const token = await ensureToken();
      if (!token) {
        window.location.href = "/login";
        return;
      }

      // 1) /me (email + role)
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
      setUserEmail(me?.user?.email);
      setRole(me?.user?.role ?? "");

      // 2) load clients (tenant only)
      const listRes = await fetch(`${API_BASE}/api/v1/clients/`, {
        method: "GET",
        headers: { Authorization: `Bearer ${token}` },
        credentials: "include",
      });

      if (!listRes.ok) {
        const text = await listRes.text();
        setMsg(`Erreur API /api/v1/clients: ${listRes.status} ${text}`);
        setRows([]);
        setLoading(false);
        return;
      }

      const data = await listRes.json();
      setRows(Array.isArray(data) ? data : []);
      setMsg("");
      setLoading(false);
    }

    load();
  }, []);

  const filtered = rows.filter((r) => {
    const s = `${r.full_name} ${r.national_id}`.toLowerCase();
    return s.includes(q.toLowerCase().trim());
  });

  return (
    <AppShell userEmail={userEmail} userRole={role} onLogout={logout}>
      {/* ✅ Tenant only: ADMIN + AGENT */}
      <RoleGate role={role} allow={["ADMIN", "AGENT"]}>
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Clients</h1>
            <p className="text-sm text-muted-foreground">KYC — gestion des profils et screening.</p>
          </div>

          <div className="flex gap-2">
            <Button onClick={() => alert("Next: page création client")}>Nouveau client</Button>
            <Button variant="outline" onClick={() => (window.location.href = "/dashboard")}>
              Dashboard
            </Button>
          </div>
        </div>

        <Card className="mt-4 rounded-2xl">
          <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <CardTitle className="text-base">Liste clients</CardTitle>
              <div className="text-sm text-muted-foreground">Recherche, filtres, actions rapides.</div>
            </div>

            <div className="flex w-full gap-2 md:w-[360px]">
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Rechercher (nom, ID…)"
              />
              <Button variant="outline" onClick={() => setQ("")}>
                Reset
              </Button>
            </div>
          </CardHeader>

          <CardContent>
            {msg ? <div className="mb-3 rounded-xl bg-muted p-3 text-sm">{msg}</div> : null}

            <div className="overflow-auto rounded-xl border">
              <table className="w-full text-sm">
                <thead className="bg-muted/40 text-left">
                  <tr>
                    <th className="px-3 py-2">Nom</th>
                    <th className="px-3 py-2">Identifiant</th>
                    <th className="px-3 py-2">Risque</th>
                    <th className="px-3 py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td className="px-3 py-3" colSpan={4}>
                        Chargement…
                      </td>
                    </tr>
                  ) : filtered.length === 0 ? (
                    <tr>
                      <td className="px-3 py-3 text-muted-foreground" colSpan={4}>
                        Aucun client pour le moment.
                      </td>
                    </tr>
                  ) : (
                    filtered.map((r) => (
                      <tr key={r.id} className="border-t">
                        <td className="px-3 py-2 font-medium">{r.full_name}</td>
                        <td className="px-3 py-2">{r.national_id}</td>
                        <td className="px-3 py-2">{r.risk_score ?? "—"}</td>
                        <td className="px-3 py-2 text-right">
                          <Button variant="outline" size="sm" onClick={() => alert(`Open ${r.id}`)}>
                            Ouvrir
                          </Button>
                        </td>
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