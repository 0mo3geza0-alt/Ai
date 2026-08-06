import { useEffect, useRef, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { motion } from "framer-motion";
import { Plus, Send, Trash2, MessageSquare, Sparkles, Download, Copy, Check, Maximize2, Image as ImageIcon, AudioLines, Code2, Globe, Paperclip, X, RefreshCw, FileText, Mic, Loader2, PhoneOff, Volume2, Lightbulb, Zap, Lock } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { toast } from "sonner";
import { api, formatApiErrorDetail } from "@/context/AuthContext";
import { Dots } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SUGGESTIONS = [
  { icon: ImageIcon, label: "Generate an image", text: "Generate an image of a futuristic city at sunset" },
  { icon: Globe, label: "Build a web app", text: "Build a landing page for a coffee shop with a hero and menu" },
  { icon: Code2, label: "Write code", text: "Write a Python function that checks if a number is prime" },
  { icon: AudioLines, label: "Create a voiceover", text: "Create a voiceover: Welcome to VibeVerse, your all-in-one AI studio" },
];

const EXT = { image: "png", voice: "mp3", audio: "mp3" };

const VOICE_OPTS = ["nova", "alloy", "ash", "coral", "echo", "fable", "onyx", "sage", "shimmer"];

const DIALECT_OPTS = [
  { id: "egyptian", label: "🇪🇬 مصري" },
  { id: "gulf", label: "🇸🇦 خليجي" },
  { id: "levantine", label: "🇸🇾 شامي" },
  { id: "standard", label: "🕌 فصحى" },
];

// Speech-recognition locale per dialect so the mic captures spoken Arabic accurately.
const DIALECT_LANG = { egyptian: "ar-EG", gulf: "ar-SA", levantine: "ar-LB", standard: "ar-SA" };

// ---- Prompt Gallery: ready-made starter ideas grouped by category ----
const PROMPT_GALLERY = [
  { cat: "Images", icon: ImageIcon, items: [
    { title: "Futuristic city", prompt: "Generate an image of a futuristic neon city at sunset, cinematic, ultra-detailed" },
    { title: "Product mockup", prompt: "Generate a clean product photo of a minimalist ceramic coffee mug on a marble table, studio lighting" },
    { title: "Logo concept", prompt: "Generate a modern flat logo for an AI startup called Nimbus, purple gradient, simple icon" },
    { title: "Fantasy character", prompt: "Generate an image of a friendly robot wizard casting glowing spells, digital art, vibrant colors" },
  ]},
  { cat: "Web apps", icon: Globe, items: [
    { title: "Coffee shop page", prompt: "Build a beautiful landing page for a coffee shop with a hero, menu grid and contact section" },
    { title: "Portfolio site", prompt: "Build a sleek personal portfolio website with an about, projects and contact section" },
    { title: "Snake game", prompt: "Build a playable Snake game in a single HTML page with score and restart button" },
    { title: "Pricing page", prompt: "Build a modern SaaS pricing page with three plans, a monthly/yearly toggle and a FAQ" },
  ]},
  { cat: "Code", icon: Code2, items: [
    { title: "Prime checker", prompt: "Write a Python function that checks if a number is prime, with tests" },
    { title: "REST API", prompt: "Write a minimal FastAPI CRUD API for a todo list with in-memory storage" },
    { title: "Debounce util", prompt: "Write a reusable JavaScript debounce function with an example" },
    { title: "SQL query", prompt: "Write a SQL query to find the top 5 customers by total order value" },
  ]},
  { cat: "Voice", icon: AudioLines, items: [
    { title: "Welcome message", prompt: "Create a voiceover: Welcome to VibeVerse, your all-in-one AI studio. Let's create something amazing together." },
    { title: "Meditation intro", prompt: "Create a voiceover: Take a deep breath in… and slowly let it go. Let's begin today's calm session." },
    { title: "Ad script", prompt: "Create a voiceover: Introducing the future of productivity — smart, simple, and made for you." },
  ]},
  { cat: "Writing", icon: FileText, items: [
    { title: "Blog article", prompt: "Write an engaging 600-word blog article about the benefits of morning routines" },
    { title: "Cold email", prompt: "Write a friendly, concise cold outreach email offering a free trial of our AI tool" },
    { title: "Product description", prompt: "Write a persuasive product description for wireless noise-cancelling headphones" },
  ]},
];


function CopyBtn({ text }) {
  const [done, setDone] = useState(false);
  return (
    <button data-testid="copy-code-btn" onClick={() => { navigator.clipboard?.writeText(text).then(() => { setDone(true); setTimeout(() => setDone(false), 1500); }); }}
      className="inline-flex items-center gap-1 text-xs text-[#94A3B8] hover:text-white transition-colors">
      {done ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />} {done ? "Copied" : "Copy"}
    </button>
  );
}

async function downloadBlob(url, filename) {
  try {
    const res = await api.get(url.replace("/api", ""), { responseType: "blob" });
    const objurl = URL.createObjectURL(res.data);
    const a = document.createElement("a"); a.href = objurl; a.download = filename; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(objurl);
    toast.success("Downloaded to your device");
  } catch { toast.error("Download failed"); }
}

function BlobMedia({ url, render, testid, fallbackH = "h-52" }) {
  const [src, setSrc] = useState(null);
  useEffect(() => { if (url) api.get(url.replace("/api", ""), { responseType: "blob" }).then((r) => setSrc(URL.createObjectURL(r.data))).catch(() => {}); }, [url]);
  if (!src) return <div className={`${fallbackH} flex items-center justify-center`}><Dots /></div>;
  return render(src);
}

function ImageBlock({ media }) {
  return (
    <div className="mt-3 rounded-xl overflow-hidden border border-[rgba(255,255,255,0.08)] bg-[#0C0C14]">
      <BlobMedia url={media.url} render={(src) => <img data-testid="chat-image" src={src} alt="" className="w-full h-auto max-h-[420px] object-contain" />} />
      <div className="p-2"><button onClick={() => downloadBlob(media.url, "nexus-image.png")} className="inline-flex items-center gap-1.5 text-xs text-[#A855F7] hover:underline"><Download className="w-3.5 h-3.5" /> Download</button></div>
    </div>
  );
}

function VoiceBlock({ media }) {
  return (
    <div className="mt-3 p-3 rounded-xl border border-[rgba(255,255,255,0.08)] bg-[#0C0C14]">
      <BlobMedia url={media.url} fallbackH="h-10" render={(src) => <audio data-testid="chat-voice" src={src} controls className="w-full" />} />
      <button onClick={() => downloadBlob(media.url, "nexus-voice.mp3")} className="inline-flex items-center gap-1.5 mt-2 text-xs text-[#A855F7] hover:underline"><Download className="w-3.5 h-3.5" /> Download</button>
    </div>
  );
}

function CodeBlock({ m, media }) {
  return (
    <div className="mt-3 rounded-xl overflow-hidden border border-[rgba(255,255,255,0.08)] bg-[#0A0A12]">
      <div className="flex items-center justify-between px-3 py-2 border-b border-[rgba(255,255,255,0.06)] text-xs text-[#64748B]"><span>{media?.language || "code"}</span><CopyBtn text={m.content} /></div>
      <pre data-testid="chat-code" className="text-xs text-[#E2E8F0] p-4 overflow-x-auto font-mono whitespace-pre-wrap">{m.content}</pre>
    </div>
  );
}

function WebappBlock({ m, media, pollJob }) {
  const status = media?.status || "done";
  const [html, setHtml] = useState(media?.html || "");
  useEffect(() => {
    if (status === "processing" && media?.cid) pollJob(m);
    if (status === "done" && !html && media?.url) {
      api.get(media.url.replace("/api", ""), { responseType: "text" }).then((r) => setHtml(typeof r.data === "string" ? r.data : "")).catch(() => {});
    }
  }, [status]); // eslint-disable-line
  if (status === "processing") return <div className="mt-3 h-40 rounded-xl border border-[rgba(255,255,255,0.08)] bg-[#0C0C14] flex flex-col items-center justify-center gap-2 text-[#64748B] text-sm" data-testid="chat-webapp-processing"><Dots /> Building your app…</div>;
  if (status === "failed") return <div className="mt-3 p-3 rounded-xl border border-red-500/30 bg-red-500/5 text-red-400 text-sm">App build failed. Please try again.</div>;
  const openFull = () => { const w = window.open(); if (w) { w.document.open(); w.document.write(html); w.document.close(); } };
  return (
    <div className="mt-3 rounded-xl overflow-hidden border border-[rgba(255,255,255,0.08)] bg-[#0C0C14]">
      <div className="flex items-center justify-between px-3 py-2 border-b border-[rgba(255,255,255,0.06)] text-xs text-[#94A3B8]">
        <span className="flex items-center gap-1.5"><Globe className="w-3.5 h-3.5 text-[#A855F7]" /> Live preview</span>
        <div className="flex items-center gap-3">
          <button data-testid="webapp-open-btn" onClick={openFull} className="inline-flex items-center gap-1 hover:text-white transition-colors"><Maximize2 className="w-3.5 h-3.5" /> Open</button>
          {media?.url && <button onClick={() => downloadBlob(media.url, "nexus-app.html")} className="inline-flex items-center gap-1 hover:text-white transition-colors"><Download className="w-3.5 h-3.5" /> Download</button>}
        </div>
      </div>
      {html ? <iframe data-testid="chat-webapp" title="app" srcDoc={html} className="w-full h-[420px] bg-white" sandbox="allow-scripts allow-forms allow-popups allow-modals" /> : <div className="h-40 flex items-center justify-center"><Dots /></div>}
    </div>
  );
}

function MediaBlock({ m, pollJob }) {
  const media = m.media;
  if (m.kind === "image" && media?.url) return <ImageBlock media={media} />;
  if (m.kind === "voice" && media?.url) return <VoiceBlock media={media} />;
  if (m.kind === "code") return <CodeBlock m={m} media={media} />;
  if (m.kind === "webapp") return <WebappBlock m={m} media={media} pollJob={pollJob} />;
  return null;
}

export default function Chat() {
  const { activeOrg, refreshUsage, user } = useOutletContext();
  const oid = activeOrg.id;
  const [sessions, setSessions] = useState([]);
  const [active, setActive] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [attachment, setAttachment] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [pinnedDoc, setPinnedDoc] = useState(null);
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [galleryCat, setGalleryCat] = useState(0);
  const [nexusMode, setNexusMode] = useState(false);
  const canNexus = user?.global_role === "admin" || activeOrg?.plan === "pro";
  const fileRef = useRef(null);
  const endRef = useRef(null);
  // --- live voice conversation ---
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [vStatus, setVStatus] = useState("idle"); // idle | listening | thinking | speaking
  const [vTranscript, setVTranscript] = useState("");
  const [voice, setVoice] = useState("nova");
  const [dialect, setDialect] = useState("egyptian");
  const [tapToHear, setTapToHear] = useState(false);
  const [agents, setAgents] = useState([]);
  const [companion, setCompanion] = useState(null);
  const recogRef = useRef(null);
  const audioRef = useRef(null);
  const audioCtxRef = useRef(null);
  const sourceRef = useRef(null);
  const pendingAudioRef = useRef(null);
  const speakingRef = useRef(false);       // true while the agent's TTS is playing (for barge-in)
  const bargedRef = useRef(false);         // guards against double barge-in in one turn
  const voiceOpenRef = useRef(false);
  const activeRef = useRef(null);
  const voiceRef = useRef("nova");
  const dialectRef = useRef("egyptian");
  const companionRef = useRef(null);
  useEffect(() => { activeRef.current = active; }, [active]);
  useEffect(() => { voiceRef.current = voice; }, [voice]);
  useEffect(() => { dialectRef.current = dialect; }, [dialect]);
  useEffect(() => { companionRef.current = companion; }, [companion]);

  // Load selectable voice companions + apply the user's saved preference as default.
  useEffect(() => {
    api.get("/voice-agents").then(({ data }) => {
      const list = data.agents || [];
      setAgents(list);
      const prefAgent = user?.preferences?.voice_agent;
      const chosen = list.find((a) => a.id === prefAgent) || list[0] || null;
      if (chosen) { setCompanion(chosen); setVoice(user?.preferences?.voice || chosen.voice); }
      if (user?.preferences?.dialect) setDialect(user.preferences.dialect);
    }).catch(() => { /* voice mode still works with defaults */ });
  }, []); // eslint-disable-line

  const loadSessions = async () => { const { data } = await api.get(`/orgs/${oid}/chat/sessions`); setSessions(data); return data; };
  useEffect(() => { setActive(null); setMessages([]); loadSessions(); }, [oid]); // eslint-disable-line
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, sending]);

  const openSession = async (id) => {
    setActive(id);
    const { data } = await api.get(`/orgs/${oid}/chat/sessions/${id}/messages`);
    setMessages(data);
    const ss = await loadSessions();
    setPinnedDoc(ss.find((s) => s.id === id)?.pinned_doc || null);
  };
  const newChat = async () => { setActive(null); setMessages([]); setAttachment(null); setPinnedDoc(null); };
  const delSession = async (id, e) => { e.stopPropagation(); await api.delete(`/orgs/${oid}/chat/sessions/${id}`); if (active === id) { setActive(null); setMessages([]); setPinnedDoc(null); } loadSessions(); };

  const pickFile = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    setUploading(true);
    try {
      const fd = new FormData(); fd.append("file", f);
      const { data } = await api.post(`/orgs/${oid}/uploads`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      if (data.kind === "image") {
        setAttachment(data);
      } else {
        // Documents get pinned to the session so the user can ask follow-up questions about them.
        let sid = active;
        if (!sid) { const { data: s } = await api.post(`/orgs/${oid}/chat/sessions`, {}); sid = s.id; setActive(sid); }
        await api.post(`/orgs/${oid}/chat/sessions/${sid}/document`, { path: data.path, mime: data.mime, kind: "file", name: data.name, url: data.url });
        setPinnedDoc({ name: data.name, mime: data.mime, url: data.url, path: data.path });
        toast.success("Document ready — ask anything about it");
        loadSessions();
      }
    } catch (err) { toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Upload failed"); }
    finally { setUploading(false); }
  };

  const removePinnedDoc = async () => {
    if (!active) { setPinnedDoc(null); return; }
    try { await api.delete(`/orgs/${oid}/chat/sessions/${active}/document`); } catch { /* noop */ }
    setPinnedDoc(null);
    loadSessions();
  };

  const pollJob = async (msg) => {
    const cid = msg.media?.cid;
    if (!cid) return;
    for (let i = 0; i < 90; i++) {
      await new Promise((r) => setTimeout(r, 4000));
      try {
        const { data } = await api.get(`/orgs/${oid}/creations/${cid}/status`);
        if (data.status === "done" || data.status === "failed") {
          setMessages((all) => all.map((m) => (m.media?.cid === cid ? { ...m, media: { ...m.media, status: data.status, url: data.url || m.media.url } } : m)));
          return;
        }
      } catch { /* keep polling */ }
    }
  };

  const send = async (preset, attachArg) => {
    const text = (preset ?? input).trim();
    const useAttach = attachArg !== undefined ? attachArg : attachment;
    if ((!text && !useAttach) || sending) return;
    let sid = active;
    if (!sid) { const { data } = await api.post(`/orgs/${oid}/chat/sessions`, {}); sid = data.id; setActive(sid); loadSessions(); }
    setInput(""); setAttachment(null);
    setMessages((m) => [...m, { role: "user", content: text, kind: "text", attachment: useAttach || null, media: useAttach ? { type: useAttach.kind, url: useAttach.url, name: useAttach.name } : null }]);
    setMessages((m) => [...m, { role: "assistant", content: "", kind: "text", media: null, _streaming: true }]);
    setSending(true);
    const patchLast = (fn) => setMessages((m) => { const c = [...m]; c[c.length - 1] = fn(c[c.length - 1]); return c; });
    try {
      if (nexusMode) {
        patchLast((l) => ({ ...l, content: "🔥 Nexus Pro يستشير Claude + GPT + Gemini للوصول لأفضل إجابة…", _nexus: true }));
        try {
          const { data } = await api.post(`/orgs/${oid}/chat/sessions/${sid}/nexus-pro`, { message: text });
          patchLast(() => ({ role: "assistant", content: data.reply, kind: "nexus", media: null }));
        } catch (err) {
          const msg = formatApiErrorDetail(err.response?.data?.detail) || "Nexus Pro error";
          patchLast((l) => ({ ...l, _streaming: false, content: msg }));
          toast.error(msg);
          if (err.response?.status === 403) setNexusMode(false);
        }
        return;
      }
      const token = localStorage.getItem("token");
      const resp = await fetch(`${API}/orgs/${oid}/chat/sessions/${sid}/agent/stream`, {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message: text, attachment: useAttach || null }),
      });
      if (!resp.ok || !resp.body) { throw new Error(resp.status === 402 ? "Out of credits — upgrade your plan." : "Request failed"); }
      const reader = resp.body.getReader(); const dec = new TextDecoder(); let buf = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf("\n\n")) !== -1) {
          const chunk = buf.slice(0, idx); buf = buf.slice(idx + 2);
          if (!chunk.startsWith("data: ")) continue;
          const ev = JSON.parse(chunk.slice(6));
          if (ev.type === "delta") patchLast((l) => ({ ...l, content: (l.content || "") + ev.content }));
          else if (ev.type === "error") { patchLast((l) => ({ ...l, _streaming: false, content: ev.detail || "Something went wrong." })); toast.error(ev.detail || "Something went wrong."); }
          else if (ev.type === "done") {
            const mm = ev.message;
            patchLast(() => ({ role: "assistant", content: mm.content, kind: mm.kind, media: mm.media }));
            if (mm.kind === "webapp" && mm.media?.status === "processing") pollJob({ media: mm.media });
          }
        }
      }
    } catch (e) {
      toast.error(e.message || "Something went wrong.");
      setMessages((m) => m.filter((x) => !x._streaming));
    } finally { setSending(false); refreshUsage(); loadSessions(); }
  };

  const regenerate = (i) => {
    for (let j = i - 1; j >= 0; j--) { if (messages[j].role === "user") { send(messages[j].content); return; } }
  };

  // ---------------- Live voice conversation ----------------
  // A tiny silent clip used to "unlock" the HTMLAudio fallback inside the user's click gesture.
  const SILENT_WAV = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=";

  const getAudioEl = () => {
    if (!audioRef.current) { audioRef.current = new Audio(); audioRef.current.preload = "auto"; audioRef.current.playsInline = true; }
    return audioRef.current;
  };

  // Web Audio API is the most reliable way to play audio that arrives seconds after the
  // last user gesture (immune to the <audio> autoplay re-lock on Chrome/Safari/iOS).
  const getAudioCtx = () => {
    if (!audioCtxRef.current) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (AC) audioCtxRef.current = new AC();
    }
    if (typeof window !== "undefined") window.__vibeAudioCtx = audioCtxRef.current || null;
    return audioCtxRef.current;
  };

  const b64ToArrayBuffer = (b64) => {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return bytes.buffer;
  };

  const decodeAudio = (ctx, arr) => new Promise((resolve, reject) => {
    try {
      const p = ctx.decodeAudioData(arr, resolve, reject); // callback form (older Safari)
      if (p && p.then) p.then(resolve).catch(reject);       // promise form (modern)
    } catch (e) { reject(e); }
  });

  // Unlock BOTH the AudioContext and the HTMLAudio fallback element within a user gesture.
  const unlockAudio = () => {
    const ctx = getAudioCtx();
    if (ctx && ctx.state === "suspended") { ctx.resume().catch(() => {}); }
    const el = getAudioEl();
    try {
      el.src = SILENT_WAV; el.muted = true;
      const p = el.play();
      if (p?.catch) p.catch(() => {});
      setTimeout(() => { try { el.pause(); el.muted = false; } catch { /* noop */ } }, 30);
    } catch { /* noop */ }
  };

  const stopAudio = () => {
    try { sourceRef.current?.stop(); } catch { /* noop */ }
    sourceRef.current = null;
    try { audioRef.current?.pause(); } catch { /* noop */ }
  };

  const stopVoiceMode = () => {
    voiceOpenRef.current = false;
    speakingRef.current = false;
    bargedRef.current = false;
    setVoiceOpen(false);
    setVStatus("idle");
    setVTranscript("");
    setTapToHear(false);
    try { recogRef.current?.abort?.(); } catch { /* noop */ }
    recogRef.current = null;
    stopAudio();
  };

  const listen = () => {
    if (!voiceOpenRef.current) return;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    if (recogRef.current) return; // only one recognition instance at a time
    const rec = new SR();
    rec.lang = DIALECT_LANG[dialectRef.current] || navigator.language || "en-US";
    rec.interimResults = true;
    rec.continuous = false;
    recogRef.current = rec;
    setTapToHear(false);
    const monitoring = speakingRef.current; // started while the agent is still speaking (barge-in watch)
    if (!monitoring) { setVTranscript(""); setVStatus("listening"); }
    let finalText = "";
    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalText += t; else interim += t;
      }
      const heard = (finalText || interim).trim();
      // BARGE-IN: the user started talking while the agent is speaking -> cut the agent off instantly.
      if (speakingRef.current && !bargedRef.current && heard.length >= 3) {
        bargedRef.current = true;
        speakingRef.current = false;
        stopAudio();
        setVStatus("listening");
      }
      setVTranscript(heard);
    };
    rec.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        toast.error("Microphone permission is required for voice mode");
        stopVoiceMode();
      }
    };
    rec.onend = () => {
      recogRef.current = null;
      const said = finalText.trim();
      if (!voiceOpenRef.current) return;
      if (said) { handleVoiceTurn(said); return; }
      // Nothing captured — keep the mic hot (a real call never stops listening).
      setTimeout(() => { if (voiceOpenRef.current && !recogRef.current) listen(); }, 250);
    };
    try { rec.start(); } catch { /* already started */ }
  };

  const vStatusIsListening = () => recogRef.current !== null;

  // Play a reply. Primary path: Web Audio API (decode + buffer source) which plays reliably
  // even seconds after the last gesture. Fallback: HTMLAudio via Blob URL. Final fallback:
  // a visible "tap to hear" button so the voice reply is never lost.
  const onSpokenEnd = () => {
    speakingRef.current = false;
    setTapToHear(false);
    if (!voiceOpenRef.current) { setVStatus("idle"); return; }
    // The mic is already monitoring (started when speech began). Just flip the status to listening.
    setVStatus("listening");
    if (!recogRef.current) listen();
  };

  const speakHtmlAudio = (b64, mime) => {
    const el = getAudioEl();
    el.muted = false;
    let url;
    try {
      const bytes = new Uint8Array(b64ToArrayBuffer(b64));
      url = URL.createObjectURL(new Blob([bytes], { type: mime || "audio/mpeg" }));
    } catch { setTapToHear(true); return; }
    el.onended = () => { try { URL.revokeObjectURL(url); } catch { /* noop */ } onSpokenEnd(); };
    el.onerror = () => { try { URL.revokeObjectURL(url); } catch { /* noop */ } setTapToHear(true); };
    el.src = url;
    try { el.load(); } catch { /* noop */ }
    const p = el.play();
    if (p?.catch) p.catch(() => { setTapToHear(true); });
  };

  const speak = async (b64, mime) => {
    pendingAudioRef.current = { b64, mime };
    speakingRef.current = true;
    bargedRef.current = false;
    setVStatus("speaking");
    setTapToHear(false);
    // Start the mic RIGHT AWAY so the user can interrupt (barge-in) mid-sentence like a real call.
    setTimeout(() => { if (voiceOpenRef.current && speakingRef.current && !recogRef.current) listen(); }, 150);
    const ctx = getAudioCtx();
    if (ctx) {
      try {
        if (ctx.state === "suspended") { await ctx.resume(); }
        const buf = await decodeAudio(ctx, b64ToArrayBuffer(b64));
        try { sourceRef.current?.stop(); } catch { /* noop */ }
        const src = ctx.createBufferSource();
        src.buffer = buf;
        src.connect(ctx.destination);
        src.onended = () => { if (sourceRef.current === src) { sourceRef.current = null; onSpokenEnd(); } };
        sourceRef.current = src;
        src.start(0);
        return;
      } catch { /* fall through to HTMLAudio */ }
    }
    speakHtmlAudio(b64, mime);
  };

  const playPending = () => {
    const pa = pendingAudioRef.current;
    setTapToHear(false);
    if (pa) speak(pa.b64, pa.mime);
    else if (voiceOpenRef.current) listen();
  };

  const handleVoiceTurn = async (said) => {
    speakingRef.current = false;
    bargedRef.current = false;
    try { recogRef.current?.abort?.(); } catch { /* noop */ }
    recogRef.current = null;
    setVStatus("thinking");
    setVTranscript(said);
    let sid = activeRef.current;
    if (!sid) { const { data } = await api.post(`/orgs/${oid}/chat/sessions`, {}); sid = data.id; setActive(sid); loadSessions(); }
    setMessages((m) => [...m, { role: "user", content: said, kind: "text", media: null }]);
    setMessages((m) => [...m, { role: "assistant", content: "", kind: "text", media: null, _streaming: true }]);
    const patchLast = (fn) => setMessages((m) => { const c = [...m]; c[c.length - 1] = fn(c[c.length - 1]); return c; });
    try {
      const comp = companionRef.current;
      const { data } = await api.post(`/orgs/${oid}/chat/sessions/${sid}/voice-chat`, {
        message: said, voice: voiceRef.current, agent: comp?.id || null, adult_ok: !!comp?.adult,
        dialect: dialectRef.current,
      });
      patchLast(() => ({ role: "assistant", content: data.reply, kind: "text", media: null }));
      refreshUsage?.();
      loadSessions();
      if (data.audio && voiceOpenRef.current) {
        stopAudio();
        speak(data.audio, data.mime);
      } else if (voiceOpenRef.current) {
        if (!data.audio) toast.error("Voice was unavailable for that reply — showing text.");
        listen();
      }
    } catch (e) {
      patchLast(() => ({ role: "assistant", content: "Sorry, something went wrong.", kind: "text", media: null }));
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Voice chat failed");
      if (voiceOpenRef.current) setTimeout(() => listen(), 800);
    }
  };

  // Tap the orb to interrupt the assistant while it's speaking and start listening immediately (like a call).
  const interrupt = () => {
    if (tapToHear) { playPending(); return; }
    if (vStatus === "speaking") {
      speakingRef.current = false;
      bargedRef.current = true;
      stopAudio();
      setTapToHear(false);
      setVStatus("listening");
      if (!recogRef.current) listen();
    } else if (vStatus === "idle") { listen(); }
  };

  const startVoiceMode = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { toast.error("Voice mode works best on Chrome or Edge browsers."); return; }
    unlockAudio();
    voiceOpenRef.current = true;
    setVoiceOpen(true);
    setVStatus("idle");
    setTapToHear(false);
    setTimeout(() => listen(), 350);
  };

  useEffect(() => () => stopVoiceMode(), []); // eslint-disable-line

  return (
    <div className="flex h-[calc(100vh-56px)] lg:h-screen">
      <aside className="hidden md:flex w-64 shrink-0 flex-col border-e border-[rgba(255,255,255,0.06)] bg-[#0C0C14]">
        <div className="p-4"><Button data-testid="new-chat-btn" onClick={newChat} className="w-full rounded-xl ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity"><Plus className="w-4 h-4 me-2" /> New chat</Button></div>
        <div className="flex-1 overflow-y-auto px-2 space-y-1">
          {sessions.length === 0 && <p className="text-center text-sm text-[#64748B] mt-6">No chats yet</p>}
          {sessions.map((s) => (
            <div key={s.id} onClick={() => openSession(s.id)} data-testid={`chat-session-${s.id}`}
              className={`group flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm cursor-pointer transition-colors ${active === s.id ? "bg-white/5 text-white" : "text-[#94A3B8] hover:bg-white/5"}`}>
              <MessageSquare className="w-4 h-4 shrink-0" /><span className="truncate flex-1">{s.title}</span>
              <button onClick={(e) => delSession(s.id, e)} className="opacity-0 group-hover:opacity-100 text-[#64748B] hover:text-red-400 transition-opacity"><Trash2 className="w-4 h-4" /></button>
            </div>
          ))}
        </div>
      </aside>
      <div className="flex-1 min-w-0 flex flex-col">
        {pinnedDoc && (
          <div data-testid="pinned-doc-banner" className="flex items-center gap-2 px-5 lg:px-8 py-2.5 border-b border-[rgba(255,255,255,0.06)] bg-[#A855F7]/10">
            <FileText className="w-4 h-4 text-[#A855F7] shrink-0" />
            <span className="text-sm text-[#E2E8F0] truncate">Chatting with <span className="font-medium">{pinnedDoc.name}</span></span>
            <span className="text-xs text-[#64748B] hidden sm:inline">— ask anything about this document</span>
            <button data-testid="pinned-doc-remove" onClick={removePinnedDoc} className="ms-auto text-[#64748B] hover:text-red-400 shrink-0" title="Stop using this document"><X className="w-4 h-4" /></button>
          </div>
        )}
        <div className="flex-1 overflow-y-auto px-5 lg:px-8 py-6">
          {messages.length === 0 && !sending ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <span className="w-14 h-14 rounded-2xl ai-gradient-bg flex items-center justify-center mb-5 glow-border"><Sparkles className="w-6 h-6 text-white" /></span>
              <h2 className="font-display text-xl font-semibold mb-2">What do you want to create?</h2>
              <p className="text-[#64748B] max-w-md mb-6">Ask anything — images, voiceovers, code, documents or full web apps. VibeVerse figures out what to build and returns it right here.</p>
              <div className="flex flex-wrap gap-2 justify-center max-w-2xl">
                {SUGGESTIONS.map((s, i) => (
                  <button key={i} data-testid={`chat-suggestion-${i}`} onClick={() => send(s.text)}
                    className="inline-flex items-center gap-2 px-3.5 py-2 rounded-full text-sm bg-[#12121C] border border-[rgba(255,255,255,0.1)] text-[#94A3B8] hover:text-white hover:border-[#A855F7] transition-colors">
                    <s.icon className="w-4 h-4 text-[#A855F7]" /> {s.label}
                  </button>
                ))}
              </div>
              <button data-testid="open-gallery-btn" onClick={() => setGalleryOpen(true)}
                className="mt-5 inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm ai-gradient-bg text-white hover:opacity-90 transition-opacity">
                <Lightbulb className="w-4 h-4" /> Browse the idea gallery
              </button>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-5">
              {messages.map((m, i) => (
                <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div data-testid={`chat-msg-${m.role}`} className={`max-w-[88%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${m.role === "user" ? "ai-gradient-bg text-white" : "bg-[#12121C] border border-[rgba(255,255,255,0.08)] text-[#F8FAFC]"}`}>
                    {m.role === "user" && m.media?.url && (m.media.type === "image"
                      ? <div className="mb-2"><BlobMedia url={m.media.url} fallbackH="h-24" render={(src) => <img data-testid="user-attachment-image" src={src} alt="" className="rounded-lg max-h-48 w-auto" />} /></div>
                      : <div className="mb-2 flex items-center gap-2 text-xs bg-black/20 rounded-lg px-2.5 py-1.5"><FileText className="w-3.5 h-3.5" /> {m.media.name || "file"}</div>)}
                    {m._streaming && !m.content ? <Dots /> : (m.kind === "code" || m.kind === "webapp" ? (m.content && <p className="whitespace-pre-wrap">{m.content}</p>) : (
                      <div className="prose-chat"><ReactMarkdown>{m.content || ""}</ReactMarkdown></div>
                    ))}
                    {m.role === "assistant" && <MediaBlock m={m} pollJob={pollJob} />}
                    {m.role === "assistant" && !m._streaming && m.media?.status !== "processing" && (
                      <button data-testid={`regenerate-${i}`} onClick={() => regenerate(i)} disabled={sending}
                        className="mt-2.5 inline-flex items-center gap-1 text-xs text-[#64748B] hover:text-[#A855F7] transition-colors">
                        <RefreshCw className="w-3.5 h-3.5" /> Regenerate
                      </button>
                    )}
                  </div>
                </motion.div>
              ))}
              <div ref={endRef} />
            </div>
          )}
        </div>
        <div className="border-t border-[rgba(255,255,255,0.06)] p-4">
          {attachment && (
            <div className="max-w-3xl mx-auto mb-2 flex items-center gap-2" data-testid="attachment-preview">
              <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-[#12121C] border border-[rgba(255,255,255,0.12)] text-xs text-[#94A3B8]">
                {attachment.kind === "image" ? <ImageIcon className="w-3.5 h-3.5 text-[#A855F7]" /> : <FileText className="w-3.5 h-3.5 text-[#A855F7]" />}
                <span className="max-w-[200px] truncate">{attachment.name}</span>
                <button data-testid="attachment-remove" onClick={() => setAttachment(null)} className="text-[#64748B] hover:text-red-400"><X className="w-3.5 h-3.5" /></button>
              </div>
            </div>
          )}
          <div className="max-w-3xl mx-auto mb-2 flex items-center gap-2">
            <button
              type="button"
              data-testid="nexus-toggle-btn"
              onClick={() => {
                if (!canNexus) { toast.error("Nexus Pro وكيل حصري لمشتركي Premium ($200). قم بالترقية للوصول إليه."); return; }
                setNexusMode((v) => !v);
              }}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${
                nexusMode
                  ? "bg-gradient-to-r from-[#6366F1] to-[#A855F7] text-white border-transparent shadow-[0_0_18px_-2px_rgba(168,85,247,0.7)]"
                  : "bg-[#12121C] text-[#A855F7] border-[rgba(168,85,247,0.35)] hover:border-[#A855F7]"
              }`}
              title={canNexus ? "وكيل خارق يمزج Claude + GPT + Gemini" : "حصري للبريميم"}
            >
              {canNexus ? <Zap className="w-3.5 h-3.5" /> : <Lock className="w-3.5 h-3.5" />}
              Nexus Pro
              <span className="text-[10px]">🔥</span>
              {!canNexus && <span className="ms-1 px-1.5 py-0.5 rounded-full bg-[#A855F7]/20 text-[#C4B5FD] text-[9px]">PRO</span>}
            </button>
            {nexusMode && (
              <span className="text-[11px] text-[#94A3B8]">مزيج الـ 3 نماذج مُفعّل — أقوى إجابة ممكنة (٨ كريدت/رسالة)</span>
            )}
          </div>
          <div className="max-w-3xl mx-auto flex items-end gap-3">
            <input ref={fileRef} type="file" accept="image/*,.pdf,.txt,.csv,.md,.json,.docx" className="hidden" onChange={pickFile} data-testid="chat-file-input" />
            <Button data-testid="chat-attach-btn" onClick={() => fileRef.current?.click()} disabled={uploading || sending} variant="outline"
              className="rounded-xl h-10 w-10 p-0 bg-[#12121C] border-[rgba(255,255,255,0.12)] text-[#94A3B8] hover:text-white shrink-0">
              {uploading ? <Dots /> : <Paperclip className="w-4 h-4" />}
            </Button>
            <Textarea data-testid="chat-input" value={input} onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
              placeholder="Describe what you want to create…" rows={1} className="resize-none bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors rounded-xl" />
            <Button data-testid="chat-ideas-btn" onClick={() => setGalleryOpen(true)} disabled={sending} title="Idea gallery" variant="outline"
              className="rounded-xl h-10 w-10 p-0 bg-[#12121C] border-[rgba(255,255,255,0.12)] text-[#A855F7] hover:text-white hover:border-[#A855F7] shrink-0"><Lightbulb className="w-4 h-4" /></Button>
            <Button data-testid="chat-voice-btn" onClick={startVoiceMode} disabled={sending || uploading} title="Talk to VibeVerse" variant="outline"
              className="rounded-xl h-10 w-10 p-0 bg-[#12121C] border-[rgba(255,255,255,0.12)] text-[#A855F7] hover:text-white hover:border-[#A855F7] shrink-0"><Mic className="w-4 h-4" /></Button>
            <Button data-testid="chat-send-btn" onClick={() => send()} disabled={sending || uploading || (!input.trim() && !attachment)} className="rounded-xl h-10 w-10 p-0 ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity shrink-0"><Send className="w-4 h-4" /></Button>
          </div>
          <p className="max-w-3xl mx-auto text-center text-[11px] text-[#64748B] mt-2">Attach an image or file, or just ask — VibeVerse makes images, voice, code, documents & web apps.</p>
        </div>
      </div>

      {voiceOpen && (() => {
        const accent = companion?.color || "#A855F7";
        const speaking = vStatus === "speaking";
        const listening = vStatus === "listening";
        const thinking = vStatus === "thinking";
        return (
        <div className="fixed inset-0 z-[60] flex flex-col items-center justify-between bg-[#05050A]/97 backdrop-blur-md py-8" data-testid="voice-overlay"
          style={{ background: `radial-gradient(circle at 50% 35%, ${accent}18, #05050A 70%)` }}>
          <button data-testid="voice-close-btn" onClick={stopVoiceMode} className="absolute top-5 end-5 text-[#94A3B8] hover:text-white z-10"><X className="w-6 h-6" /></button>

          {/* Companion header + switcher */}
          <div className="flex flex-col items-center gap-3 pt-2">
            <div className="flex items-center gap-2.5">
              <div className="w-11 h-11 rounded-2xl flex items-center justify-center text-2xl" style={{ background: `${accent}22`, border: `1px solid ${accent}66` }}>{companion?.emoji || "🎙️"}</div>
              <div className="text-start">
                <p className="text-white font-semibold leading-tight flex items-center gap-1.5">{companion?.name || "VibeVerse"}
                  {companion?.adult && <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/40">18+</span>}
                </p>
                <p className="text-[11px] text-[#64748B]">{companion?.tagline || "Your AI voice companion"}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <select data-testid="voice-agent-select" value={companion?.id || ""}
                onChange={(e) => { const a = agents.find((x) => x.id === e.target.value); if (a) { setCompanion(a); setVoice(a.voice); } }}
                className="bg-[#12121C] border border-[rgba(255,255,255,0.14)] text-xs text-[#94A3B8] rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-[#A855F7]">
                {agents.map((a) => <option key={a.id} value={a.id}>{a.emoji} {a.name}{a.adult ? " (18+)" : ""}</option>)}
              </select>
              <select data-testid="voice-select" value={voice} onChange={(e) => setVoice(e.target.value)}
                className="bg-[#12121C] border border-[rgba(255,255,255,0.14)] text-xs text-[#94A3B8] rounded-lg px-2.5 py-1.5 capitalize focus:outline-none focus:border-[#A855F7]">
                {VOICE_OPTS.map((v) => <option key={v} value={v} className="capitalize">{v}</option>)}
              </select>
              <select data-testid="voice-dialect-select" value={dialect}
                onChange={(e) => { const d = e.target.value; setDialect(d); api.put("/auth/me/preferences", { dialect: d }).catch(() => {}); }}
                className="bg-[#12121C] border border-[rgba(255,255,255,0.14)] text-xs text-[#94A3B8] rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-[#A855F7]">
                {DIALECT_OPTS.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}
              </select>
            </div>
          </div>

          {/* Animated orb — tap to interrupt/talk */}
          <button onClick={interrupt} data-testid="voice-orb" className="relative flex items-center justify-center focus:outline-none" style={{ width: 280, height: 280 }}
            title={speaking ? "Tap to interrupt" : "Tap to talk"}>
            {(listening || speaking) && (
              <>
                <span className="absolute rounded-full animate-ping" style={{ width: 220, height: 220, background: `${accent}22` }} />
                <span className="absolute rounded-full animate-pulse" style={{ width: 260, height: 260, border: `1px solid ${accent}44` }} />
              </>
            )}
            <span className="absolute rounded-full blur-2xl" style={{ width: 200, height: 200, background: `${accent}55` }} />
            <div className="relative rounded-full flex items-center justify-center transition-all duration-300"
              style={{ width: speaking ? 180 : listening ? 168 : 156, height: speaking ? 180 : listening ? 168 : 156,
                background: `radial-gradient(circle at 30% 30%, ${accent}, #6D28D9 60%, #0891B2)`,
                boxShadow: `0 0 60px -6px ${accent}` }}>
              {speaking ? (
                <div className="flex items-end gap-1.5 h-12" data-testid="voice-wave">
                  {[0,1,2,3,4].map((i) => (
                    <span key={i} className="w-1.5 rounded-full bg-white/90 voice-bar" style={{ animationDelay: `${i * 0.12}s` }} />
                  ))}
                </div>
              ) : thinking ? <Loader2 className="w-14 h-14 text-white animate-spin" />
                : <Mic className="w-14 h-14 text-white" />}
            </div>
          </button>

          {/* Status + live captions */}
          <div className="flex flex-col items-center px-6 w-full max-w-lg">
            <p className="text-lg font-medium text-white mb-2" data-testid="voice-status">
              {tapToHear ? "Tap to hear the reply" : listening ? "Listening…" : thinking ? "Thinking…" : speaking ? "Speaking — just talk to interrupt" : "Tap the orb to talk"}
            </p>
            <p className="text-sm text-[#B4C0D3] text-center min-h-[44px] leading-relaxed" data-testid="voice-transcript">{vTranscript}</p>
            <div className="flex items-center gap-3 mt-6">
              {tapToHear ? (
                <Button data-testid="voice-tap-hear-btn" onClick={playPending} className="rounded-full h-14 px-7 ai-gradient-bg text-white border-0"><Volume2 className="w-5 h-5 me-2" /> Tap to hear reply</Button>
              ) : vStatus === "idle" ? (
                <Button data-testid="voice-listen-btn" onClick={() => listen()} className="rounded-full h-14 px-7 ai-gradient-bg text-white border-0"><Mic className="w-5 h-5 me-2" /> Start talking</Button>
              ) : (
                <Button data-testid="voice-stop-btn" onClick={stopVoiceMode} variant="outline" className="rounded-full h-14 px-7 bg-red-500/10 border-red-500/40 text-red-300 hover:bg-red-500/20"><PhoneOff className="w-5 h-5 me-2" /> End conversation</Button>
              )}
            </div>
            <p className="text-[11px] text-[#64748B] mt-5 text-center">Best on Chrome &amp; Edge · Just start talking to interrupt · Headphones give the cleanest interruptions · Saved to this chat</p>
          </div>
        </div>
        );
      })()}

      {galleryOpen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" data-testid="gallery-overlay" onClick={() => setGalleryOpen(false)}>
          <div className="w-full max-w-3xl max-h-[85vh] flex flex-col rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.1)] overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-[rgba(255,255,255,0.08)]">
              <span className="flex items-center gap-2 text-white font-semibold"><Lightbulb className="w-5 h-5 text-[#A855F7]" /> Idea Gallery</span>
              <button data-testid="gallery-close-btn" onClick={() => setGalleryOpen(false)} className="text-[#64748B] hover:text-white"><X className="w-5 h-5" /></button>
            </div>
            <div className="flex gap-2 px-5 py-3 border-b border-[rgba(255,255,255,0.06)] overflow-x-auto">
              {PROMPT_GALLERY.map((g, ci) => (
                <button key={ci} data-testid={`gallery-cat-${ci}`} onClick={() => setGalleryCat(ci)}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm whitespace-nowrap transition-colors ${galleryCat === ci ? "ai-gradient-bg text-white" : "bg-[#12121C] text-[#94A3B8] hover:text-white border border-[rgba(255,255,255,0.1)]"}`}>
                  <g.icon className="w-4 h-4" /> {g.cat}
                </button>
              ))}
            </div>
            <div className="p-5 overflow-y-auto grid sm:grid-cols-2 gap-3">
              {PROMPT_GALLERY[galleryCat].items.map((it, ii) => (
                <button key={ii} data-testid={`gallery-item-${ii}`}
                  onClick={() => { setGalleryOpen(false); send(it.prompt); }}
                  className="text-start p-4 rounded-xl bg-[#12121C] border border-[rgba(255,255,255,0.08)] hover:border-[#A855F7] transition-colors group">
                  <p className="text-sm font-medium text-white mb-1 flex items-center gap-1.5">{it.title}<Sparkles className="w-3.5 h-3.5 text-[#A855F7] opacity-0 group-hover:opacity-100 transition-opacity" /></p>
                  <p className="text-xs text-[#64748B] line-clamp-2">{it.prompt}</p>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}


    </div>
  );
}
