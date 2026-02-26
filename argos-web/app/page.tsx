"use client";

import { useEffect } from "react";
import { getAccessToken, setAccessToken } from "@/lib/auth/session";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function Home() {
  useEffect(() => {
    async function run() {
      // Si token déjà en mémoire => dashboard
      if (getAccessToken()) {
        window.location.href = "/dashboard";
        return;
      }

      // Sinon on tente refresh via cookie httpOnly
      const r = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });

      if (!r.ok) {
        window.location.href = "/login";
        return;
      }

      const data = await r.json();
      setAccessToken(data.access_token ?? null);
      window.location.href = "/dashboard";
    }

    run();
  }, []);

  return <main style={{ padding: 24 }}>Chargement...</main>;
}