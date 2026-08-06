import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LayoutDashboard, Building2, KeyRound, FolderGit2, Settings as SettingsIcon, LogOut, Menu, ChevronsUpDown, Check, MessageSquare, Sparkles, Images, Shield, Coins, Bot, Brain, ShieldAlert, CreditCard, Workflow } from "lucide-react";
import { useAuth, api } from "@/context/AuthContext";
import { Logo } from "@/components/shared";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [orgs, setOrgs] = useState([]);
  const [activeOrg, setActiveOrg] = useState(null);
  const [usage, setUsage] = useState(null);

  const refreshOrgs = async () => {
    const { data } = await api.get("/orgs");
    setOrgs(data);
    setActiveOrg((cur) => {
      if (cur) { const found = data.find((o) => o.id === cur.id); if (found) return found; }
      return data.find((o) => o.id === user?.default_org_id) || data[0] || null;
    });
    return data;
  };
  useEffect(() => { refreshOrgs(); }, []); // eslint-disable-line

  const refreshUsage = async () => {
    if (!activeOrg) return;
    try { const { data } = await api.get(`/orgs/${activeOrg.id}/usage`); setUsage(data); } catch { /* ignore */ }
  };
  useEffect(() => { refreshUsage(); }, [activeOrg]); // eslint-disable-line

  const items = [
    { to: "/app", end: true, icon: LayoutDashboard, label: "Overview", id: "overview" },
    { to: "/app/chat", icon: Sparkles, label: "AI Studio", id: "chat" },
    { to: "/app/creations", icon: Images, label: "Creations", id: "creations" },
    { to: "/app/agents", icon: Bot, label: "AI Agents", id: "agents" },
    { to: "/app/planning", icon: Workflow, label: "Planning", id: "planning" },
    { to: "/app/memory", icon: Brain, label: "Knowledge", id: "memory" },
    { to: "/app/projects", icon: FolderGit2, label: "Projects", id: "projects" },
    { to: "/app/organization", icon: Building2, label: "Organization", id: "organization" },
    { to: "/app/api-keys", icon: KeyRound, label: "API Keys", id: "api-keys" },
    { to: "/app/billing", icon: CreditCard, label: "Billing", id: "billing" },
    { to: "/app/settings", icon: SettingsIcon, label: "Settings", id: "settings" },
  ];
  if (user?.global_role === "admin") {
    items.push({ to: "/app/security", icon: ShieldAlert, label: "Security", id: "security" });
    items.push({ to: "/app/admin", icon: Shield, label: "Admin", id: "admin" });
  }

  const doLogout = async () => { await logout(); nav("/"); };

  const Inner = (
    <div className="flex flex-col h-full">
      <div className="p-5"><Logo to="/app" /></div>

      <div className="px-3 mb-3">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button data-testid="org-switcher" className="w-full flex items-center justify-between gap-2 px-3 py-2.5 rounded-xl bg-[#12121C] border border-[rgba(255,255,255,0.08)] text-sm hover:border-[rgba(255,255,255,0.2)] transition-colors">
              <span className="flex items-center gap-2 min-w-0"><Building2 className="w-4 h-4 text-[#A855F7] shrink-0" /><span className="truncate">{activeOrg?.name || "…"}</span></span>
              <ChevronsUpDown className="w-4 h-4 text-[#64748B] shrink-0" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-56 bg-[#12121C] border border-[rgba(255,255,255,0.12)] text-white">
            {orgs.map((o) => (
              <DropdownMenuItem key={o.id} data-testid={`org-option-${o.id}`} onClick={() => setActiveOrg(o)}
                className="flex items-center justify-between gap-2 cursor-pointer focus:bg-white/5">
                <span className="truncate">{o.name}</span>
                {activeOrg?.id === o.id && <Check className="w-4 h-4 text-emerald-400" />}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <nav className="flex-1 px-3 space-y-1 overflow-y-auto">
        {items.map((it) => (
          <NavLink key={it.id} to={it.to} end={it.end} onClick={() => setOpen(false)} data-testid={`sidebar-${it.id}-link`}
            className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-colors ${isActive ? "bg-white/5 text-white border border-[rgba(255,255,255,0.1)]" : "text-[#94A3B8] hover:text-white hover:bg-white/5 border border-transparent"}`}>
            <it.icon className="w-[18px] h-[18px]" /> {it.label}
          </NavLink>
        ))}
      </nav>

      <div className="p-3 border-t border-[rgba(255,255,255,0.06)]">
        <NavLink to="/app/billing" onClick={() => setOpen(false)} data-testid="sidebar-credits-badge"
          className="flex items-center gap-2 px-3 py-2.5 mb-1 rounded-xl bg-[#12121C] border border-[rgba(255,255,255,0.08)] text-sm hover:border-[#A855F7] transition-colors">
          <Coins className="w-4 h-4 text-[#D946EF]" />
          <span data-testid="sidebar-credits" className="text-white font-medium">{usage?.credits ?? "…"}</span>
          <span className="text-[#64748B]">credits</span>
          <span className="ms-auto text-xs text-[#64748B] capitalize">{usage?.plan}</span>
        </NavLink>
        <div className="px-3 py-2 text-sm">
          <p className="text-white font-medium truncate">{user?.name}</p>
          <p className="text-[#64748B] text-xs truncate">{user?.email}</p>
        </div>
        <button data-testid="logout-btn" onClick={doLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-[#94A3B8] hover:text-white hover:bg-white/5 transition-colors">
          <LogOut className="w-[18px] h-[18px]" /> Log out
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen text-[#F8FAFC] flex">
      <aside className="hidden lg:flex w-64 shrink-0 border-e border-[rgba(255,255,255,0.06)] bg-[#0C0C14] flex-col h-screen sticky top-0">{Inner}</aside>
      {open && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
          <aside className="relative w-64 bg-[#0C0C14] border-e border-[rgba(255,255,255,0.08)] h-full">{Inner}</aside>
        </div>
      )}
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="lg:hidden glass border-b border-[rgba(255,255,255,0.06)] h-14 flex items-center justify-between px-4 sticky top-0 z-40">
          <button data-testid="mobile-menu-btn" onClick={() => setOpen(true)} className="text-white"><Menu className="w-6 h-6" /></button>
          <Logo size="text-lg" to="/app" />
          <span className="w-6" />
        </header>
        <main className="flex-1 min-w-0">
          {activeOrg ? <Outlet context={{ activeOrg, orgs, setActiveOrg, refreshOrgs, refreshUsage, usage, user }} /> :
            <div className="p-8 text-[#64748B]">Loading workspace…</div>}
        </main>
      </div>
    </div>
  );
}
