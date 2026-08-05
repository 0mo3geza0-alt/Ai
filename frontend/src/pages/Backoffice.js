import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ShieldCheck, Users, Building2, Trash2, Crown, Coins, LogOut, Search } from "lucide-react";
import { api, setAuthToken } from "@/context/AuthContext";
import { Logo, Dots } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function Backoffice() {
  const [me, setMe] = useState(null);          // null=checking, false=not admin, obj=admin
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const check = async () => {
    try { const { data } = await api.get("/auth/me"); setMe(data.global_role === "admin" ? data : false); }
    catch { setMe(false); }
  };
  useEffect(() => { check(); }, []);

  const login = async (e) => {
    e.preventDefault(); setLoading(true);
    try {
      const { data } = await api.post("/auth/login", { email, password });
      setAuthToken(data.token);
      if (data.user.global_role !== "admin") { toast.error("This account is not an administrator."); setMe(false); }
      else setMe(data.user);
    } catch (err) { toast.error("Invalid credentials"); }
    finally { setLoading(false); }
  };

  if (me === null) return <div className="min-h-screen flex items-center justify-center bg-[#05050A]"><Dots /></div>;

  if (!me) return (
    <div className="min-h-screen flex flex-col text-[#F8FAFC]">
      <div className="p-5"><Logo /></div>
      <div className="flex-1 flex items-center justify-center px-5">
        <div className="w-full max-w-md p-8 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.08)]">
          <div className="flex items-center gap-2 mb-1"><ShieldCheck className="w-5 h-5 text-[#D946EF]" /><h1 className="font-display text-2xl font-bold">Admin Backoffice</h1></div>
          <p className="text-[#94A3B8] text-sm mb-8">Restricted access — administrators only.</p>
          <form onSubmit={login} className="space-y-5">
            <Input data-testid="admin-email-input" type="email" required placeholder="admin@email.com" value={email} onChange={(e) => setEmail(e.target.value)} className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" />
            <Input data-testid="admin-password-input" type="password" required placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" />
            <Button data-testid="admin-login-btn" type="submit" disabled={loading} className="w-full rounded-full h-11 ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity">{loading ? <Dots /> : "Enter Backoffice"}</Button>
          </form>
        </div>
      </div>
    </div>
  );

  return <Panel me={me} onLogout={async () => { try { await api.post("/auth/logout"); } catch {} setAuthToken(null); setMe(false); }} />;
}

