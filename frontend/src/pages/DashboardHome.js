import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Coins, Crown, MessageSquare, PenLine, Image as ImageIcon, ArrowRight } from "lucide-react";
import { useApp, api } from "@/context/AppContext";

export default function DashboardHome() {
  const { t, user } = useApp();
  const nav = useNavigate();
  const [usage, setUsage] = useState(null);

  useEffect(() => { api.get("/usage").then(({ data }) => setUsage(data)).catch(() => {}); }, []);

  const stats = [
    { label: t.dash.creditsLeft, value: usage?.credits ?? user?.credits ?? "—", icon: Coins, accent: "text-[#D946EF]" },
    { label: t.dash.plan, value: (usage?.plan ?? user?.plan) === "pro" ? t.pricing.pro : t.pricing.free, icon: Crown, accent: "text-[#4F46E5]" },
    { label: t.dash.chats, value: usage?.counts?.chat ?? 0, icon: MessageSquare, accent: "text-[#0EA5E9]" },
    { label: t.dash.texts, value: usage?.counts?.text ?? 0, icon: PenLine, accent: "text-[#A855F7]" },
    { label: t.dash.images, value: usage?.counts?.image ?? 0, icon: ImageIcon, accent: "text-[#D946EF]" },
  ];

  const actions = [
    { label: t.dash.startChat, icon: MessageSquare, to: "/app/chat" },
    { label: t.dash.genText, icon: PenLine, to: "/app/text" },
    { label: t.dash.genImage, icon: ImageIcon, to: "/app/image" },
  ];

  return (
    <div className="px-5 lg:px-8 py-8 max-w-5xl">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
        <h1 className="font-display text-2xl md:text-3xl font-bold mb-1">{t.dash.welcome}, {user?.name?.split(" ")[0]}</h1>
        <p className="text-[#94A3B8] mb-8">{t.dash.subtitle}</p>
      </motion.div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-10">
        {stats.map((s, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: i * 0.05 }}
            data-testid={`stat-card-${i}`}
            className="p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
            <s.icon className={`w-5 h-5 mb-4 ${s.accent}`} />
            <p className="font-display text-2xl font-bold">{s.value}</p>
            <p className="text-[#64748B] text-sm mt-1">{s.label}</p>
          </motion.div>
        ))}
      </div>

      <h2 className="font-display text-lg font-semibold mb-4">{t.dash.quick}</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {actions.map((a, i) => (
          <button key={i} onClick={() => nav(a.to)} data-testid={`quick-action-${i}`}
            className="group flex items-center justify-between p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] hover:border-[rgba(255,255,255,0.18)] transition-colors text-start">
            <span className="flex items-center gap-3">
              <span className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center group-hover:ai-gradient-bg transition-colors">
                <a.icon className="w-5 h-5 text-[#A855F7] group-hover:text-white transition-colors" />
              </span>
              <span className="font-medium">{a.label}</span>
            </span>
            <ArrowRight className="w-4 h-4 text-[#64748B] group-hover:text-white transition-colors rtl:rotate-180" />
          </button>
        ))}
      </div>
    </div>
  );
}
