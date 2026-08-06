import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Users, Building2, FolderGit2, KeyRound, MessageSquare, FileText, Code2, Image as ImageIcon, AudioLines, Music, Search as SearchIcon, Trash2, Ban, CheckCircle2, ShieldCheck, Coins, Gift, History, RefreshCw } from "lucide-react";
import { api, formatApiErrorDetail } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const err = (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Something went wrong");

export default function Admin() {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [orgs, setOrgs] = useState([]);
  const [denied, setDenied] = useState(false);
  const [uq, setUq] = useState("");
  const [oq, setOq] = useState("");
  const [confirmDel, setConfirmDel] = useState(null);
  const [creditInput, setCreditInput] = useState({});
  const [grantAmt, setGrantAmt] = useState("");
  const [activity, setActivity] = useState([]);

  const loadStats = () => api.get("/admin/stats").then((r) => setStats(r.data)).catch(() => setDenied(true));
  const loadUsers = () => api.get("/admin/users").then((r) => setUsers(r.data)).catch(() => setDenied(true));
  const loadOrgs = () => api.get("/admin/organizations").then((r) => setOrgs(r.data)).catch(() => {});
  const loadActivity = () => api.get("/admin/activity").then((r) => setActivity(r.data)).catch(() => {});
  useEffect(() => { loadStats(); loadUsers(); loadOrgs(); loadActivity(); }, []);

  if (denied) return <div className="px-5 lg:px-8 py-8 text-[#64748B]" data-testid="admin-denied">Admin access required.</div>;

  const cards = stats ? [
    { label: "Users", value: stats.users, icon: Users },
    { label: "Organizations", value: stats.organizations, icon: Building2 },
    { label: "Projects", value: stats.projects, icon: FolderGit2 },
    { label: "API Keys", value: stats.api_keys, icon: KeyRound },
    { label: "Chat msgs", value: stats.chat_messages, icon: MessageSquare },
    { label: "Documents", value: stats.creations.document, icon: FileText },
    { label: "Code gens", value: stats.creations.code, icon: Code2 },
    { label: "Images", value: stats.creations.image, icon: ImageIcon },
    { label: "Voice", value: stats.creations.audio, icon: AudioLines },
    { label: "Music", value: stats.creations.music, icon: Music },
  ] : [];

  const setRole = async (u, role) => {
    try { await api.patch(`/admin/users/${u.id}/role`, { global_role: role }); toast.success("Role updated"); loadUsers(); loadActivity(); }
    catch (e) { err(e); }
  };
  const toggleSuspend = async (u) => {
    try { await api.patch(`/admin/users/${u.id}/suspend`, { suspended: !u.suspended }); toast.success(u.suspended ? "Account reactivated" : "Account suspended"); loadUsers(); loadActivity(); }
    catch (e) { err(e); }
  };
  const deleteUser = async (u) => {
    try { const { data } = await api.delete(`/admin/users/${u.id}`); toast.success(`User deleted${data.orgs_removed ? ` (+${data.orgs_removed} org cleaned)` : ""}`); setConfirmDel(null); loadUsers(); loadOrgs(); loadStats(); loadActivity(); }
    catch (e) { err(e); }
  };
  const patchOrg = async (o, body, okMsg) => {
    try { const { data } = await api.patch(`/admin/organizations/${o.id}`, body); toast.success(okMsg); setOrgs((prev) => prev.map((x) => x.id === o.id ? { ...x, plan: data.plan, credits: data.credits } : x)); loadActivity(); }
    catch (e) { err(e); }
  };
  const grantAll = async () => {
    const n = parseInt(grantAmt, 10);
    if (!n) { toast.error("Enter a credit amount (use a negative number to deduct)"); return; }
    try { const { data } = await api.post("/admin/credits/grant-all", { add_credits: n }); toast.success(`${n > 0 ? "Granted" : "Deducted"} ${Math.abs(n)} credits across ${data.updated} orgs`); setGrantAmt(""); loadOrgs(); loadActivity(); }
    catch (e) { err(e); }
  };
  const monthlyReset = async () => {
    try { const { data } = await api.post("/admin/credits/monthly-reset"); toast.success(`Refilled ${data.updated} orgs to their plan allowance`); loadOrgs(); loadActivity(); }
    catch (e) { err(e); }
  };

  const fUsers = users.filter((u) => !uq || (u.email + (u.name || "")).toLowerCase().includes(uq.toLowerCase()));
  const fOrgs = orgs.filter((o) => !oq || (o.name + (o.owner_email || "")).toLowerCase().includes(oq.toLowerCase()));
  const tab = "bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] rounded-2xl";
  const pill = "px-2.5 py-1 rounded-full bg-[#12121C] border border-[rgba(255,255,255,0.1)] text-xs";

  return (
    <div className="px-5 lg:px-8 py-8 max-w-6xl">
      <div className="flex items-center gap-2 mb-1"><ShieldCheck className="w-6 h-6 text-[#A855F7]" /><h1 className="font-display text-2xl md:text-3xl font-bold">Admin Panel</h1></div>
      <p className="text-[#94A3B8] mb-8">Manage platform users, organizations and credits.</p>

      <Tabs defaultValue="overview">
        <TabsList className="bg-[#12121C] border border-[rgba(255,255,255,0.08)] mb-6">
          <TabsTrigger value="overview" data-testid="admin-tab-overview" className="data-[state=active]:bg-white/10">Overview</TabsTrigger>
          <TabsTrigger value="users" data-testid="admin-tab-users" className="data-[state=active]:bg-white/10">Users</TabsTrigger>
          <TabsTrigger value="orgs" data-testid="admin-tab-orgs" className="data-[state=active]:bg-white/10">Organizations</TabsTrigger>
          <TabsTrigger value="activity" data-testid="admin-tab-activity" className="data-[state=active]:bg-white/10">Activity</TabsTrigger>
        </TabsList>

        {/* OVERVIEW */}
        <TabsContent value="overview">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {cards.map((c, i) => (
              <motion.div key={i} data-testid={`admin-stat-${c.label.toLowerCase().replace(/\s/g, "-")}`} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: i * 0.03 }}
                className="p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
                <c.icon className="w-5 h-5 mb-3 text-[#A855F7]" />
                <p className="font-display text-2xl font-bold">{c.value}</p>
                <p className="text-[#64748B] text-sm mt-1">{c.label}</p>
              </motion.div>
            ))}
          </div>
        </TabsContent>

        {/* USERS */}
        <TabsContent value="users">
          <div className="relative mb-4 max-w-sm">
            <SearchIcon className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#64748B]" />
            <Input data-testid="admin-user-search" value={uq} onChange={(e) => setUq(e.target.value)} placeholder="Search users…" className="ps-9 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white" />
          </div>
          <div className={tab + " overflow-hidden"}>
            {fUsers.map((u) => (
              <div key={u.id} data-testid={`admin-user-${u.id}`} className="flex flex-col md:flex-row md:items-center justify-between gap-3 px-5 py-4 border-b border-[rgba(255,255,255,0.04)] last:border-0">
                <div className="min-w-0 flex items-center gap-3">
                  <div className="min-w-0">
                    <p className="text-sm text-white truncate flex items-center gap-2">{u.name || u.email}{u.suspended && <span className="px-2 py-0.5 rounded-full bg-red-500/15 text-red-400 text-[10px]">Suspended</span>}</p>
                    <p className="text-xs text-[#64748B] truncate">{u.email} · {u.orgs} org(s) · {u.auth_provider}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Select value={u.global_role} onValueChange={(v) => setRole(u, v)}>
                    <SelectTrigger data-testid={`admin-role-${u.id}`} className="w-28 h-8 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-[#12121C] border-[rgba(255,255,255,0.12)] text-white">
                      <SelectItem value="user" className="focus:bg-white/5">User</SelectItem>
                      <SelectItem value="admin" className="focus:bg-white/5">Admin</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button data-testid={`admin-suspend-${u.id}`} onClick={() => toggleSuspend(u)} size="sm" variant="outline"
                    className={`h-8 border-[rgba(255,255,255,0.12)] ${u.suspended ? "text-emerald-400 hover:text-emerald-300" : "text-amber-400 hover:text-amber-300"} bg-transparent`}>
                    {u.suspended ? <><CheckCircle2 className="w-4 h-4 me-1" /> Reactivate</> : <><Ban className="w-4 h-4 me-1" /> Suspend</>}
                  </Button>
                  {confirmDel === u.id ? (
                    <>
                      <Button data-testid={`admin-delete-confirm-${u.id}`} onClick={() => deleteUser(u)} size="sm" className="h-8 bg-red-500 hover:bg-red-600 text-white">Confirm</Button>
                      <Button onClick={() => setConfirmDel(null)} size="sm" variant="ghost" className="h-8 text-[#94A3B8]">Cancel</Button>
                    </>
                  ) : (
                    <Button data-testid={`admin-delete-${u.id}`} onClick={() => setConfirmDel(u.id)} size="sm" variant="outline" className="h-8 border-[rgba(255,255,255,0.12)] text-red-400 hover:text-red-300 bg-transparent"><Trash2 className="w-4 h-4" /></Button>
                  )}
                </div>
              </div>
            ))}
            {fUsers.length === 0 && <p className="px-5 py-6 text-sm text-[#64748B]">No users found.</p>}
          </div>
        </TabsContent>

        {/* ORGANIZATIONS */}
        <TabsContent value="orgs">
          <div className="p-5 mb-5 rounded-2xl bg-[#12101C] border border-[#A855F7]/40 flex flex-col sm:flex-row sm:items-center gap-3">
            <div className="flex items-center gap-2 text-sm text-white"><Gift className="w-5 h-5 text-[#D946EF]" /> Grant credits to <span className="font-semibold">all</span> organizations</div>
            <div className="flex items-center gap-2 sm:ms-auto">
              <Input data-testid="admin-grant-all-input" type="number" value={grantAmt} onChange={(e) => setGrantAmt(e.target.value)} placeholder="e.g. 500 (or -100)" className="w-40 h-9 bg-[#0C0C14] border-[rgba(255,255,255,0.12)] text-white" />
              <Button data-testid="admin-grant-all-btn" onClick={grantAll} className="h-9 rounded-full ai-gradient-bg text-white border-0"><Coins className="w-4 h-4 me-1" /> Apply to all</Button>
              <Button data-testid="admin-monthly-reset-btn" onClick={monthlyReset} variant="outline" className="h-9 rounded-full border-[rgba(255,255,255,0.15)] bg-transparent text-white"><RefreshCw className="w-4 h-4 me-1" /> Refill to plan</Button>
            </div>
          </div>
          <div className="relative mb-4 max-w-sm">
            <SearchIcon className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#64748B]" />
            <Input data-testid="admin-org-search" value={oq} onChange={(e) => setOq(e.target.value)} placeholder="Search organizations…" className="ps-9 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white" />
          </div>
          <div className={tab + " overflow-hidden"}>
            {fOrgs.map((o) => (
              <div key={o.id} data-testid={`admin-org-${o.id}`} className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 px-5 py-4 border-b border-[rgba(255,255,255,0.04)] last:border-0">
                <div className="min-w-0">
                  <p className="text-sm text-white truncate">{o.name}</p>
                  <p className="text-xs text-[#64748B] truncate">{o.owner_email || "—"} · {o.members} member(s)</p>
                </div>
                <div className="flex flex-wrap items-center gap-2 shrink-0">
                  <span className={pill + " text-[#D946EF] flex items-center gap-1"} data-testid={`admin-org-credits-${o.id}`}><Coins className="w-3 h-3" /> {o.credits}</span>
                  <Select value={o.plan} onValueChange={(v) => patchOrg(o, { plan: v }, "Plan updated")}>
                    <SelectTrigger data-testid={`admin-org-plan-${o.id}`} className="w-28 h-8 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white text-xs capitalize"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-[#12121C] border-[rgba(255,255,255,0.12)] text-white">
                      <SelectItem value="free" className="focus:bg-white/5">Free</SelectItem>
                      <SelectItem value="pro" className="focus:bg-white/5">Pro</SelectItem>
                      <SelectItem value="business" className="focus:bg-white/5">Business</SelectItem>
                    </SelectContent>
                  </Select>
                  <Input data-testid={`admin-org-credit-input-${o.id}`} type="number" value={creditInput[o.id] ?? ""} onChange={(e) => setCreditInput((s) => ({ ...s, [o.id]: e.target.value }))} placeholder="amount" className="w-24 h-8 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white text-xs" />
                  <Button data-testid={`admin-org-add-${o.id}`} onClick={() => patchOrg(o, { add_credits: parseInt(creditInput[o.id] || "0", 10) }, "Credits added")} size="sm" className="h-8 bg-emerald-500/90 hover:bg-emerald-500 text-white">+ Add</Button>
                  <Button data-testid={`admin-org-deduct-${o.id}`} onClick={() => patchOrg(o, { add_credits: -Math.abs(parseInt(creditInput[o.id] || "0", 10)) }, "Credits deducted")} size="sm" variant="outline" className="h-8 border-[rgba(255,255,255,0.12)] text-amber-400 bg-transparent">− Deduct</Button>
                  <Button data-testid={`admin-org-set-${o.id}`} onClick={() => patchOrg(o, { credits: parseInt(creditInput[o.id] || "0", 10) }, "Credits set")} size="sm" variant="outline" className="h-8 border-[rgba(255,255,255,0.12)] text-white bg-transparent">Set</Button>
                </div>
              </div>
            ))}
            {fOrgs.length === 0 && <p className="px-5 py-6 text-sm text-[#64748B]">No organizations found.</p>}
          </div>
        </TabsContent>

        {/* ACTIVITY LOG */}
        <TabsContent value="activity">
          <div className="flex items-center gap-2 mb-4 text-sm text-[#94A3B8]"><History className="w-4 h-4 text-[#A855F7]" /> Every credit change, suspension and deletion is recorded here.</div>
          <div className={tab + " overflow-hidden"}>
            {activity.length === 0 ? <p className="px-5 py-6 text-sm text-[#64748B]" data-testid="admin-activity-empty">No admin activity yet.</p> : activity.map((a) => (
              <div key={a.id} data-testid={`admin-activity-${a.id}`} className="flex items-center justify-between gap-3 px-5 py-3 border-b border-[rgba(255,255,255,0.04)] last:border-0">
                <div className="flex items-center gap-3 min-w-0">
                  <span className={pill + " capitalize " + (a.action === "delete" ? "text-red-400" : a.action === "suspend" ? "text-amber-400" : a.action === "reactivate" ? "text-emerald-400" : "text-[#A855F7]")}>{a.action.replace(/_/g, " ")}</span>
                  <div className="min-w-0">
                    <p className="text-sm text-white truncate">{a.target_label || a.target_type} {a.detail && <span className="text-[#64748B]">· {a.detail}</span>}</p>
                    <p className="text-xs text-[#64748B] truncate">by {a.actor_email}</p>
                  </div>
                </div>
                <span className="text-xs text-[#64748B] shrink-0">{a.created_at ? new Date(a.created_at).toLocaleString() : ""}</span>
              </div>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
