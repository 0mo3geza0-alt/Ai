import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { PenLine, Image as ImageIcon, Trash2, Clock } from "lucide-react";
import { toast } from "sonner";
import { useApp, api } from "@/context/AppContext";

export default function History() {
  const { t } = useApp();
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);

  const load = async () => { setLoading(true); try { const { data } = await api.get("/history"); setItems(data); } finally { setLoading(false); } };
  useEffect(() => { load(); }, []);

  const del = async (id) => { await api.delete(`/history/${id}`); setItems((x) => x.filter((i) => i.id !== id)); toast.success("Deleted"); };

  const filtered = items.filter((i) => filter === "all" || i.kind === filter);
  const tabs = [{ id: "all", label: t.history.all }, { id: "text", label: t.history.texts }, { id: "image", label: t.history.images }];

  return (
    <div className="px-5 lg:px-8 py-8 max-w-4xl">
      <h1 className="font-display text-2xl md:text-3xl font-bold mb-1">{t.history.title}</h1>
      <p className="text-[#94A3B8] mb-8">{t.history.sub}</p>

      <div className="flex gap-2 mb-6">
        {tabs.map((tb) => (
          <button key={tb.id} onClick={() => setFilter(tb.id)} data-testid={`history-filter-${tb.id}`}
            className={`px-4 py-2 rounded-full text-sm transition-colors border ${filter === tb.id ? "ai-gradient-bg text-white border-transparent" : "bg-transparent text-[#94A3B8] border-[rgba(255,255,255,0.12)] hover:text-white"}`}>
            {tb.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-[#64748B]">{t.common.loading}</p>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center text-center py-20 text-[#64748B]">
          <Clock className="w-10 h-10 mb-3 opacity-40" /><p>{t.history.empty}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map((it, idx) => (
            <motion.div key={it.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: idx * 0.03 }}
              data-testid={`history-item-${it.id}`}
              className="p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
              <div className="flex items-start justify-between gap-3 mb-3">
                <span className="flex items-center gap-2 text-xs text-[#94A3B8]">
                  {it.kind === "image" ? <ImageIcon className="w-4 h-4 text-[#D946EF]" /> : <PenLine className="w-4 h-4 text-[#A855F7]" />}
                  {new Date(it.created_at).toLocaleString()}
                </span>
                <button onClick={() => del(it.id)} data-testid={`history-delete-${it.id}`} className="text-[#64748B] hover:text-red-400 transition-colors"><Trash2 className="w-4 h-4" /></button>
              </div>
              <p className="text-sm text-[#94A3B8] mb-3"><span className="text-[#64748B]">{t.history.prompt}: </span>{it.prompt}</p>
              {it.kind === "image" ? (
                <img src={it.result} alt="" className="max-h-64 rounded-xl border border-[rgba(255,255,255,0.06)]" />
              ) : (
                <p className="text-sm text-[#F8FAFC] leading-relaxed whitespace-pre-wrap line-clamp-6">{it.result}</p>
              )}
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
