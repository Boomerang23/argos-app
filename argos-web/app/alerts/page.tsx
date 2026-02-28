"use client";

import { useEffect, useState } from "react";
import AppShell from "../../components/layout/AppShell";
import RoleGate from "../../components/auth/RoleGate";
import { getAccessToken, setAccessToken } from "../../lib/auth/session";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type AlertRow = {
  id: number;
  client_name: string;
  matched_name: string;
  similarity_score?: number;
  status?: string; // OUVERT | EN_COURS | FERME
  decision?: string | null; // FAUX_POSITIF | CONFIRME
  comments?: string | null;

  // ✅ assignment propre
  assigned_user_id?: number | null;

  // 🔒 legacy
  assigned_to?: string | null;

  created_at?: string;
  closed_at?: string | null;
};

type UserRow = { id: number; email: string; full_name?: string; role: string };

type AlertEventRow = {
  id: number;
  alert_id: number;
  user_email: string;
  event_type: string;
  old_value?: string | null;
  new_value?: string | null;
  created_at: string;
};

export default function AlertsPage() {
  const [userEmail, setUserEmail] = useState<string>();
  const [role, setRole] = useState<string>("");
  const [userId, setUserId] = useState<number | null>(null);

  const [rows, setRows] = useState<AlertRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");

  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [decisionFilter, setDecisionFilter] = useState<string>("ALL");

  // mes alertes (assigned=me)
  const [assignedMe, setAssignedMe] = useState(false);

  // ✅ filtre admin: assigned_user_id=...
  const [assignedUserFilter, setAssignedUserFilter] = useState<string>("ALL");

  const [selected, setSelected] = useState<AlertRow | null>(null);
  const [saving, setSaving] = useState(false);

  // ✅ Admin assignment
  const [users, setUsers] = useState<UserRow[]>([]);
  const [assigneeId, setAssigneeId] = useState<string>("");

  // ✅ Timeline
  const [events, setEvents] = useState<AlertEventRow[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);

  const isAdmin = role === "ADMIN";

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

  async function loadMeOnce(): Promise<{ role: string; id: number | null } | null> {
    const token = await ensureToken();
    if (!token) {
      window.location.href = "/login";
      return null;
    }

    const meRes = await fetch(`${API_BASE}/api/v1/auth/me`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    });

    if (!meRes.ok) {
      window.location.href = "/login";
      return null;
    }

    const me = await meRes.json();
    const r = me?.user?.role ?? "";
    const id = me?.user?.id ?? null;

    setUserEmail(me?.user?.email);
    setRole(r);
    setUserId(id);

    return { role: r, id };
  }

  async function loadUsersIfAdmin(currentRole: string) {
    if (currentRole !== "ADMIN") return;

    const token = await ensureToken();
    if (!token) return;

    const res = await fetch(`${API_BASE}/api/v1/users/`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    });

    if (!res.ok) return;

    const data = await res.json();
    setUsers(Array.isArray(data) ? data : []);
  }

  async function loadEvents(alertId: number) {
    setEventsLoading(true);

    const token = await ensureToken();
    if (!token) {
      setEventsLoading(false);
      return;
    }

    const res = await fetch(`${API_BASE}/api/v1/alerts/${alertId}/events`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    });

    if (!res.ok) {
      setEvents([]);
      setEventsLoading(false);
      return;
    }

    const data = await res.json();
    setEvents(Array.isArray(data) ? data : []);
    setEventsLoading(false);
  }

  async function loadAlertsWithFilters(): Promise<AlertRow[]> {
    setLoading(true);
    setMsg("");

    const token = await ensureToken();
    if (!token) {
      window.location.href = "/login";
      return [];
    }

    const params = new URLSearchParams();
    if (statusFilter !== "ALL") params.set("status", statusFilter);
    if (decisionFilter !== "ALL") params.set("decision", decisionFilter);
    if (q.trim()) params.set("q", q.trim());

    if (assignedMe) params.set("assigned", "me");

    // ✅ filtre admin: assigné à un user
    if (role === "ADMIN" && assignedUserFilter !== "ALL") {
      params.set("assigned_user_id", assignedUserFilter);
    }

    const qs = params.toString();
    const url = qs ? `${API_BASE}/api/v1/alerts/?${qs}` : `${API_BASE}/api/v1/alerts/`;

    const res = await fetch(url, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    });

    if (!res.ok) {
      const text = await res.text();
      setMsg(`Erreur API /api/v1/alerts: ${res.status} ${text}`);
      setRows([]);
      setLoading(false);
      return [];
    }

    const data = await res.json();
    const list: AlertRow[] = Array.isArray(data) ? data : [];
    setRows(list);
    setLoading(false);
    return list;
  }

  async function patchAlert(alertId: number, payload: Record<string, any>) {
    setSaving(true);
    setMsg("");

    const token = await ensureToken();
    if (!token) return;

    const res = await fetch(`${API_BASE}/api/v1/alerts/${alertId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      credentials: "include",
      body: JSON.stringify(payload),
    });

    const text = await res.text();
    if (!res.ok) {
      setMsg(`Erreur update alert: ${res.status} ${text}`);
      setSaving(false);
      return;
    }

    const refreshed = await loadAlertsWithFilters();

    setSelected((prev) => {
      if (!prev) return prev;
      const found = refreshed.find((x) => x.id === prev.id);
      return found ?? prev;
    });

    // ✅ refresh timeline si drawer ouvert
    if (selected?.id === alertId) {
      await loadEvents(alertId);
    }

    setSaving(false);
  }

  useEffect(() => {
    (async () => {
      const me = await loadMeOnce();
      if (me) await loadUsersIfAdmin(me.role);
      await loadAlertsWithFilters();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      loadAlertsWithFilters();
    }, 250);

    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, statusFilter, decisionFilter, assignedMe, assignedUserFilter]);

  function badgeStatus(status?: string) {
    const s = String(status ?? "").toUpperCase();
    const base = "inline-flex items-center rounded-full border px-2 py-0.5 text-xs";
    if (s === "OUVERT") return <span className={base}>OUVERT</span>;
    if (s === "EN_COURS") return <span className={base}>EN_COURS</span>;
    if (s === "FERME" || s === "CLOSED") return <span className={base}>FERME</span>;
    return <span className={base}>—</span>;
  }

  function assignedLabel(a: AlertRow) {
    if (!a.assigned_user_id) return "Non";
    if (userId && a.assigned_user_id === userId) return "Moi";
    return "Oui";
  }
    return (
    <AppShell userEmail={userEmail} userRole={role} onLogout={logout}>
      <RoleGate role={role} allow={["ADMIN", "AGENT"]}>
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Alertes</h1>
            <p className="text-sm text-muted-foreground">Case management — traitement des matches.</p>
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => (window.location.href = "/dashboard")}>
              Dashboard
            </Button>
          </div>
        </div>

        <Card className="mt-4 rounded-2xl">
          <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <CardTitle className="text-base">Liste alertes</CardTitle>
              <div className="text-sm text-muted-foreground">
                Filtres serveur (status, décision, recherche, assignation).
              </div>
            </div>

            <div className="flex w-full flex-col gap-2 md:w-[1100px] md:flex-row">
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Rechercher (client, match, id…)"
              />

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="h-10 rounded-md border bg-background px-3 text-sm"
              >
                <option value="ALL">Tous statuts</option>
                <option value="OUVERT">OUVERT</option>
                <option value="EN_COURS">EN_COURS</option>
                <option value="FERME">FERME</option>
              </select>

              <select
                value={decisionFilter}
                onChange={(e) => setDecisionFilter(e.target.value)}
                className="h-10 rounded-md border bg-background px-3 text-sm"
              >
                <option value="ALL">Toutes décisions</option>
                <option value="FAUX_POSITIF">FAUX_POSITIF</option>
                <option value="CONFIRME">CONFIRME</option>
              </select>

              {/* ✅ ADMIN: filtre assigné à */}
              {isAdmin ? (
                <select
                  value={assignedUserFilter}
                  onChange={(e) => {
                    setAssignedUserFilter(e.target.value);
                    setAssignedMe(false);
                  }}
                  className="h-10 rounded-md border bg-background px-3 text-sm"
                  title="Filtrer par user assigné"
                >
                  <option value="ALL">Assigné à (tous)</option>
                  {users.map((u) => (
                    <option key={u.id} value={String(u.id)}>
                      {u.full_name ? `${u.full_name} (${u.email})` : u.email}
                    </option>
                  ))}
                </select>
              ) : null}

              <Button
                variant={assignedMe ? "default" : "outline"}
                onClick={() => {
                  setAssignedMe((v) => !v);
                  setAssignedUserFilter("ALL");
                }}
                title="Filtre: alertes assignées à moi"
              >
                Mes alertes
              </Button>

              <Button
                variant="outline"
                onClick={() => {
                  setQ("");
                  setStatusFilter("ALL");
                  setDecisionFilter("ALL");
                  setAssignedMe(false);
                  setAssignedUserFilter("ALL");
                }}
              >
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
                    <th className="px-3 py-2">ID</th>
                    <th className="px-3 py-2">Client</th>
                    <th className="px-3 py-2">Match</th>
                    <th className="px-3 py-2">Score</th>
                    <th className="px-3 py-2">Statut</th>
                    <th className="px-3 py-2">Assigné</th>
                    <th className="px-3 py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td className="px-3 py-3" colSpan={7}>
                        Chargement…
                      </td>
                    </tr>
                  ) : rows.length === 0 ? (
                    <tr>
                      <td className="px-3 py-3 text-muted-foreground" colSpan={7}>
                        Aucune alerte.
                      </td>
                    </tr>
                  ) : (
                    rows.map((a) => (
                      <tr key={a.id} className="border-t">
                        <td className="px-3 py-2 font-medium">{a.id}</td>
                        <td className="px-3 py-2">{a.client_name}</td>
                        <td className="px-3 py-2">{a.matched_name}</td>
                        <td className="px-3 py-2">{a.similarity_score ?? "—"}</td>
                        <td className="px-3 py-2">{badgeStatus(a.status)}</td>
                        <td className="px-3 py-2">{assignedLabel(a)}</td>
                        <td className="px-3 py-2 text-right">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={async () => {
                              setSelected(a);
                              setAssigneeId(a.assigned_user_id ? String(a.assigned_user_id) : "");
                              await loadEvents(a.id);
                            }}
                          >
                            Ouvrir
                          </Button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Drawer simple */}
            {selected ? (
              <div className="mt-4 rounded-2xl border p-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-sm text-muted-foreground">Alerte #{selected.id}</div>
                    <div className="text-lg font-semibold">{selected.client_name}</div>
                    <div className="text-sm text-muted-foreground">
                      Match: <span className="text-foreground">{selected.matched_name}</span> • Score:{" "}
                      <span className="text-foreground">{selected.similarity_score ?? "—"}</span>
                    </div>

                    <div className="mt-2 text-sm">
                      Statut: <span className="font-medium">{String(selected.status ?? "—")}</span> • Décision:{" "}
                      <span className="font-medium">{String(selected.decision ?? "—")}</span>
                    </div>

                    <div className="mt-1 text-sm">
                      Assigné:{" "}
                      <span className="font-medium">
                        {selected.assigned_user_id ? assignedLabel(selected) : "Non"}
                      </span>
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      onClick={() => {
                        setSelected(null);
                        setEvents([]);
                        setAssigneeId("");
                      }}
                    >
                      Fermer
                    </Button>
                  </div>
                </div>

                {/* ✅ ADMIN: assigner à un user */}
                {isAdmin ? (
                  <div className="mt-4 flex flex-col gap-2 md:flex-row md:items-center">
                    <div className="text-sm font-medium">Assigner à</div>

                    <select
                      value={assigneeId}
                      onChange={(e) => setAssigneeId(e.target.value)}
                      className="h-10 rounded-md border bg-background px-3 text-sm md:min-w-[340px]"
                    >
                      <option value="">— Choisir un user —</option>
                      {users.map((u) => (
                        <option key={u.id} value={String(u.id)}>
                          {u.full_name ? `${u.full_name} (${u.email})` : u.email} — {u.role}
                        </option>
                      ))}
                    </select>

                    <Button
                      disabled={
                        saving ||
                        !assigneeId ||
                        Number(assigneeId) === (selected.assigned_user_id ?? 0)
                      }
                      onClick={() => patchAlert(selected.id, { assigned_user_id: Number(assigneeId) })}
                    >
                      Assigner
                    </Button>
                  </div>
                ) : null}

                <div className="mt-4 flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    disabled={saving}
                    onClick={() => patchAlert(selected.id, { status: "EN_COURS" })}
                  >
                    Mettre EN_COURS
                  </Button>

                  <Button
                    variant="outline"
                    disabled={saving || !userId || selected.assigned_user_id === userId}
                    onClick={() => patchAlert(selected.id, { assigned_user_id: userId })}
                    title={!userId ? "User id manquant" : ""}
                  >
                    M’assigner
                  </Button>

                  <Button
                    variant="outline"
                    disabled={saving || !isAdmin}
                    onClick={() => patchAlert(selected.id, { decision: "FAUX_POSITIF" })}
                    title={!isAdmin ? "ADMIN requis" : ""}
                  >
                    Décision: FAUX_POSITIF
                  </Button>

                  <Button
                    variant="outline"
                    disabled={saving || !isAdmin}
                    onClick={() => patchAlert(selected.id, { decision: "CONFIRME" })}
                    title={!isAdmin ? "ADMIN requis" : ""}
                  >
                    Décision: CONFIRME
                  </Button>

                  <Button
                    disabled={saving || !isAdmin}
                    onClick={() => patchAlert(selected.id, { status: "FERME" })}
                    title={!isAdmin ? "ADMIN requis" : ""}
                  >
                    Fermer (FERME)
                  </Button>
                </div>

                {/* ===== Timeline ===== */}
                <div className="mt-6 border-t pt-4">
                  <div className="mb-2 text-sm font-semibold">Historique</div>

                  {eventsLoading ? (
                    <div className="text-xs text-muted-foreground">Chargement…</div>
                  ) : events.length === 0 ? (
                    <div className="text-xs text-muted-foreground">Aucun événement.</div>
                  ) : (
                    events.map((e) => (
                      <div key={e.id} className="border-b py-2 text-xs">
                        <div className="font-medium">{e.event_type}</div>
                        <div>{e.user_email}</div>
                        <div>
                          {(e.old_value ?? "—").toString()} → {(e.new_value ?? "—").toString()}
                        </div>
                        <div className="text-muted-foreground">
                          {new Date(e.created_at).toLocaleString()}
                        </div>
                      </div>
                    ))
                  )}
                </div>

                {!isAdmin ? (
                  <div className="mt-3 text-xs text-muted-foreground">
                    Note: seules les actions “décision” et “fermeture” nécessitent ADMIN.
                  </div>
                ) : null}
              </div>
            ) : null}
          </CardContent>
        </Card>
      </RoleGate>
    </AppShell>
  );
}