"use client";

import { useState } from "react";
import { getAccessToken, setAccessToken } from "@/lib/auth/session";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export default function LoginPage() {
  const [email, setEmail] = useState("admin@sgi.ci");
  const [password, setPassword] = useState("admin");
  const [accessTokenState, setAccessTokenState] = useState<string>("");
  const [msg, setMsg] = useState<string>("");

  async function onLogin() {
    setMsg("...");
    setAccessToken(null);
    setAccessTokenState("");

    // OAuth2PasswordRequestForm => x-www-form-urlencoded
    const body = new URLSearchParams();
    body.set("username", email);
    body.set("password", password);

    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
      credentials: "include", // IMPORTANT pour recevoir le cookie refresh
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      setMsg(`Erreur login: ${res.status} ${text}`);
      return;
    }

    const data = await res.json();
    setAccessToken(data.access_token ?? null);
    setAccessTokenState(data.access_token ?? "");
    setMsg("Login OK. Cookie refresh posé.");
  }

  async function onMe() {
    setMsg("...");
    const token = getAccessToken();

    const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
      method: "GET",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: "include",
    });

    const text = await res.text();
    setMsg(text);
  }

  async function onRefresh() {
    setMsg("...");
    const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      setMsg(`Erreur refresh: ${res.status} ${JSON.stringify(data)}`);
      return;
    }

    setAccessToken(data.access_token ?? null);
    setAccessTokenState(data.access_token ?? "");
    setMsg("Refresh OK. Nouveau access_token récupéré.");
  }

  return (
    <main style={{ padding: 24, maxWidth: 520 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 16 }}>
        ARGOS 360 — Login
      </h1>

      <div style={{ display: "grid", gap: 8 }}>
        <label>
          Email
          <input
            style={{
              width: "100%",
              padding: 10,
              border: "1px solid #ddd",
              borderRadius: 8,
            }}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>

        <label>
          Password
          <input
            type="password"
            style={{
              width: "100%",
              padding: 10,
              border: "1px solid #ddd",
              borderRadius: 8,
            }}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>

        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button
            onClick={onLogin}
            style={{
              padding: "10px 14px",
              borderRadius: 10,
              border: "1px solid #ddd",
            }}
          >
            Login
          </button>
          <button
            onClick={onMe}
            style={{
              padding: "10px 14px",
              borderRadius: 10,
              border: "1px solid #ddd",
            }}
          >
            /me
          </button>
          <button
            onClick={onRefresh}
            style={{
              padding: "10px 14px",
              borderRadius: 10,
              border: "1px solid #ddd",
            }}
          >
            Refresh
          </button>
        </div>

        <div style={{ marginTop: 16 }}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>Access token</div>
          <textarea
            readOnly
            value={accessTokenState}
            style={{
              width: "100%",
              height: 120,
              padding: 10,
              border: "1px solid #ddd",
              borderRadius: 8,
            }}
          />
        </div>

        <div style={{ marginTop: 16 }}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>Message</div>
          <pre
            style={{
              padding: 10,
              background: "#f7f7f7",
              borderRadius: 10,
              whiteSpace: "pre-wrap",
            }}
          >
            {msg}
          </pre>
        </div>
      </div>
    </main>
  );
}