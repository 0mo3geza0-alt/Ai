import { useEffect, useRef, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { motion } from "framer-motion";
import { Plus, Send, Trash2, MessageSquare, Sparkles, Download, Copy, Check, Maximize2, Image as ImageIcon, AudioLines, Code2, Globe, Paperclip, X, RefreshCw, FileText, Mic, Loader2, PhoneOff, Volume2, Lightbulb } from "lucide-react";
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
  const { activeOrg, refreshUsage } = useOutletContext();
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
  const fileRef = useRef(null);
  const endRef = useRef(null);
  // --- live voice conversation ---
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [vStatus, setVStatus] = useState("idle"); // idle | listening | thinking | speaking
  const [vTranscript, setVTranscript] = useState("");
  const [voice, setVoice] = useState("nova");
  const recogRef = useRef(null);
  const audioRef = useRef(null);
  const voiceOpenRef = useRef(false);
  const activeRef = useRef(null);
  useEffect(() => { activeRef.current = active; }, [active]);

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
  const stopAudio = () => { try { audioRef.current?.pause(); } catch { /* noop */ } audioRef.current = null; };

  const stopVoiceMode = () => {
    voiceOpenRef.current = false;
    setVoiceOpen(false);
    setVStatus("idle");
    setVTranscript("");
    try { recogRef.current?.abort?.(); } catch { /* noop */ }
    recogRef.current = null;
    stopAudio();
  };

  const listen = () => {
    if (!voiceOpenRef.current) return;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    const rec = new SR();
    rec.lang = navigator.language || "en-US";
    rec.interimResults = true;
    rec.continuous = false;
    recogRef.current = rec;
    setVTranscript("");
    setVStatus("listening");
    let finalText = "";
    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalText += t; else interim += t;
      }
      setVTranscript(finalText || interim);
    };
    rec.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        toast.error("Microphone permission is required for voice mode");
        stopVoiceMode();
      }
    };
    rec.onend = () => {
      const said = finalText.trim();
      if (!voiceOpenRef.current) return;
      if (said) handleVoiceTurn(said);
      else if (vStatusIsListening()) listen(); // nothing captured, keep listening
    };
    try { rec.start(); } catch { /* already started */ }
  };

  const vStatusIsListening = () => recogRef.current !== null;

  const handleVoiceTurn = async (said) => {
    setVStatus("thinking");
    setVTranscript(said);
    let sid = activeRef.current;
    if (!sid) { const { data } = await api.post(`/orgs/${oid}/chat/sessions`, {}); sid = data.id; setActive(sid); loadSessions(); }
    setMessages((m) => [...m, { role: "user", content: said, kind: "text", media: null }]);
    setMessages((m) => [...m, { role: "assistant", content: "", kind: "text", media: null, _streaming: true }]);
    const patchLast = (fn) => setMessages((m) => { const c = [...m]; c[c.length - 1] = fn(c[c.length - 1]); return c; });
    try {
      const { data } = await api.post(`/orgs/${oid}/chat/sessions/${sid}/voice-chat`, { message: said, voice });
      patchLast(() => ({ role: "assistant", content: data.reply, kind: "text", media: null }));
      refreshUsage?.();
      loadSessions();
      if (data.audio && voiceOpenRef.current) {
        setVStatus("speaking");
        stopAudio();
        const audio = new Audio(`data:${data.mime || "audio/mpeg"};base64,${data.audio}`);
        audioRef.current = audio;
        audio.onended = () => { if (voiceOpenRef.current) listen(); else setVStatus("idle"); };
        audio.onerror = () => { if (voiceOpenRef.current) listen(); };
        audio.play().catch(() => { if (voiceOpenRef.current) listen(); });
      } else if (voiceOpenRef.current) {
        listen();
      }
    } catch (e) {
      patchLast(() => ({ role: "assistant", content: "Sorry, something went wrong.", kind: "text", media: null }));
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Voice chat failed");
      if (voiceOpenRef.current) setTimeout(() => listen(), 800);
    }
  };

  const startVoiceMode = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { toast.error("Voice mode works best on Chrome or Edge browsers."); return; }
    voiceOpenRef.current = true;
    setVoiceOpen(true);
    setVStatus("idle");
    setTimeout(() => listen(), 300);
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

      {voiceOpen && (
        <div className="fixed inset-0 z-[60] flex flex-col items-center justify-center bg-[#07070C]/95 backdrop-blur-sm" data-testid="voice-overlay">
          <button data-testid="voice-close-btn" onClick={stopVoiceMode} className="absolute top-5 end-5 text-[#64748B] hover:text-white"><X className="w-6 h-6" /></button>

          <div className="mb-6">
            <select data-testid="voice-select" value={voice} onChange={(e) => setVoice(e.target.value)}
              className="bg-[#12121C] border border-[rgba(255,255,255,0.12)] text-sm text-[#94A3B8] rounded-lg px-3 py-1.5 capitalize focus:outline-none">
              {VOICE_OPTS.map((v) => <option key={v} value={v} className="capitalize">{v}</option>)}
            </select>
          </div>

          <div className="relative flex items-center justify-center mb-8">
            <span className={`absolute rounded-full ${vStatus === "listening" ? "animate-ping bg-[#A855F7]/40" : vStatus === "speaking" ? "animate-pulse bg-[#22D3EE]/30" : "bg-transparent"}`} style={{ width: 180, height: 180 }} />
            <div className={`relative w-36 h-36 rounded-full flex items-center justify-center transition-colors ${vStatus === "thinking" ? "bg-gradient-to-br from-[#6D28D9] to-[#D946EF]" : vStatus === "speaking" ? "bg-gradient-to-br from-[#0891B2] to-[#6D28D9]" : "ai-gradient-bg"}`}>
              {vStatus === "thinking" ? <Loader2 className="w-12 h-12 text-white animate-spin" />
                : vStatus === "speaking" ? <Volume2 className="w-12 h-12 text-white" />
                : <Mic className="w-12 h-12 text-white" />}
            </div>
          </div>

          <p className="text-lg font-medium text-white mb-1" data-testid="voice-status">
            {vStatus === "listening" ? "Listening…" : vStatus === "thinking" ? "Thinking…" : vStatus === "speaking" ? "Speaking…" : "Tap the mic to talk"}
          </p>
          <p className="text-sm text-[#94A3B8] max-w-md text-center min-h-[20px] px-6" data-testid="voice-transcript">{vTranscript}</p>

          <div className="flex items-center gap-4 mt-10">
            {vStatus === "idle" ? (
              <Button data-testid="voice-listen-btn" onClick={() => listen()} className="rounded-full h-14 px-6 ai-gradient-bg text-white border-0"><Mic className="w-5 h-5 me-2" /> Start talking</Button>
            ) : (
              <Button data-testid="voice-stop-btn" onClick={stopVoiceMode} variant="outline" className="rounded-full h-14 px-6 bg-red-500/10 border-red-500/40 text-red-300 hover:bg-red-500/20"><PhoneOff className="w-5 h-5 me-2" /> End conversation</Button>
            )}
          </div>
          <p className="text-[11px] text-[#64748B] mt-6">Voice mode works best on Chrome &amp; Edge. Your conversation is saved to this chat.</p>
        </div>
      )}

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
