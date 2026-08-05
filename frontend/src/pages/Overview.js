import { useEffect, useState } from "react";
import { useOutletContext, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { FolderGit2, Users, KeyRound, ShieldCheck, ArrowRight } from "lucide-react";
import { api } from "@/context/AuthContext";

export default function Overview() {
  const { activeOrg, user } = useOutletContext();
  const nav = useNavigate();
  const [counts, setCounts] = useState({ projects: 0, members: 0, keys: 0 });

  useEffect(() => {
    const oid = activeOrg.id;
    Promise.all([
      api.get(`/orgs/${oid}/projects`).then((r) => r.data.length).catch(() => 0),
      api.get(`/orgs/${oid}/members`).then((r) => r.data.length).catch(() => 0),
      api.get(`/orgs/${oid}/api-keys`).then((r) => r.data.length).catch(() => 0),
    ]).then(([projects, members, keys]) => setCounts({ projects, members, keys }));
  }, [activeOrg]);

  const stats = [
    { label: "Projects", value: counts.projects, icon: FolderGit2, accent: "text-[#0EA5E9]" },
    { label: "Members", value: counts.members, icon: Users, accent: "text-[#A855F7]" },
    { label: "API Keys", value: counts.keys, icon: KeyRound, accent: "text-[#D946EF]" },
    { label: "Your Role", value: activeOrg.role, icon: ShieldCheck, accent: "text-emerald-400" },
  ];

  return (
    <div className="px-5 lg:px-8 py-8 max-w-5xl">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
        <h1 className="font-display text-2xl md:text-3xl font-bold mb-1">Welcome back, {user?.name?.split(" ")[0]}</h1>
        <p className="text-[#94A3B8] mb-8">Organization: <span className="text-white">{activeOrg.name}</span></p>
      </motion.div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
        {stats.map((s, i) => (
          <motion.div key={i} data-testid={`overview-stat-${s.label.toLowerCase().replace(/\s/g, "-")}`}
            initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: i * 0.05 }}
            className="p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
            <s.icon className={`w-5 h-5 mb-4 ${s.accent}`} />
            <p className="font-display text-2xl font-bold capitalize">{s.value}</p>
            <p className="text-[#64748B] text-sm mt-1">{s.label}</p>
          </motion.div>
        ))}
      </div>

      <h2 className="font-display text-lg font-semibold mb-4">Quick actions</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[
          { label: "Create a project", to: "/app/projects", icon: FolderGit2 },
          { label: "Invite a team member", to: "/app/organization", icon: Users },
        ].map((a, i) => (
          <button key={i} onClick={() => nav(a.to)} data-testid={`quick-${i}`}
            className="group flex items-center justify-between p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] hover:border-[rgba(255,255,255,0.18)] transition-colors text-start">
            <span className="flex items-center gap-3">
              <span className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center group-hover:ai-gradient-bg transition-colors">
                <a.icon className="w-5 h-5 text-[#A855F7] group-hover:text-white transition-colors" />
              </span>
              <span className="font-medium">{a.label}</span>
            </span>
            <ArrowRight className="w-4 h-4 text-[#64748B] group-hover:text-white transition-colors" />
          </button>
        ))}
      </div>
    </div>
  );
}
