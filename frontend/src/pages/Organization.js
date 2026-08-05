import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { toast } from "sonner";
import { UserPlus, Users, Plus, Trash2, Shield } from "lucide-react";
import { api, formatApiErrorDetail } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const ROLES = ["admin", "member", "viewer"];

export default function Organization() {
  const { activeOrg } = useOutletContext();
  const oid = activeOrg.id;
  const canManage = ["owner", "admin"].includes(activeOrg.role);
  const [members, setMembers] = useState([]);
  const [teams, setTeams] = useState([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [teamName, setTeamName] = useState("");

  const load = async () => {
    const [m, t] = await Promise.all([
      api.get(`/orgs/${oid}/members`).then((r) => r.data).catch(() => []),
      api.get(`/orgs/${oid}/teams`).then((r) => r.data).catch(() => []),
    ]);
    setMembers(m); setTeams(t);
  };
  useEffect(() => { load(); }, [oid]); // eslint-disable-line

  const addMember = async (e) => {
    e.preventDefault();
    try { await api.post(`/orgs/${oid}/members`, { email, role }); setEmail(""); toast.success("Member added"); load(); }
    catch (err) { toast.error(formatApiErrorDetail(err.response?.data?.detail)); }
  };
  const removeMember = async (uid) => {
    try { await api.delete(`/orgs/${oid}/members/${uid}`); toast.success("Removed"); load(); }
    catch (err) { toast.error(formatApiErrorDetail(err.response?.data?.detail)); }
  };
  const addTeam = async (e) => {
    e.preventDefault();
    try { await api.post(`/orgs/${oid}/teams`, { name: teamName }); setTeamName(""); toast.success("Team created"); load(); }
    catch (err) { toast.error(formatApiErrorDetail(err.response?.data?.detail)); }
  };

  return (
    <div className="px-5 lg:px-8 py-8 max-w-3xl">
      <h1 className="font-display text-2xl md:text-3xl font-bold mb-1">Organization</h1>
      <p className="text-[#94A3B8] mb-8">{activeOrg.name} · your role: <span className="text-white capitalize">{activeOrg.role}</span></p>

      {/* members */}
      <section className="p-6 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] mb-6">
        <h2 className="font-display text-lg font-semibold mb-5 flex items-center gap-2"><Users className="w-5 h-5 text-[#A855F7]" /> Members</h2>
        {canManage && (
          <form onSubmit={addMember} className="flex flex-col sm:flex-row gap-3 mb-6">
            <Input data-testid="member-email-input" type="email" required placeholder="member@email.com" value={email} onChange={(e) => setEmail(e.target.value)}
              className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" />
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger data-testid="member-role-select" className="sm:w-36 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#12121C] border-[rgba(255,255,255,0.12)] text-white">
                {ROLES.map((r) => <SelectItem key={r} value={r} className="capitalize focus:bg-white/5">{r}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button data-testid="add-member-btn" type="submit" className="rounded-full ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity"><UserPlus className="w-4 h-4 me-2" /> Add</Button>
          </form>
        )}
        <div className="space-y-2">
          {members.map((m) => (
            <div key={m.id} data-testid={`member-${m.user_id}`} className="flex items-center justify-between px-4 py-3 rounded-xl bg-[#12121C] border border-[rgba(255,255,255,0.06)]">
              <div className="min-w-0">
                <p className="text-sm text-white truncate">{m.name || m.email}</p>
                <p className="text-xs text-[#64748B] truncate">{m.email}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1.5 text-xs text-[#94A3B8] capitalize"><Shield className="w-3.5 h-3.5" /> {m.role}</span>
                {canManage && m.role !== "owner" && (
                  <button data-testid={`remove-member-${m.user_id}`} onClick={() => removeMember(m.user_id)} className="text-[#64748B] hover:text-red-400 transition-colors"><Trash2 className="w-4 h-4" /></button>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* teams */}
      <section className="p-6 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
        <h2 className="font-display text-lg font-semibold mb-5">Teams</h2>
        {canManage && (
          <form onSubmit={addTeam} className="flex gap-3 mb-6">
            <Input data-testid="team-name-input" required placeholder="Team name" value={teamName} onChange={(e) => setTeamName(e.target.value)}
              className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" />
            <Button data-testid="add-team-btn" type="submit" className="rounded-full ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity"><Plus className="w-4 h-4 me-2" /> Create</Button>
          </form>
        )}
        {teams.length === 0 ? <p className="text-sm text-[#64748B]">No teams yet.</p> : (
          <div className="flex flex-wrap gap-2">
            {teams.map((t) => <span key={t.id} data-testid={`team-${t.id}`} className="px-3 py-1.5 rounded-full text-sm bg-[#12121C] border border-[rgba(255,255,255,0.1)] text-[#94A3B8]">{t.name}</span>)}
          </div>
        )}
      </section>
    </div>
  );
}
