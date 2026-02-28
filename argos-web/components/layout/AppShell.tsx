"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

type Role = "SUPER_ADMIN" | "ADMIN" | "AGENT";

type NavItem = {
  href: string;
  label: string;
  desc?: string;
  roles: Role[];
};

const NAV: NavItem[] = [
  // Common
  { href: "/dashboard", label: "Dashboard", desc: "Vue globale", roles: ["SUPER_ADMIN", "ADMIN", "AGENT"] },
  { href: "/settings", label: "Settings", desc: "Sécurité & préférences", roles: ["SUPER_ADMIN", "ADMIN", "AGENT"] },

  // Tenant (ops)
  { href: "/clients", label: "Clients", desc: "KYC", roles: ["ADMIN", "AGENT"] },
  { href: "/alerts", label: "Alertes", desc: "Case management", roles: ["ADMIN", "AGENT"] },

  // Platform
  { href: "/organizations", label: "Organisations", desc: "Tenants", roles: ["SUPER_ADMIN"] },

  // (Tu ajouteras ensuite)
  // { href: "/screening", label: "Screening", desc: "Listes & contrôles", roles: ["ADMIN", "AGENT"] },
  // { href: "/audit", label: "Audit", desc: "Historique actions", roles: ["ADMIN", "AGENT"] },
  // { href: "/platform/access", label: "Accès", desc: "Admins & rôles", roles: ["SUPER_ADMIN"] },
  // { href: "/platform/audit", label: "Audit", desc: "Traçabilité", roles: ["SUPER_ADMIN"] },
];

function getInitials(email?: string) {
  if (!email) return "U";
  const base = email.split("@")[0] ?? "U";
  return base.slice(0, 2).toUpperCase();
}

function getHeaderTitle(role?: string) {
  return role === "SUPER_ADMIN" ? "Platform Console" : "Console";
}

function getHeaderSubtitle(role?: string) {
  return role === "SUPER_ADMIN"
    ? "Tenants • Access • Security • Audit"
    : "KYC • Screening • Alerts • Audit";
}

function ThemeToggle() {
  const [mounted, setMounted] = useState(false);
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setMounted(true);
    const saved = localStorage.getItem("theme");
    const isDark =
      saved === "dark" ||
      (!saved && window.matchMedia("(prefers-color-scheme: dark)").matches);

    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  }

  if (!mounted) return null;

  return (
    <Button variant="outline" size="sm" onClick={toggle}>
      {dark ? "Light" : "Dark"}
    </Button>
  );
}

export default function AppShell({
  children,
  userEmail,
  userRole,
  onLogout,
}: {
  children: React.ReactNode;
  userEmail?: string;
  userRole?: string;
  onLogout?: () => void;
}) {
  const pathname = usePathname();

  // sécurité: si userRole inconnu -> aucune section sensible
  const role = (userRole ?? "") as Role;

  const navByRole = useMemo(() => {
    return NAV.filter((item) => item.roles.includes(role));
  }, [role]);

  const active = useMemo(() => {
    return navByRole.find((n) => pathname?.startsWith(n.href))?.href ?? "/dashboard";
  }, [pathname, navByRole]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-[1400px]">
        <div className="grid min-h-screen grid-cols-12">
          {/* Sidebar */}
          <aside className="col-span-12 border-b bg-background px-4 py-4 md:col-span-3 md:min-h-screen md:border-b-0 md:border-r lg:col-span-2">
            <div className="flex items-center justify-between md:block">
              <div className="flex items-center gap-2">
                <div className="h-9 w-9 rounded-xl bg-foreground/10" />
                <div>
                  <div className="text-sm font-semibold leading-none">ARGOS 360</div>
                  <div className="text-xs text-muted-foreground">Compliance Suite</div>
                </div>
              </div>
              <div className="md:hidden">
                <ThemeToggle />
              </div>
            </div>

            <Separator className="my-4 hidden md:block" />

            <nav className="mt-2 grid gap-1">
              {navByRole.map((item) => {
                const isActive = active === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "group rounded-xl px-3 py-2 transition",
                      "hover:bg-foreground/5",
                      isActive && "bg-foreground/5"
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-medium">{item.label}</div>
                    </div>
                    {item.desc ? (
                      <div className="text-xs text-muted-foreground">{item.desc}</div>
                    ) : null}
                  </Link>
                );
              })}
            </nav>

            <div className="mt-6 hidden md:block">
              <Separator className="my-4" />
              <div className="flex items-center justify-between">
                <div className="text-xs text-muted-foreground">Theme</div>
                <ThemeToggle />
              </div>
            </div>
          </aside>

          {/* Main */}
          <div className="col-span-12 md:col-span-9 lg:col-span-10">
            {/* Topbar */}
            <header className="sticky top-0 z-20 border-b bg-background/70 backdrop-blur">
              <div className="flex items-center justify-between px-4 py-3">
                <div>
                  <div className="text-sm font-semibold">{getHeaderTitle(userRole)}</div>
                  <div className="text-xs text-muted-foreground">{getHeaderSubtitle(userRole)}</div>
                </div>

                <div className="flex items-center gap-2">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button className="flex items-center gap-2 rounded-xl px-2 py-1 hover:bg-foreground/5">
                        <Avatar className="h-8 w-8">
                          <AvatarFallback>{getInitials(userEmail)}</AvatarFallback>
                        </Avatar>
                        <div className="hidden text-left md:block">
                          <div className="text-sm font-medium leading-none">
                            {userEmail ?? "User"}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {userRole === "SUPER_ADMIN" ? "Platform" : "Tenant"} account
                          </div>
                        </div>
                      </button>
                    </DropdownMenuTrigger>

                    <DropdownMenuContent align="end">
                      <DropdownMenuItem asChild>
                        <Link href="/settings">Settings</Link>
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => onLogout?.()}
                        className="text-red-600 focus:text-red-600"
                      >
                        Logout
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            </header>

            <main className="px-4 py-6">{children}</main>
          </div>
        </div>
      </div>
    </div>
  );
}