import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Users, Building2, FolderGit2, KeyRound, MessageSquare, FileText, Code2, Image as ImageIcon, AudioLines } from "lucide-react";
import { api } from "@/context/AuthContext";

export default function Admin() {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [err, setErr] = useState(false);

  useEffect(() => {
    Promise.all([
      api.get("/admin/stats").then((r) => r.data),
      api.get("/admin/users").then((r) => r.data),
    ]).then(([s, u]) => { setStats(s); setUsers(u); }).catch(() => setErr(true));
  }, []);

  if (err) return <div className="px-5 lg:px-8 py-8 text-[#64748B]">Admin access required.</div>;

  const cards = stats ? [
    { label: "Users", value: stats.users, icon: Users },
    { label: "Organizations", value: stats.organizations, icon: Building2 },
    { label: "Projects", value: stats.projects, icon: FolderGit2 },
    { label: "API Keys", value: stats.api_keys, icon: KeyRound },
    { label: "Chat msgs", value: stats.chat_messages, icon: MessageSquare },
    { label: "Documents", value: stats.creations.document, icon: FileText },
    { label: "Code gens", value: stats.creations.code, icon: Code2 },
    { label: "Images", value: stats.creations.image, icon: ImageIcon },
    { label: "Audio", value: stats.creations.audio, icon: AudioLines },
  ] : [];

  return (
    <div className="px-5 lg:px-8 py-8 max-w-5xl">
      <h1 className="font-display text-2xl md:text-3xl font-bold mb-1">Admin Panel</h1>
      <p className="text-[#94A3B8] mb-8">Platform-wide metrics and users.</p>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-10">
        {cards.map((c, i) => (
          <motion.div key={i} data-testid={`admin-stat-${c.label.toLowerCase().replace(/\s/g, "-")}`} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: i * 0.03 }}
            className="p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
            <c.icon className="w-5 h-5 mb-3 text-[#A855F7]" />
            <p className="font-display text-2xl font-bold">{c.value}</p>
            <p className="text-[#64748B] text-sm mt-1">{c.label}</p>
          </motion.div>
        ))}
      </div>

      <h2 className="font-display text-lg font-semibold mb-4">Users</h2>
      <div className="rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] overflow-hidden">
        {users.map((u) => (
          <div key={u.id} data-testid={`admin-user-${u.id}`} className="flex items-center justify-between px-5 py-3 border-b border-[rgba(255,255,255,0.04)] last:border-0">
            <div className="min-w-0"><p className="text-sm text-white truncate">{u.name || u.email}</p><p className="text-xs text-[#64748B] truncate">{u.email}</p></div>
            <div className="flex items-center gap-2 text-xs">
              <span className="px-2.5 py-1 rounded-full bg-[#12121C] border border-[rgba(255,255,255,0.1)] capitalize text-[#94A3B8]">{u.global_role}</span>
              <span className="px-2.5 py-1 rounded-full bg-[#12121C] border border-[rgba(255,255,255,0.1)] text-[#64748B]">{u.auth_provider}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
