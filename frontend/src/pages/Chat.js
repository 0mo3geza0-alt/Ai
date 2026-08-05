import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Plus, Send, Trash2, MessageSquare } from "lucide-react";
import { toast } from "sonner";
import { useApp, api, formatApiErrorDetail } from "@/context/AppContext";
import { Dots } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export default function Chat() {
  const { t, updateCredits } = useApp();
  const [sessions, setSessions] = useState([]);
  const [active, setActive] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef(null);

  const loadSessions = async () => { const { data } = await api.get("/chat/sessions"); setSessions(data); return data; };
  useEffect(() => { loadSessions(); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, sending]);

  const openSession = async (id) => {
    setActive(id);
    const { data } = await api.get(`/chat/sessions/${id}/messages`);
    setMessages(data);
  };

  const newChat = async () => {
    const { data } = await api.post("/chat/sessions", { title: "New chat" });
    await loadSessions();
    setActive(data.id); setMessages([]);
  };

  const delSession = async (id, e) => {
    e.stopPropagation();
    await api.delete(`/chat/sessions/${id}`);
    if (active === id) { setActive(null); setMessages([]); }
    loadSessions();
  };

  const send = async () => {
    const text = input.trim();
    if (!text) return;
    let sid = active;
    if (!sid) {
      const { data } = await api.post("/chat/sessions", { title: "New chat" });
      sid = data.id; setActive(sid); await loadSessions();
    }
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setSending(true);
    try {
      const { data } = await api.post(`/chat/sessions/${sid}/send`, { message: text });
      setMessages((m) => [...m, { role: "assistant", content: data.reply }]);
      updateCredits(data.credits);
      loadSessions();
    } catch (err) {
      const msg = formatApiErrorDetail(err.response?.data?.detail);
      toast.error(err.response?.status === 402 ? t.common.noCredits : msg || t.common.error);
      setMessages((m) => m.slice(0, -1));
    } finally { setSending(false); }
  };

  return (
    <div className="flex h-[calc(100vh-56px)] lg:h-screen">
      {/* sessions list */}
      <aside className="hidden md:flex w-64 shrink-0 flex-col border-e border-[rgba(255,255,255,0.06)] bg-[#0C0C14]">
        <div className="p-4">
          <Button data-testid="new-chat-btn" onClick={newChat} className="w-full rounded-xl ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity">
            <Plus className="w-4 h-4 me-2" /> {t.chat.newChat}
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 space-y-1">
          {sessions.length === 0 && <p className="text-center text-sm text-[#64748B] mt-6">{t.chat.noSessions}</p>}
          {sessions.map((s) => (
            <div key={s.id} onClick={() => openSession(s.id)} data-testid={`chat-session-${s.id}`}
              className={`group flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm cursor-pointer transition-colors ${active === s.id ? "bg-white/5 text-white" : "text-[#94A3B8] hover:bg-white/5"}`}>
              <MessageSquare className="w-4 h-4 shrink-0" />
              <span className="truncate flex-1">{s.title}</span>
              <button onClick={(e) => delSession(s.id, e)} data-testid={`delete-session-${s.id}`} className="opacity-0 group-hover:opacity-100 text-[#64748B] hover:text-red-400 transition-opacity"><Trash2 className="w-4 h-4" /></button>
            </div>
          ))}
        </div>
      </aside>

      {/* conversation */}
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex-1 overflow-y-auto px-5 lg:px-8 py-6">
          {messages.length === 0 && !sending ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <span className="w-14 h-14 rounded-2xl ai-gradient-bg flex items-center justify-center mb-5 glow-border"><MessageSquare className="w-6 h-6 text-white" /></span>
              <h2 className="font-display text-xl font-semibold mb-2">{t.chat.empty}</h2>
              <p className="text-[#64748B] max-w-sm">{t.chat.emptySub}</p>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-5">
              {messages.map((m, i) => (
                <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
                  className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div data-testid={`chat-msg-${m.role}`} className={`max-w-[85%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${m.role === "user" ? "ai-gradient-bg text-white" : "bg-[#12121C] border border-[rgba(255,255,255,0.08)] text-[#F8FAFC]"}`}>
                    {m.content}
                  </div>
                </motion.div>
              ))}
              {sending && <div className="flex justify-start"><div className="px-4 py-3 rounded-2xl bg-[#12121C] border border-[rgba(255,255,255,0.08)]"><Dots /></div></div>}
              <div ref={endRef} />
            </div>
          )}
        </div>
        <div className="border-t border-[rgba(255,255,255,0.06)] p-4">
          <div className="max-w-3xl mx-auto flex items-end gap-3">
            <Textarea data-testid="chat-input" value={input} onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
              placeholder={t.chat.placeholder} rows={1}
              className="resize-none bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors rounded-xl" />
            <Button data-testid="chat-send-btn" onClick={send} disabled={sending || !input.trim()}
              className="rounded-xl h-10 w-10 p-0 ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity shrink-0">
              <Send className="w-4 h-4 rtl:rotate-180" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
