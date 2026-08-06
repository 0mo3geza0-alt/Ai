import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { motion } from "framer-motion";
import { FileText, Code2, Image as ImageIcon, Video, Music, Search, AudioLines, Sparkles } from "lucide-react";
import { Logo } from "@/components/shared";
import { Button } from "@/components/ui/button";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const ICONS = { document: FileText, code: Code2, image: ImageIcon, audio: AudioLines, video: Video, music: Music, research: Search };
const TABS = [{ id: "all", l: "All" }, { id: "image", l: "Images" }, { id: "video", l: "Video" }, { id: "music", l: "Music" }, { id: "document", l: "Docs" }, { id: "research", l: "Research" }];

function Media({ token, url, kind }) {
  const [blob, setBlob] = useState(null);
  useEffect(() => { (async () => { try { const r = await axios.get(`${API}/public/creations/${token}/file`, { responseType: "blob" }); setBlob(URL.createObjectURL(r.data)); } catch { /* ignore */ } })(); }, [token]); // eslint-disable-line
  if (!blob) return <div className="aspect-video rounded-xl bg-[#12121C] flex items-center justify-center"><span className="dot" /></div>;
  if (kind === "image") return <img src={blob} alt="" className="w-full h-full object-cover" />;
  if (kind === "video") return <video src={blob} controls className="w-full" />;
  return <audio src={blob} controls className="w-full" />;
}

export default function Gallery() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/public/gallery`, { params: { kind: filter } }).then(({ data }) => setItems(data)).catch(() => setItems([])).finally(() => setLoading(false));
  }, [filter]);

  return (
    <div className="min-h-screen text-[#F8FAFC] relative z-10">
      <header className="fixed top-0 inset-x-0 z-50 glass border-b border-[rgba(255,255,255,0.06)]">
        <div className="max-w-6xl mx-auto px-5 h-16 flex items-center justify-between">
          <Logo />
          <Link to="/register"><Button className="rounded-full ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity">Create yours</Button></Link>
        </div>
      </header>

      <section className="pt-28 pb-10 px-5 max-w-6xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full glass border border-[rgba(255,255,255,0.1)] text-xs text-[#94A3B8] mb-5"><Sparkles className="w-3.5 h-3.5" /> Community Gallery</div>
        <h1 className="font-display text-4xl sm:text-5xl font-bold tracking-tight mb-4">Made with <span className="ai-gradient-text">VibeVerse</span></h1>
        <p className="text-[#94A3B8] max-w-xl mx-auto mb-8">A public showcase of creations shared by the community.</p>
        <div className="flex flex-wrap justify-center gap-2">
          {TABS.map((t) => <button key={t.id} data-testid={`gallery-filter-${t.id}`} onClick={() => setFilter(t.id)} className={`px-4 py-2 rounded-full text-sm border transition-colors ${filter === t.id ? "ai-gradient-bg text-white border-transparent" : "bg-transparent text-[#94A3B8] border-[rgba(255,255,255,0.12)] hover:text-white"}`}>{t.l}</button>)}
        </div>
      </section>

      <section className="px-5 max-w-6xl mx-auto pb-20">
        {loading ? <p className="text-center text-[#64748B]">Loading…</p> : items.length === 0 ? (
          <div className="text-center py-20 text-[#64748B]">No shared creations yet. Be the first — share one from your dashboard!</div>
        ) : (
          <div className="columns-1 sm:columns-2 lg:columns-3 gap-5 [column-fill:_balance]">
            {items.map((c, i) => {
              const Icon = ICONS[c.kind] || FileText;
              return (
                <motion.div key={c.token} data-testid={`gallery-item-${i}`} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.4 }}
                  className="mb-5 break-inside-avoid rounded-2xl overflow-hidden bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] hover:border-[rgba(255,255,255,0.18)] transition-colors">
                  <Link to={`/share/${c.token}`}>
                    {["image", "video", "audio", "music"].includes(c.kind) ? <Media token={c.token} url={c.url} kind={c.kind === "music" ? "audio" : c.kind} /> : (
                      <div className="p-5"><Icon className="w-5 h-5 text-[#A855F7] mb-3" /><pre className="text-xs text-[#94A3B8] whitespace-pre-wrap line-clamp-6 font-mono">{c.content}</pre></div>
                    )}
                    <div className="p-4 flex items-center gap-2 text-xs text-[#94A3B8]"><Icon className="w-4 h-4 shrink-0" /><span className="truncate">{c.title || c.prompt}</span></div>
                  </Link>
                </motion.div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
