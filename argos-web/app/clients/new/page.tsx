"use client";

import { useEffect, useState } from "react";
import AppShell from "../../../components/layout/AppShell";
import { getAccessToken, setAccessToken } from "../../../lib/auth/session";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function NewClientPage() {
  const [userEmail, setUserEmail] = useState<string>();
  const [fullName, setFullName] = useState("");
  const [nationalId, setNationalId] = useState("");
  const [entityType, setEntityType] = useState("Physique");
  const [country, setCountry] = useState("CI");
  const [msg, setMsg] = useState("");

  async function logout() {
    await fetch(`${API_BASE}/api/v1/auth/logout`, { method: "POST", credentials: "include" }).catch(
      () => null
    );
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
    async function loadMe() {
      const token = await ensureToken();
      if (!token) {
        window.location.href = "/login";
        return;
      }

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

      // ✅ Plateforme -> pas de KYC
      if (me?.user?.role === "SUPER_ADMIN") {
        window.location.href = "/organizations";
        return;
      }

      setUserEmail(me?.user?.email);
    }

    loadMe();
  }, []);

  async function onCreate() {
    setMsg("...");
    const token = await ensureToken();
    if (!token) {
      window.location.href = "/login";
      return;
    }

    const res = await fetch(`${API_BASE}/clients/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      credentials: "include",
      body: JSON.stringify({
        full_name: fullName,
        entity_type: entityType,
        national_id: nationalId,
        country_residence: country,
        tenant_id: "MANUAL",
      }),
    });

    const text = await res.text();
    if (!res.ok) {
      setMsg(`Erreur: ${res.status} ${text}`);
      return;
    }

    setMsg("Client créé. Retour à la liste...");
    setTimeout(() => {
      window.location.href = "/clients";
    }, 500);
  }

  return (
    <AppShell userEmail={userEmail} onLogout={logout}>
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Nouveau client</h1>
          <p className="text-sm text-muted-foreground">Création + screening automatique.</p>
        </div>

        <div className="flex gap-2">
          <Button variant="outline" onClick={() => (window.location.href = "/clients")}>
            Retour
          </Button>
        </div>
      </div>

      <Card className="mt-4 rounded-2xl">
        <CardHeader>
          <CardTitle className="text-base">Informations KYC</CardTitle>
        </CardHeader>

        <CardContent className="grid gap-3 md:max-w-[520px]">
          <div className="grid gap-2">
            <div className="text-sm font-medium">Nom complet</div>
            <Input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Ex: Ange GBOCHO"
            />
          </div>

          <div className="grid gap-2">
            <div className="text-sm font-medium">Identifiant (national_id)</div>
            <Input
              value={nationalId}
              onChange={(e) => setNationalId(e.target.value)}
              placeholder="Ex: CI-12345"
            />
          </div>

          <div className="grid gap-2">
            <div className="text-sm font-medium">Type</div>
            <Input
              value={entityType}
              onChange={(e) => setEntityType(e.target.value)}
              placeholder="Physique / Morale"
            />
          </div>

          <div className="grid gap-2">
            <div className="text-sm font-medium">Pays de résidence</div>
            <Input value={country} onChange={(e) => setCountry(e.target.value)} placeholder="CI / CA" />
          </div>

          <div className="flex gap-2 pt-2">
            <Button onClick={onCreate} disabled={!fullName || !nationalId}>
              Créer
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setFullName("");
                setNationalId("");
                setMsg("");
              }}
            >
              Reset
            </Button>
          </div>

          {msg ? <div className="rounded-xl bg-muted p-3 text-sm">{msg}</div> : null}
        </CardContent>
      </Card>
    </AppShell>
  );
}