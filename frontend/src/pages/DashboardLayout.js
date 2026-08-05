import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LayoutDashboard, MessageSquare, PenLine, Image as ImageIcon, History as HistoryIcon, Settings as SettingsIcon, Crown, LogOut, Menu, X, Coins } from "lucide-react";
import { toast } from "sonner";
import { useApp } from "@/context/AppContext";
import { Logo, LangSwitcher } from "@/components/shared";
import { api } from "@/context/AppContext";
import { Button } from "@/components/ui/button";

export default function DashboardLayout() {
  const { t, user, logout, setUser } = useApp();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);

  const items = [
    { to: "/app", end: true, icon: LayoutDashboard, label: t.sidebar.dashboard, id: "dashboard" },
    { to: "/app/chat", icon: MessageSquare, label: t.sidebar.chat, id: "chat" },
    { to: "/app/text", icon: PenLine, label: t.sidebar.text, id: "text" },
    { to: "/app/image", icon: ImageIcon, label: t.sidebar.image, id: "image" },
    { to: "/app/history", icon: HistoryIcon, label: t.sidebar.history, id: "history" },
    { to: "/app/settings", icon: SettingsIcon, label: t.sidebar.settings, id: "settings" },
  ];

  const doLogout = async () => { await logout(); nav("/"); };
  const upgrade = async () => {
    try { const { data } = await api.post("/billing/upgrade"); setUser(data); toast.success("Pro activated"); }
    catch { toast.error(t.common.error); }
  };

  const SidebarInner = (
    <div className="flex flex-col h-full">
      <div className="p-5"><Logo /></div>
      <nav className="flex-1 px-3 space-y-1 overflow-y-auto">
        {items.map((it) => (
          <NavLink key={it.id} to={it.to} end={it.end} onClick={() => setOpen(false)} data-testid={`sidebar-${it.id}-link`}
            className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-colors ${isActive ? "bg-white/5 text-white border border-[rgba(255,255,255,0.1)]" : "text-[#94A3B8] hover:text-white hover:bg-white/5 border border-transparent"}`}>
            <it.icon className="w-[18px] h-[18px]" /> {it.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-3 space-y-3">
        {user?.plan !== "pro" && (
          <button data-testid="sidebar-upgrade-btn" onClick={upgrade}
            className="w-full flex items-center gap-2 justify-center px-3 py-2.5 rounded-xl text-sm text-white ai-gradient-bg hover:opacity-90 transition-opacity glow-border">
            <Crown className="w-4 h-4" /> {t.sidebar.upgrade}
          </button>
        )}
        <div className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-[#12121C] border border-[rgba(255,255,255,0.08)] text-sm">
          <Coins className="w-4 h-4 text-[#D946EF]" />
          <span data-testid="sidebar-credits" className="text-white font-medium">{user?.credits}</span>
          <span className="text-[#64748B]">{t.sidebar.credits}</span>
        </div>
        <button data-testid="sidebar-logout-btn" onClick={doLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-[#94A3B8] hover:text-white hover:bg-white/5 transition-colors">
          <LogOut className="w-[18px] h-[18px]" /> {t.sidebar.logout}
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen text-[#F8FAFC] flex">
      {/* desktop sidebar */}
      <aside className="hidden lg:flex w-64 shrink-0 border-e border-[rgba(255,255,255,0.06)] bg-[#0C0C14] flex-col h-screen sticky top-0">
        {SidebarInner}
      </aside>

      {/* mobile drawer */}
      {open && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
          <aside className="relative w-64 bg-[#0C0C14] border-e border-[rgba(255,255,255,0.08)] h-full">{SidebarInner}</aside>
        </div>
      )}

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="lg:hidden glass border-b border-[rgba(255,255,255,0.06)] h-14 flex items-center justify-between px-4 sticky top-0 z-40">
          <button data-testid="mobile-menu-btn" onClick={() => setOpen(true)} className="text-white"><Menu className="w-6 h-6" /></button>
          <Logo size="text-lg" />
          <LangSwitcher />
        </header>
        <div className="hidden lg:flex justify-end px-8 pt-6">
          <LangSwitcher />
        </div>
        <main className="flex-1 min-w-0"><Outlet /></main>
      </div>
    </div>
  );
}
