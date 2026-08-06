import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { Download } from "lucide-react";
import { Logo } from "@/components/shared";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const EXT = { image: "png", video: "mp4", audio: "mp3", music: "wav" };

export default function SharePage() {
  const { token } = useParams();
  const [c, setC] = useState(null);
  const [err, setErr] = useState(false);
  const [media, setMedia] = useState(null);

  useEffect(() => {
    axios.get(`${API}/public/creations/${token}`).then(async ({ data }) => {
      setC(data);
      if (data.url) { try { const res = await axios.get(`${API}/public/creations/${token}/file`, { responseType: "blob" }); setMedia(URL.createObjectURL(res.data)); } catch { /* ignore */ } }
    }).catch(() => setErr(true));
  }, [token]);

  const dlName = c ? `${(c.title || c.kind).replace(/[^a-z0-9]+/gi, "-").slice(0, 40) || "vibeverse"}.${EXT[c.kind] || "bin"}` : "vibeverse";

  return (
    <div className="min-h-screen text-[#F8FAFC] relative z-10">
      <header className="glass border-b border-[rgba(255,255,255,0.06)]"><div className="max-w-3xl mx-auto px-5 h-16 flex items-center"><Logo /></div></header>
      <main className="max-w-3xl mx-auto px-5 py-12">
        {err ? <p className="text-[#64748B]">This shared link is invalid or was removed.</p> : !c ? <p className="text-[#64748B]">Loading…</p> : (
          <div>
            <span className="inline-block px-3 py-1 rounded-full text-xs bg-[#12121C] border border-[rgba(255,255,255,0.1)] text-[#A855F7] mb-4 capitalize">{c.kind}</span>
            <h1 className="font-display text-2xl md:text-3xl font-bold mb-6">{c.title || c.prompt}</h1>
            {c.kind === "image" && media && <img src={media} alt="" className="rounded-2xl w-full mb-6" />}
            {c.kind === "video" && media && <video src={media} controls className="rounded-2xl w-full mb-6" />}
            {(c.kind === "audio" || c.kind === "music") && media && <audio src={media} controls className="w-full mb-6" />}
            {media && ["image", "video", "audio", "music"].includes(c.kind) && (
              <a href={media} download={dlName} data-testid="share-download-btn"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full ai-gradient-bg text-white text-sm font-medium hover:opacity-90 transition-opacity mb-6">
                <Download className="w-4 h-4" /> Download to your device
              </a>
            )}
            {c.content && <pre className="text-sm text-[#F8FAFC] whitespace-pre-wrap leading-relaxed font-mono p-6 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">{c.content}</pre>}
          </div>
        )}
      </main>
    </div>
  );
}
