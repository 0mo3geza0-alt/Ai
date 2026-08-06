import { useEffect, useRef, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { motion } from "framer-motion";
import { Plus, Send, Trash2, MessageSquare, Sparkles, Download, Copy, Check, Maximize2, Image as ImageIcon, Video, AudioLines, Code2, Globe, Paperclip, X, RefreshCw, FileText } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { toast } from "sonner";
import { api, formatApiErrorDetail } from "@/context/AuthContext";
import { Dots } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SUGGESTIONS = [
  { icon: ImageIcon, label: "Generate an image", text: "Generate an image of a futuristic city at sunset" },
  { icon: Video, label: "Make a video", text: "Make a short video of waves crashing on a beach" },
  { icon: Globe, label: "Build a web app", text: "Build a landing page for a coffee shop with a hero and menu" },
  { icon: Code2, label: "Write code", text: "Write a Python function that checks if a number is prime" },
  { icon: AudioLines, label: "Create a voiceover", text: "Create a voiceover: Welcome to VibeVerse, your all-in-one AI studio" },
];

const EXT = { image: "png", video: "mp4", voice: "mp3", audio: "mp3" };

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

function VideoBlock({ m, media, pollJob }) {
  const status = media?.status || "processing";
  useEffect(() => { if (status === "processing" && media?.cid) pollJob(m); }, [status]); // eslint-disable-line
  if (status === "processing") return <div className="mt-3 h-40 rounded-xl border border-[rgba(255,255,255,0.08)] bg-[#0C0C14] flex flex-col items-center justify-center gap-2 text-[#64748B] text-sm" data-testid="chat-video-processing"><Dots /> Rendering video — 1-3 min…</div>;
  if (status === "failed") return <div className="mt-3 p-3 rounded-xl border border-red-500/30 bg-red-500/5 text-red-400 text-sm">Video failed to render. Please try again.</div>;
  return (
    <div className="mt-3 rounded-xl overflow-hidden border border-[rgba(255,255,255,0.08)] bg-[#0C0C14]">
      <BlobMedia url={media.url} fallbackH="h-40" render={(src) => <video data-testid="chat-video" src={src} controls className="w-full max-h-[420px]" />} />
      <div className="p-2"><button onClick={() => downloadBlob(media.url, "nexus-video.mp4")} className="inline-flex items-center gap-1.5 text-xs text-[#A855F7] hover:underline"><Download className="w-3.5 h-3.5" /> Download</button></div>
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
  if (m.kind === "video") return <VideoBlock m={m} media={media} pollJob={pollJob} />;
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
  const fileRef = useRef(null);
  const endRef = useRef(null);

  const loadSessions = async () => { const { data } = await api.get(`/orgs/${oid}/chat/sessions`); setSessions(data); return data; };
  useEffect(() => { setActive(null); setMessages([]); loadSessions(); }, [oid]); // eslint-disable-line
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, sending]);

  const openSession = async (id) => { setActive(id); const { data } = await api.get(`/orgs/${oid}/chat/sessions/${id}/messages`); setMessages(data); };
  const newChat = async () => { setActive(null); setMessages([]); setAttachment(null); };
  const delSession = async (id, e) => { e.stopPropagation(); await api.delete(`/orgs/${oid}/chat/sessions/${id}`); if (active === id) { setActive(null); setMessages([]); } loadSessions(); };

  const pickFile = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    setUploading(true);
    try {
      const fd = new FormData(); fd.append("file", f);
      const { data } = await api.post(`/orgs/${oid}/uploads`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setAttachment(data);
    } catch (err) { toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Upload failed"); }
    finally { setUploading(false); }
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
            if ((mm.kind === "video" || mm.kind === "webapp") && mm.media?.status === "processing") pollJob({ media: mm.media });
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
        <div className="flex-1 overflow-y-auto px-5 lg:px-8 py-6">
          {messages.length === 0 && !sending ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <span className="w-14 h-14 rounded-2xl ai-gradient-bg flex items-center justify-center mb-5 glow-border"><Sparkles className="w-6 h-6 text-white" /></span>
              <h2 className="font-display text-xl font-semibold mb-2">What do you want to create?</h2>
              <p className="text-[#64748B] max-w-md mb-6">Ask anything — images, videos, voiceovers, code, documents or full web apps. VibeVerse figures out what to build and returns it right here.</p>
              <div className="flex flex-wrap gap-2 justify-center max-w-2xl">
                {SUGGESTIONS.map((s, i) => (
                  <button key={i} data-testid={`chat-suggestion-${i}`} onClick={() => send(s.text)}
                    className="inline-flex items-center gap-2 px-3.5 py-2 rounded-full text-sm bg-[#12121C] border border-[rgba(255,255,255,0.1)] text-[#94A3B8] hover:text-white hover:border-[#A855F7] transition-colors">
                    <s.icon className="w-4 h-4 text-[#A855F7]" /> {s.label}
                  </button>
                ))}
              </div>
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
            <Button data-testid="chat-send-btn" onClick={() => send()} disabled={sending || uploading || (!input.trim() && !attachment)} className="rounded-xl h-10 w-10 p-0 ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity shrink-0"><Send className="w-4 h-4" /></Button>
          </div>
          <p className="max-w-3xl mx-auto text-center text-[11px] text-[#64748B] mt-2">Attach an image or file, or just ask — VibeVerse makes images, videos, voice, code, documents & web apps.</p>
        </div>
      </div>
    </div>
  );
}
