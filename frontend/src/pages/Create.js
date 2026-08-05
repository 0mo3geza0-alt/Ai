import { useState, useEffect } from "react";
import { useOutletContext } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { FileText, Code2, Image as ImageIcon, AudioLines, Video, Music, Search, Sparkles, Copy, Check, Download, Wand2 } from "lucide-react";
import { api, formatApiErrorDetail } from "@/context/AuthContext";
import { Dots } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const VOICES = ["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"];
const DOC_MODES = [{ v: "report", l: "Report" }, { v: "presentation", l: "Presentation" }, { v: "article", l: "Article" }];
const LANGS = ["python", "javascript", "typescript", "go", "rust", "java"];
const MODIFIERS = [{ v: "none", l: "None" }, { v: "photorealistic", l: "Photorealistic" }, { v: "no-background", l: "No background" }, { v: "upscale", l: "Upscale/HD" }, { v: "anime", l: "Anime" }, { v: "3d", l: "3D render" }];

const TEMPLATES = {
  document: ["Business plan for a coffee shop", "Marketing strategy for a mobile app", "Weekly team status report"],
  code: ["REST API for a todo app", "Function to debounce events", "SQL to find top customers"],
  image: ["A cinematic product shot of a perfume bottle", "Minimal SaaS dashboard hero illustration", "Cyberpunk city at night, neon"],
  audio: ["Welcome to our platform, where ideas come to life.", "Thanks for listening — subscribe for more."],
  video: ["A drone shot flying over a misty forest at sunrise", "A sleek smartphone rotating on a studio pedestal"],
  music: ["Calm lofi hip hop beat for studying", "Epic cinematic orchestral trailer"],
  research: ["Compare React vs Vue in 2026", "What are the health benefits of green tea"],
};

function Chips({ items, onPick }) {
  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {items.map((t, i) => (
        <button key={i} data-testid={`template-chip-${i}`} onClick={() => onPick(t)}
          className="px-3 py-1.5 rounded-full text-xs bg-[#12121C] border border-[rgba(255,255,255,0.1)] text-[#94A3B8] hover:text-white hover:border-[rgba(255,255,255,0.25)] transition-colors">
          <Wand2 className="w-3 h-3 me-1 inline" />{t.length > 40 ? t.slice(0, 40) + "…" : t}
        </button>
      ))}
    </div>
  );
}

function ResultBox({ text, sources }) {
  const [copied, setCopied] = useState(false);
  if (!text) return null;
  const copy = () => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); };
  return (
    <div className="mt-5 p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
      <div className="flex justify-end mb-2"><button onClick={copy} data-testid="copy-result-btn" className="flex items-center gap-1.5 text-xs text-[#94A3B8] hover:text-white transition-colors">{copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />} {copied ? "Copied" : "Copy"}</button></div>
      <pre data-testid="text-result" className="text-sm text-[#F8FAFC] whitespace-pre-wrap leading-relaxed font-mono">{text}</pre>
      {sources?.length > 0 && (
        <div className="mt-4 pt-4 border-t border-[rgba(255,255,255,0.06)]">
          <p className="text-xs text-[#64748B] mb-2">Sources</p>
          {sources.map((s, i) => <a key={i} href={s.url} target="_blank" rel="noreferrer" className="block text-xs text-[#A855F7] hover:underline truncate">[{i + 1}] {s.title}</a>)}
        </div>
      )}
    </div>
  );
}

