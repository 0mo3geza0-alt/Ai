import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { FileText, Code2, Image as ImageIcon, AudioLines, Sparkles, Copy, Check, Download } from "lucide-react";
import { api, formatApiErrorDetail } from "@/context/AuthContext";
import { Dots } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const VOICES = ["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"];
const DOC_MODES = [{ v: "report", l: "Report" }, { v: "presentation", l: "Presentation" }, { v: "article", l: "Article" }];
const LANGS = ["python", "javascript", "typescript", "go", "rust", "java"];

function ResultBox({ text }) {
  const [copied, setCopied] = useState(false);
  if (!text) return null;
  const copy = () => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); };
  return (
    <div className="mt-5 p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
      <div className="flex justify-end mb-2"><button onClick={copy} data-testid="copy-result-btn" className="flex items-center gap-1.5 text-xs text-[#94A3B8] hover:text-white transition-colors">{copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />} {copied ? "Copied" : "Copy"}</button></div>
      <pre data-testid="text-result" className="text-sm text-[#F8FAFC] whitespace-pre-wrap leading-relaxed font-mono">{text}</pre>
    </div>
  );
}

export default function Create() {
  const { activeOrg, refreshUsage } = useOutletContext();
  const oid = activeOrg.id;

  const [docPrompt, setDocPrompt] = useState(""); const [docMode, setDocMode] = useState("report"); const [docOut, setDocOut] = useState(""); const [docLoad, setDocLoad] = useState(false);
  const [codePrompt, setCodePrompt] = useState(""); const [lang, setLang] = useState("python"); const [codeOut, setCodeOut] = useState(""); const [codeLoad, setCodeLoad] = useState(false);
  const [imgPrompt, setImgPrompt] = useState(""); const [imgs, setImgs] = useState([]); const [imgLoad, setImgLoad] = useState(false);
  const [audText, setAudText] = useState(""); const [voice, setVoice] = useState("nova"); const [audUrl, setAudUrl] = useState(null); const [audLoad, setAudLoad] = useState(false);

  const err = (e) => toast.error(e.response?.status === 402 ? "Out of credits — upgrade the org plan." : formatApiErrorDetail(e.response?.data?.detail));

  const genDoc = async () => { if (!docPrompt.trim()) return; setDocLoad(true); setDocOut(""); try { const { data } = await api.post(`/orgs/${oid}/generate/document`, { prompt: docPrompt, mode: docMode }); setDocOut(data.content); refreshUsage(); } catch (e) { err(e); } finally { setDocLoad(false); } };
  const genCode = async () => { if (!codePrompt.trim()) return; setCodeLoad(true); setCodeOut(""); try { const { data } = await api.post(`/orgs/${oid}/generate/code`, { prompt: codePrompt, language: lang }); setCodeOut(data.content); refreshUsage(); } catch (e) { err(e); } finally { setCodeLoad(false); } };
  const genImg = async () => { if (!imgPrompt.trim()) return; setImgLoad(true); setImgs([]); try { const { data } = await api.post(`/orgs/${oid}/generate/image`, { prompt: imgPrompt, variations: 1 }); setImgs(data.images); refreshUsage(); } catch (e) { err(e); } finally { setImgLoad(false); } };
  const genAud = async () => { if (!audText.trim()) return; setAudLoad(true); setAudUrl(null); try { const { data } = await api.post(`/orgs/${oid}/generate/audio`, { text: audText, voice }); const res = await api.get(data.url.replace("/api", ""), { responseType: "blob" }); setAudUrl(URL.createObjectURL(res.data)); refreshUsage(); } catch (e) { err(e); } finally { setAudLoad(false); } };

  const [blobUrls, setBlobUrls] = useState({});
  const loadImg = async (im) => {
    if (blobUrls[im.id]) return;
    try { const res = await api.get(im.url.replace("/api", ""), { responseType: "blob" }); setBlobUrls((b) => ({ ...b, [im.id]: URL.createObjectURL(res.data) })); } catch { /* ignore */ }
  };

  const inputCls = "resize-none bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors rounded-xl";
  const btnCls = "rounded-full h-11 px-8 ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity";

  return (
    <div className="px-5 lg:px-8 py-8 max-w-4xl">
      <h1 className="font-display text-2xl md:text-3xl font-bold mb-1">Create Studio</h1>
      <p className="text-[#94A3B8] mb-8">Generate documents, code, images and voiceovers from natural language.</p>

      <Tabs defaultValue="document">
        <TabsList className="bg-[#0C0C14] border border-[rgba(255,255,255,0.08)] mb-6">
          <TabsTrigger value="document" data-testid="tab-document" className="data-[state=active]:bg-white/10"><FileText className="w-4 h-4 me-2" /> Document</TabsTrigger>
          <TabsTrigger value="code" data-testid="tab-code" className="data-[state=active]:bg-white/10"><Code2 className="w-4 h-4 me-2" /> Code</TabsTrigger>
          <TabsTrigger value="image" data-testid="tab-image" className="data-[state=active]:bg-white/10"><ImageIcon className="w-4 h-4 me-2" /> Image</TabsTrigger>
          <TabsTrigger value="audio" data-testid="tab-audio" className="data-[state=active]:bg-white/10"><AudioLines className="w-4 h-4 me-2" /> Audio</TabsTrigger>
        </TabsList>

        <TabsContent value="document">
          <div className="flex gap-2 mb-4">
            {DOC_MODES.map((m) => <button key={m.v} data-testid={`doc-mode-${m.v}`} onClick={() => setDocMode(m.v)} className={`px-4 py-2 rounded-full text-sm border transition-colors ${docMode === m.v ? "ai-gradient-bg text-white border-transparent" : "bg-transparent text-[#94A3B8] border-[rgba(255,255,255,0.12)] hover:text-white"}`}>{m.l}</button>)}
          </div>
          <Textarea data-testid="doc-prompt-input" value={docPrompt} onChange={(e) => setDocPrompt(e.target.value)} rows={5} placeholder="Describe the document you need..." className={inputCls} />
          <Button data-testid="doc-generate-btn" onClick={genDoc} disabled={docLoad || !docPrompt.trim()} className={`${btnCls} mt-4`}>{docLoad ? <Dots /> : <><Sparkles className="w-4 h-4 me-2" /> Generate</>}</Button>
          {docLoad ? <div className="mt-5 flex justify-center"><Dots /></div> : <ResultBox text={docOut} />}
        </TabsContent>

        <TabsContent value="code">
          <div className="flex gap-3 mb-4">
            <Select value={lang} onValueChange={setLang}><SelectTrigger data-testid="code-lang-select" className="w-40 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#12121C] border-[rgba(255,255,255,0.12)] text-white">{LANGS.map((l) => <SelectItem key={l} value={l} className="capitalize focus:bg-white/5">{l}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <Textarea data-testid="code-prompt-input" value={codePrompt} onChange={(e) => setCodePrompt(e.target.value)} rows={5} placeholder="Describe the function or program..." className={inputCls} />
          <Button data-testid="code-generate-btn" onClick={genCode} disabled={codeLoad || !codePrompt.trim()} className={`${btnCls} mt-4`}>{codeLoad ? <Dots /> : <><Code2 className="w-4 h-4 me-2" /> Generate</>}</Button>
          {codeLoad ? <div className="mt-5 flex justify-center"><Dots /></div> : <ResultBox text={codeOut} />}
        </TabsContent>

        <TabsContent value="image">
          <Textarea data-testid="image-prompt-input" value={imgPrompt} onChange={(e) => setImgPrompt(e.target.value)} rows={4} placeholder="A cinematic product shot of..." className={inputCls} />
          <Button data-testid="image-generate-btn" onClick={genImg} disabled={imgLoad || !imgPrompt.trim()} className={`${btnCls} mt-4`}>{imgLoad ? <Dots /> : <><Sparkles className="w-4 h-4 me-2" /> Generate image</>}</Button>
          {imgLoad ? <div className="mt-6 flex justify-center"><Dots /></div> : (
            <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
              {imgs.map((im) => { loadImg(im); return (
                <motion.div key={im.id} initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} className="rounded-2xl overflow-hidden bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
                  {blobUrls[im.id] ? <img data-testid="generated-image" src={blobUrls[im.id]} alt="" className="w-full h-auto" /> : <div className="aspect-square flex items-center justify-center"><Dots /></div>}
                </motion.div>
              ); })}
            </div>
          )}
        </TabsContent>

        <TabsContent value="audio">
          <Textarea data-testid="audio-text-input" value={audText} onChange={(e) => setAudText(e.target.value)} rows={4} placeholder="Type the script for the voiceover..." className={inputCls} />
          <div className="flex items-center gap-3 mt-4">
            <Select value={voice} onValueChange={setVoice}><SelectTrigger data-testid="audio-voice-select" className="w-40 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#12121C] border-[rgba(255,255,255,0.12)] text-white">{VOICES.map((v) => <SelectItem key={v} value={v} className="capitalize focus:bg-white/5">{v}</SelectItem>)}</SelectContent>
            </Select>
            <Button data-testid="audio-generate-btn" onClick={genAud} disabled={audLoad || !audText.trim()} className={btnCls}>{audLoad ? <Dots /> : <><AudioLines className="w-4 h-4 me-2" /> Generate voice</>}</Button>
          </div>
          {audUrl && (
            <div className="mt-6 p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
              <audio data-testid="generated-audio" src={audUrl} controls className="w-full" />
              <a href={audUrl} download="voiceover.mp3" className="inline-flex items-center gap-2 mt-3 text-sm text-[#A855F7] hover:underline"><Download className="w-4 h-4" /> Download mp3</a>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
