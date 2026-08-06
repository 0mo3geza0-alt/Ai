import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { FileText, Code2, Image as ImageIcon, AudioLines, Video, Music, Search, Clock, Share2, Download, Check } from "lucide-react";
import { api } from "@/context/AuthContext";

const ICONS = { document: FileText, code: Code2, image: ImageIcon, audio: AudioLines, video: Video, music: Music, research: Search };
const TABS = [{ id: "all", l: "All" }, { id: "document", l: "Docs" }, { id: "code", l: "Code" }, { id: "image", l: "Images" }, { id: "audio", l: "Voice" }, { id: "music", l: "Music" }, { id: "research", l: "Research" }];

export default function Creations() {
  const { activeOrg } = useOutletContext();
  const oid = activeOrg.id;
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [blobs, setBlobs] = useState({});
  const [shared, setShared] = useState({});

  const load = () => { setLoading(true); api.get(`/orgs/${oid}/creations`).then(({ data }) => setItems(data)).finally(() => setLoading(false)); };
  useEffect(() => { load(); }, [oid]); // eslint-disable-line

  useEffect(() => {
    items.filter((i) => i.url && i.status === "done" && !blobs[i.id]).forEach(async (i) => {
      try { const res = await api.get(i.url.replace("/api", ""), { responseType: "blob" }); setBlobs((b) => ({ ...b, [i.id]: URL.createObjectURL(res.data) })); } catch { /* ignore */ }
    });
  }, [items]); // eslint-disable-line

  const share = async (id) => {
    let link;
    try {
      const { data } = await api.post(`/orgs/${oid}/creations/${id}/share`);
      link = `${window.location.origin}${data.path}`;
    } catch { toast.error("Could not create share link"); return; }
    setShared((s) => ({ ...s, [id]: true })); setTimeout(() => setShared((s) => ({ ...s, [id]: false })), 2000);
    try {
      await navigator.clipboard.writeText(link);
      toast.success("Public link copied to clipboard");
    } catch {
      toast.success("Public link created", { description: link, duration: 8000 });
    }
  };

  const exportDoc = async (id, fmt) => {
    try {
      const res = await api.get(`/orgs/${oid}/creations/${id}/export?format=${fmt}`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = `creation-${id}.${fmt}`; a.click(); URL.revokeObjectURL(url);
    } catch { toast.error("Export failed"); }
  };

  const EXT = { image: "png", video: "mp4", audio: "mp3", music: "wav" };
  const downloadCreation = async (c) => {
    try {
      const res = await api.get(c.url.replace("/api", ""), { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const name = `${(c.title || c.kind).replace(/[^a-z0-9]+/gi, "-").slice(0, 40) || "nexus"}.${EXT[c.kind] || "bin"}`;
      const a = document.createElement("a"); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
      toast.success("Downloaded to your device");
    } catch { toast.error("Download failed"); }
  };

  const filtered = items.filter((i) => filter === "all" || i.kind === filter);

  return (
    <div className="px-5 lg:px-8 py-8 max-w-5xl">
      <h1 className="font-display text-2xl md:text-3xl font-bold mb-1">Creations</h1>
      <p className="text-[#94A3B8] mb-8">Everything generated in {activeOrg.name}.</p>

      <div className="flex flex-wrap gap-2 mb-6">
        {TABS.map((t) => <button key={t.id} data-testid={`creations-filter-${t.id}`} onClick={() => setFilter(t.id)} className={`px-4 py-2 rounded-full text-sm border transition-colors ${filter === t.id ? "ai-gradient-bg text-white border-transparent" : "bg-transparent text-[#94A3B8] border-[rgba(255,255,255,0.12)] hover:text-white"}`}>{t.l}</button>)}
      </div>

      {loading ? <p className="text-[#64748B]">Loading…</p> : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center text-center py-20 text-[#64748B]"><Clock className="w-10 h-10 mb-3 opacity-40" /><p>No creations yet.</p></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((c, i) => {
            const Icon = ICONS[c.kind] || FileText;
            const isText = ["document", "code", "research"].includes(c.kind);
            return (
              <motion.div key={c.id} data-testid={`creation-${c.id}`} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: i * 0.03 }}
                className="p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] flex flex-col">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-xs text-[#94A3B8] min-w-0"><Icon className="w-4 h-4 text-[#A855F7] shrink-0" /> <span className="capitalize">{c.kind}</span> · {new Date(c.created_at).toLocaleDateString()}</div>
                  <div className="flex items-center gap-1 shrink-0">
                    {isText && <button data-testid={`export-${c.id}`} onClick={() => exportDoc(c.id, "md")} className="p-1.5 text-[#64748B] hover:text-white transition-colors" title="Export .md"><Download className="w-4 h-4" /></button>}
                    {!isText && c.status === "done" && c.url && <button data-testid={`download-${c.id}`} onClick={() => downloadCreation(c)} className="p-1.5 text-[#64748B] hover:text-white transition-colors" title="Download to device"><Download className="w-4 h-4" /></button>}
                    <button data-testid={`share-${c.id}`} onClick={() => share(c.id)} className="p-1.5 text-[#64748B] hover:text-white transition-colors" title="Share">{shared[c.id] ? <Check className="w-4 h-4 text-emerald-400" /> : <Share2 className="w-4 h-4" />}</button>
                  </div>
                </div>
                <p className="text-sm text-white mb-3 line-clamp-1">{c.title || c.prompt}</p>
                {c.status === "processing" ? <div className="h-24 rounded-xl bg-[#12121C] flex items-center justify-center text-xs text-[#64748B]"><span className="dot" /> generating…</div> :
                  c.kind === "image" ? (blobs[c.id] ? <img src={blobs[c.id]} alt="" className="rounded-xl w-full h-auto max-h-64 object-cover" /> : <div className="h-40 rounded-xl bg-[#12121C] flex items-center justify-center"><span className="dot" /></div>) :
                  c.kind === "video" ? (blobs[c.id] ? <video src={blobs[c.id]} controls className="rounded-xl w-full max-h-64" /> : <div className="h-40 rounded-xl bg-[#12121C]" />) :
                  (c.kind === "audio" || c.kind === "music") ? (blobs[c.id] ? <audio src={blobs[c.id]} controls className="w-full" /> : <div className="h-12 rounded-xl bg-[#12121C]" />) :
                  <pre className="text-xs text-[#94A3B8] whitespace-pre-wrap line-clamp-6 font-mono">{c.content}</pre>}
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