export default function Create() {
  const { activeOrg, refreshUsage } = useOutletContext();
  const oid = activeOrg.id;
  const err = (e) => toast.error(e.response?.status === 402 ? "Out of credits — upgrade the org plan." : formatApiErrorDetail(e.response?.data?.detail));

  const [docPrompt, setDocPrompt] = useState(""); const [docMode, setDocMode] = useState("report"); const [docOut, setDocOut] = useState(""); const [docLoad, setDocLoad] = useState(false);
  const [codePrompt, setCodePrompt] = useState(""); const [lang, setLang] = useState("python"); const [codeOut, setCodeOut] = useState(""); const [codeLoad, setCodeLoad] = useState(false);
  const [imgPrompt, setImgPrompt] = useState(""); const [modifier, setModifier] = useState("none"); const [imgs, setImgs] = useState([]); const [imgLoad, setImgLoad] = useState(false); const [blobUrls, setBlobUrls] = useState({});
  const [audText, setAudText] = useState(""); const [voice, setVoice] = useState("nova"); const [audUrl, setAudUrl] = useState(null); const [audLoad, setAudLoad] = useState(false);
  const [vidPrompt, setVidPrompt] = useState(""); const [vidUrl, setVidUrl] = useState(null); const [vidLoad, setVidLoad] = useState(false);
  const [musPrompt, setMusPrompt] = useState(""); const [musUrl, setMusUrl] = useState(null); const [musLoad, setMusLoad] = useState(false);
  const [resQuery, setResQuery] = useState(""); const [resOut, setResOut] = useState(""); const [resSources, setResSources] = useState([]); const [resLoad, setResLoad] = useState(false);

  const blobOf = async (url) => { const res = await api.get(url.replace("/api", ""), { responseType: "blob" }); return URL.createObjectURL(res.data); };

  const pollJob = async (id, onDone, onFail) => {
    for (let i = 0; i < 90; i++) {
      await new Promise((r) => setTimeout(r, 4000));
      try {
        const { data } = await api.get(`/orgs/${oid}/creations/${id}/status`);
        if (data.status === "done") { onDone(data); return; }
        if (data.status === "failed") { onFail(data.error || "generation failed"); return; }
      } catch { /* keep polling */ }
    }
    onFail("timed out");
  };

  const genDoc = async () => { if (!docPrompt.trim()) return; setDocLoad(true); setDocOut(""); try { const { data } = await api.post(`/orgs/${oid}/generate/document`, { prompt: docPrompt, mode: docMode }); setDocOut(data.content); refreshUsage(); } catch (e) { err(e); } finally { setDocLoad(false); } };
  const genCode = async () => { if (!codePrompt.trim()) return; setCodeLoad(true); setCodeOut(""); try { const { data } = await api.post(`/orgs/${oid}/generate/code`, { prompt: codePrompt, language: lang }); setCodeOut(data.content); refreshUsage(); } catch (e) { err(e); } finally { setCodeLoad(false); } };
  const genImg = async () => { if (!imgPrompt.trim()) return; setImgLoad(true); setImgs([]); try { const { data } = await api.post(`/orgs/${oid}/generate/image`, { prompt: imgPrompt, variations: 1, modifier }); setImgs(data.images); refreshUsage(); } catch (e) { err(e); } finally { setImgLoad(false); } };
  const genAud = async () => { if (!audText.trim()) return; setAudLoad(true); setAudUrl(null); try { const { data } = await api.post(`/orgs/${oid}/generate/audio`, { text: audText, voice }); setAudUrl(await blobOf(data.url)); refreshUsage(); } catch (e) { err(e); } finally { setAudLoad(false); } };
  const genRes = async () => { if (!resQuery.trim()) return; setResLoad(true); setResOut(""); setResSources([]); try { const { data } = await api.post(`/orgs/${oid}/generate/research`, { query: resQuery }); setResOut(data.content); setResSources(data.sources || []); refreshUsage(); } catch (e) { err(e); } finally { setResLoad(false); } };
  const genVid = async () => { if (!vidPrompt.trim()) return; setVidLoad(true); setVidUrl(null); try { const { data } = await api.post(`/orgs/${oid}/generate/video`, { prompt: vidPrompt }); refreshUsage(); pollJob(data.id, async (d) => { setVidUrl(await blobOf(d.url)); setVidLoad(false); }, (e) => { toast.error("Video: " + e); setVidLoad(false); }); } catch (e) { err(e); setVidLoad(false); } };
  const genMus = async () => { if (!musPrompt.trim()) return; setMusLoad(true); setMusUrl(null); try { const { data } = await api.post(`/orgs/${oid}/generate/music`, { prompt: musPrompt, seconds: 20 }); refreshUsage(); pollJob(data.id, async (d) => { setMusUrl(await blobOf(d.url)); setMusLoad(false); }, (e) => { toast.error("Music: " + e); setMusLoad(false); }); } catch (e) { err(e); setMusLoad(false); } };

  const loadImg = async (im) => { if (blobUrls[im.id]) return; try { const u = await blobOf(im.url); setBlobUrls((b) => ({ ...b, [im.id]: u })); } catch { /* ignore */ } };

  const inputCls = "resize-none bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors rounded-xl";
  const btnCls = "rounded-full h-11 px-8 ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity";

  return (
    <div className="px-5 lg:px-8 py-8 max-w-4xl">
      <h1 className="font-display text-2xl md:text-3xl font-bold mb-1">Create Studio</h1>
      <p className="text-[#94A3B8] mb-8">Documents, code, images, voice, video, music & research — from natural language.</p>

      <Tabs defaultValue="document">
        <TabsList className="bg-[#0C0C14] border border-[rgba(255,255,255,0.08)] mb-6 flex-wrap h-auto">
          <TabsTrigger value="document" data-testid="tab-document" className="data-[state=active]:bg-white/10"><FileText className="w-4 h-4 me-2" /> Document</TabsTrigger>
          <TabsTrigger value="code" data-testid="tab-code" className="data-[state=active]:bg-white/10"><Code2 className="w-4 h-4 me-2" /> Code</TabsTrigger>
          <TabsTrigger value="image" data-testid="tab-image" className="data-[state=active]:bg-white/10"><ImageIcon className="w-4 h-4 me-2" /> Image</TabsTrigger>
          <TabsTrigger value="audio" data-testid="tab-audio" className="data-[state=active]:bg-white/10"><AudioLines className="w-4 h-4 me-2" /> Voice</TabsTrigger>
          <TabsTrigger value="video" data-testid="tab-video" className="data-[state=active]:bg-white/10"><Video className="w-4 h-4 me-2" /> Video</TabsTrigger>
          <TabsTrigger value="music" data-testid="tab-music" className="data-[state=active]:bg-white/10"><Music className="w-4 h-4 me-2" /> Music</TabsTrigger>
          <TabsTrigger value="research" data-testid="tab-research" className="data-[state=active]:bg-white/10"><Search className="w-4 h-4 me-2" /> Research</TabsTrigger>
        </TabsList>

        <TabsContent value="document">
          <div className="flex gap-2 mb-4">{DOC_MODES.map((m) => <button key={m.v} data-testid={`doc-mode-${m.v}`} onClick={() => setDocMode(m.v)} className={`px-4 py-2 rounded-full text-sm border transition-colors ${docMode === m.v ? "ai-gradient-bg text-white border-transparent" : "bg-transparent text-[#94A3B8] border-[rgba(255,255,255,0.12)] hover:text-white"}`}>{m.l}</button>)}</div>
          <Chips items={TEMPLATES.document} onPick={setDocPrompt} />
          <Textarea data-testid="doc-prompt-input" value={docPrompt} onChange={(e) => setDocPrompt(e.target.value)} rows={5} placeholder="Describe the document you need..." className={inputCls} />
          <Button data-testid="doc-generate-btn" onClick={genDoc} disabled={docLoad || !docPrompt.trim()} className={`${btnCls} mt-4`}>{docLoad ? <Dots /> : <><Sparkles className="w-4 h-4 me-2" /> Generate</>}</Button>
          {docLoad ? <div className="mt-5 flex justify-center"><Dots /></div> : <ResultBox text={docOut} />}
        </TabsContent>

        <TabsContent value="code">
          <div className="flex gap-3 mb-4"><Select value={lang} onValueChange={setLang}><SelectTrigger data-testid="code-lang-select" className="w-40 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white"><SelectValue /></SelectTrigger><SelectContent className="bg-[#12121C] border-[rgba(255,255,255,0.12)] text-white">{LANGS.map((l) => <SelectItem key={l} value={l} className="capitalize focus:bg-white/5">{l}</SelectItem>)}</SelectContent></Select></div>
          <Chips items={TEMPLATES.code} onPick={setCodePrompt} />
          <Textarea data-testid="code-prompt-input" value={codePrompt} onChange={(e) => setCodePrompt(e.target.value)} rows={5} placeholder="Describe the function or program..." className={inputCls} />
          <Button data-testid="code-generate-btn" onClick={genCode} disabled={codeLoad || !codePrompt.trim()} className={`${btnCls} mt-4`}>{codeLoad ? <Dots /> : <><Code2 className="w-4 h-4 me-2" /> Generate</>}</Button>
          {codeLoad ? <div className="mt-5 flex justify-center"><Dots /></div> : <ResultBox text={codeOut} />}
        </TabsContent>

        <TabsContent value="image">
          <div className="flex gap-3 mb-4"><Select value={modifier} onValueChange={setModifier}><SelectTrigger data-testid="image-modifier-select" className="w-44 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white"><SelectValue /></SelectTrigger><SelectContent className="bg-[#12121C] border-[rgba(255,255,255,0.12)] text-white">{MODIFIERS.map((m) => <SelectItem key={m.v} value={m.v} className="focus:bg-white/5">{m.l}</SelectItem>)}</SelectContent></Select></div>
          <Chips items={TEMPLATES.image} onPick={setImgPrompt} />
          <Textarea data-testid="image-prompt-input" value={imgPrompt} onChange={(e) => setImgPrompt(e.target.value)} rows={4} placeholder="A cinematic product shot of..." className={inputCls} />
          <Button data-testid="image-generate-btn" onClick={genImg} disabled={imgLoad || !imgPrompt.trim()} className={`${btnCls} mt-4`}>{imgLoad ? <Dots /> : <><Sparkles className="w-4 h-4 me-2" /> Generate image</>}</Button>
          {imgLoad ? <div className="mt-6 flex justify-center"><Dots /></div> : (
            <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
              {imgs.map((im) => { loadImg(im); return (<motion.div key={im.id} initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} className="rounded-2xl overflow-hidden bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">{blobUrls[im.id] ? <><img data-testid="generated-image" src={blobUrls[im.id]} alt="" className="w-full h-auto" /><div className="p-3"><a href={blobUrls[im.id]} download="nexus-image.png" data-testid="image-download-link" className="inline-flex items-center gap-2 text-sm text-[#A855F7] hover:underline"><Download className="w-4 h-4" /> Download</a></div></> : <div className="aspect-square flex items-center justify-center"><Dots /></div>}</motion.div>); })}
            </div>
          )}
        </TabsContent>

        <TabsContent value="audio">
          <Chips items={TEMPLATES.audio} onPick={setAudText} />
          <Textarea data-testid="audio-text-input" value={audText} onChange={(e) => setAudText(e.target.value)} rows={4} placeholder="Type the script for the voiceover..." className={inputCls} />
          <div className="flex items-center gap-3 mt-4"><Select value={voice} onValueChange={setVoice}><SelectTrigger data-testid="audio-voice-select" className="w-40 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white"><SelectValue /></SelectTrigger><SelectContent className="bg-[#12121C] border-[rgba(255,255,255,0.12)] text-white">{VOICES.map((v) => <SelectItem key={v} value={v} className="capitalize focus:bg-white/5">{v}</SelectItem>)}</SelectContent></Select>
            <Button data-testid="audio-generate-btn" onClick={genAud} disabled={audLoad || !audText.trim()} className={btnCls}>{audLoad ? <Dots /> : <><AudioLines className="w-4 h-4 me-2" /> Generate voice</>}</Button></div>
          {audUrl && <div className="mt-6 p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]"><audio data-testid="generated-audio" src={audUrl} controls className="w-full" /><a href={audUrl} download="voiceover.mp3" className="inline-flex items-center gap-2 mt-3 text-sm text-[#A855F7] hover:underline"><Download className="w-4 h-4" /> Download</a></div>}
        </TabsContent>

        <TabsContent value="video">
          <Chips items={TEMPLATES.video} onPick={setVidPrompt} />
          <Textarea data-testid="video-prompt-input" value={vidPrompt} onChange={(e) => setVidPrompt(e.target.value)} rows={4} placeholder="Describe the video scene..." className={inputCls} />
          <Button data-testid="video-generate-btn" onClick={genVid} disabled={vidLoad || !vidPrompt.trim()} className={`${btnCls} mt-4`}>{vidLoad ? <Dots /> : <><Video className="w-4 h-4 me-2" /> Generate video</>}</Button>
          {vidLoad && <p className="mt-4 text-sm text-[#64748B] flex items-center gap-2"><Dots /> Rendering high-quality video — this can take 1-3 minutes…</p>}
          {vidUrl && <div className="mt-6 rounded-2xl overflow-hidden bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]"><video data-testid="generated-video" src={vidUrl} controls className="w-full" /><div className="p-3"><a href={vidUrl} download="nexus-video.mp4" data-testid="video-download-link" className="inline-flex items-center gap-2 text-sm text-[#A855F7] hover:underline"><Download className="w-4 h-4" /> Download video</a></div></div>}
        </TabsContent>

        <TabsContent value="music">
          <Chips items={TEMPLATES.music} onPick={setMusPrompt} />
          <Textarea data-testid="music-prompt-input" value={musPrompt} onChange={(e) => setMusPrompt(e.target.value)} rows={4} placeholder="Describe the music / mood..." className={inputCls} />
          <Button data-testid="music-generate-btn" onClick={genMus} disabled={musLoad || !musPrompt.trim()} className={`${btnCls} mt-4`}>{musLoad ? <Dots /> : <><Music className="w-4 h-4 me-2" /> Generate music</>}</Button>
          {musLoad && <p className="mt-4 text-sm text-[#64748B] flex items-center gap-2"><Dots /> Composing — this can take 1-2 minutes…</p>}
          {musUrl && <div className="mt-6 p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]"><audio data-testid="generated-music" src={musUrl} controls className="w-full" /><a href={musUrl} download="nexus-music.wav" data-testid="music-download-link" className="inline-flex items-center gap-2 mt-3 text-sm text-[#A855F7] hover:underline"><Download className="w-4 h-4" /> Download</a></div>}
        </TabsContent>

        <TabsContent value="research">
          <Chips items={TEMPLATES.research} onPick={setResQuery} />
          <Textarea data-testid="research-input" value={resQuery} onChange={(e) => setResQuery(e.target.value)} rows={3} placeholder="Ask a research question..." className={inputCls} />
          <Button data-testid="research-generate-btn" onClick={genRes} disabled={resLoad || !resQuery.trim()} className={`${btnCls} mt-4`}>{resLoad ? <Dots /> : <><Search className="w-4 h-4 me-2" /> Research</>}</Button>
          {resLoad ? <div className="mt-5 flex justify-center"><Dots /></div> : <ResultBox text={resOut} sources={resSources} />}
        </TabsContent>
      </Tabs>
    </div>
  );
}