function Panel({ me, onLogout }) {
  const [tab, setTab] = useState("overview");
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [orgs, setOrgs] = useState([]);
  const [q, setQ] = useState("");

  const load = async () => {
    const [s, u, o] = await Promise.all([
      api.get("/admin/stats").then((r) => r.data).catch(() => null),
      api.get("/admin/users").then((r) => r.data).catch(() => []),
      api.get("/admin/organizations").then((r) => r.data).catch(() => []),
    ]);
    setStats(s); setUsers(u); setOrgs(o);
  };
  useEffect(() => { load(); }, []);

  const setRole = async (id, role) => { try { await api.patch(`/admin/users/${id}/role`, { global_role: role }); toast.success("Role updated"); load(); } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } };
  const delUser = async (id) => { if (!window.confirm("Delete this user permanently?")) return; try { await api.delete(`/admin/users/${id}`); toast.success("User deleted"); load(); } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } };
  const addCredits = async (id, amt) => { try { const { data } = await api.patch(`/admin/organizations/${id}`, { add_credits: amt }); toast.success(`Credits: ${data.credits}`); load(); } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } };
  const setPlan = async (id, plan) => { try { await api.patch(`/admin/organizations/${id}`, { plan }); toast.success("Plan updated"); load(); } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } };
  const setCredits = async (id) => { const v = window.prompt("Set credits to:"); if (v == null) return; try { const { data } = await api.patch(`/admin/organizations/${id}`, { credits: parseInt(v, 10) || 0 }); toast.success(`Credits: ${data.credits}`); load(); } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } };
  const switchTab = (id) => { setQ(""); setTab(id); };

  const fUsers = users.filter((u) => !q || (u.email + (u.name || "")).toLowerCase().includes(q.toLowerCase()));
  const fOrgs = orgs.filter((o) => !q || (o.name + (o.owner_email || "")).toLowerCase().includes(q.toLowerCase()));

  const cards = stats ? [["Users", stats.users], ["Orgs", stats.organizations], ["Projects", stats.projects], ["API Keys", stats.api_keys], ["Chats", stats.chat_messages], ["Images", stats.creations.image], ["Videos", stats.creations.video], ["Music", stats.creations.music]] : [];

  return (
    <div className="min-h-screen text-[#F8FAFC] relative z-10">
      <header className="glass border-b border-[rgba(255,255,255,0.06)] sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-5 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2"><ShieldCheck className="w-5 h-5 text-[#D946EF]" /><span className="font-display font-bold">Backoffice</span></div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-[#94A3B8] hidden sm:inline">{me.email}</span>
            <button data-testid="admin-logout-btn" onClick={onLogout} className="flex items-center gap-2 text-sm text-[#94A3B8] hover:text-white transition-colors"><LogOut className="w-4 h-4" /> Sign out</button>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-5 py-8">
        <div className="flex gap-2 mb-8">
          {[["overview", "Overview"], ["users", "Users"], ["orgs", "Organizations"]].map(([id, l]) => (
            <button key={id} data-testid={`admin-tab-${id}`} onClick={() => switchTab(id)} className={`px-4 py-2 rounded-full text-sm border transition-colors ${tab === id ? "ai-gradient-bg text-white border-transparent" : "bg-transparent text-[#94A3B8] border-[rgba(255,255,255,0.12)] hover:text-white"}`}>{l}</button>
          ))}
        </div>

        {tab === "overview" && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {cards.map(([l, v], i) => (
              <div key={i} data-testid={`admin-card-${l.toLowerCase()}`} className="p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
                <p className="font-display text-2xl font-bold">{v}</p><p className="text-[#64748B] text-sm mt-1">{l}</p>
              </div>
            ))}
          </div>
        )}

        {tab !== "overview" && (
          <div className="relative mb-4">
            <Search className="w-4 h-4 absolute start-3 top-1/2 -translate-y-1/2 text-[#64748B]" />
            <Input data-testid="admin-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" className="ps-9 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" />
          </div>
        )}

        {tab === "users" && (
          <div className="rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] overflow-hidden">
            {fUsers.map((u) => (
              <div key={u.id} data-testid={`admin-user-row-${u.id}`} className="flex items-center justify-between px-5 py-3 border-b border-[rgba(255,255,255,0.04)] last:border-0">
                <div className="min-w-0"><p className="text-sm text-white truncate">{u.name || u.email} {u.global_role === "admin" && <Crown className="w-3.5 h-3.5 inline text-[#D946EF]" />}</p><p className="text-xs text-[#64748B] truncate">{u.email} · {u.orgs} orgs · {u.auth_provider}</p></div>
                <div className="flex items-center gap-2 shrink-0">
                  <button data-testid={`toggle-role-${u.id}`} onClick={() => setRole(u.id, u.global_role === "admin" ? "user" : "admin")} className="text-xs px-3 py-1.5 rounded-full bg-[#12121C] border border-[rgba(255,255,255,0.12)] text-[#94A3B8] hover:text-white transition-colors">{u.global_role === "admin" ? "Make user" : "Make admin"}</button>
                  <button data-testid={`delete-user-${u.id}`} onClick={() => delUser(u.id)} className="p-1.5 text-[#64748B] hover:text-red-400 transition-colors"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === "orgs" && (
          <div className="space-y-3">
            {fOrgs.map((o) => (
              <div key={o.id} data-testid={`admin-org-row-${o.id}`} className="p-4 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="min-w-0"><p className="text-sm text-white truncate">{o.name}</p><p className="text-xs text-[#64748B] truncate">{o.owner_email} · {o.members} members</p></div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="flex items-center gap-1.5 text-sm text-white px-3 py-1.5 rounded-full bg-[#12121C] border border-[rgba(255,255,255,0.1)]"><Coins className="w-3.5 h-3.5 text-[#D946EF]" />{o.credits}</span>
                  <span className="text-xs px-2.5 py-1 rounded-full bg-[#12121C] border border-[rgba(255,255,255,0.1)] capitalize text-[#94A3B8]">{o.plan}</span>
                  <button data-testid={`add-credits-${o.id}`} onClick={() => addCredits(o.id, 500)} className="text-xs px-3 py-1.5 rounded-full ai-gradient-bg text-white hover:opacity-90 transition-opacity">+500</button>
                  <button data-testid={`set-credits-${o.id}`} onClick={() => setCredits(o.id)} className="text-xs px-3 py-1.5 rounded-full bg-[#12121C] border border-[rgba(255,255,255,0.12)] text-[#94A3B8] hover:text-white transition-colors">Set</button>
                  <button data-testid={`toggle-plan-${o.id}`} onClick={() => setPlan(o.id, o.plan === "pro" ? "free" : "pro")} className="text-xs px-3 py-1.5 rounded-full bg-[#12121C] border border-[rgba(255,255,255,0.12)] text-[#94A3B8] hover:text-white transition-colors">{o.plan === "pro" ? "→ Free" : "→ Pro"}</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
