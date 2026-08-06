import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Play, Pause, Check, Loader2, Sparkles, ShieldAlert, Mic } from "lucide-react";
import { api, formatApiErrorDetail } from "@/context/AuthContext";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

// First-run experience: every user picks an AI voice companion + voice before using voice mode.
export default function VoiceOnboarding({ oid, onDone }) {
  const [agents, setAgents] = useState([]);
  const [voices, setVoices] = useState([]);
  const [selected, setSelected] = useState(null);
  const [voice, setVoice] = useState(null);
  const [adult, setAdult] = useState(false);
  const [saving, setSaving] = useState(false);
  const [previewId, setPreviewId] = useState(null); // agent id currently previewing
  const audioRef = useRef(null);

  useEffect(() => {
    api.get("/voice-agents")
      .then(({ data }) => { setAgents(data.agents || []); setVoices(data.voices || []); })
      .catch(() => toast.error("Could not load voice companions"));
    return () => { try { audioRef.current?.pause(); } catch { /* noop */ } };
  }, []);

  const pick = (a) => {
    setSelected(a);
    setVoice(a.voice);
    if (!a.adult) setAdult(false);
  };

  const preview = async (a, e) => {
    e.stopPropagation();
    try { audioRef.current?.pause(); } catch { /* noop */ }
    if (previewId === a.id) { setPreviewId(null); return; }
    setPreviewId(a.id);
    try {
      const useVoice = selected?.id === a.id ? voice : a.voice;
      const { data } = await api.post(`/orgs/${oid}/voice-sample`, { agent: a.id, voice: useVoice });
      if (!data.audio) throw new Error("no audio");
      const audio = new Audio(`data:${data.mime || "audio/mpeg"};base64,${data.audio}`);
      audioRef.current = audio;
      audio.onended = () => setPreviewId(null);
      audio.onerror = () => setPreviewId(null);
      await audio.play();
    } catch (err) {
      setPreviewId(null);
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Preview failed");
    }
  };

  const save = async () => {
    if (!selected) return;
    if (selected.adult && !adult) { toast.error("Please confirm you are 18+ to choose this companion"); return; }
    setSaving(true);
    try {
      try { audioRef.current?.pause(); } catch { /* noop */ }
      const { data } = await api.put("/auth/me/preferences", {
        voice_agent: selected.id, voice, adult_confirmed: !!(selected.adult && adult),
      });
      toast.success(`${selected.name} is now your voice companion`);
      onDone?.(data);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not save your choice");
    } finally { setSaving(false); }
  };

  const genderPill = (g) => g === "male" ? "♂ Male" : g === "female" ? "♀ Female" : "Neutral";

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-[#05050A]/95 backdrop-blur-md p-4 overflow-y-auto" data-testid="voice-onboarding">
      <motion.div initial={{ opacity: 0, y: 24, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
        className="w-full max-w-4xl my-8 rounded-3xl bg-[#0C0C14] border border-[rgba(255,255,255,0.1)] overflow-hidden shadow-2xl">
        <div className="px-7 pt-8 pb-5 text-center border-b border-[rgba(255,255,255,0.06)]">
          <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#A855F7]/10 border border-[#A855F7]/30 text-[#C4B5FD] text-xs mb-3">
            <Sparkles className="w-3.5 h-3.5" /> Welcome to VibeVerse Voice
          </span>
          <h2 className="text-2xl sm:text-3xl font-bold text-white">Choose your AI voice companion</h2>
          <p className="text-sm text-[#94A3B8] mt-2 max-w-lg mx-auto">Pick a personality and voice. You can preview each one and change it anytime in voice mode.</p>
        </div>

        <div className="p-5 sm:p-6 grid sm:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[46vh] overflow-y-auto">
          {agents.length === 0 && <div className="col-span-full flex justify-center py-10"><Loader2 className="w-6 h-6 text-[#A855F7] animate-spin" /></div>}
          {agents.map((a) => {
            const active = selected?.id === a.id;
            return (
              <button key={a.id} data-testid={`voice-agent-${a.id}`} onClick={() => pick(a)}
                className="relative text-start p-4 rounded-2xl border transition-all bg-[#12121C] hover:border-white/25"
                style={{ borderColor: active ? a.color : "rgba(255,255,255,0.08)", boxShadow: active ? `0 0 0 1px ${a.color}, 0 8px 30px -12px ${a.color}` : "none" }}>
                {active && <span className="absolute top-3 end-3 w-6 h-6 rounded-full flex items-center justify-center text-white" style={{ background: a.color }}><Check className="w-4 h-4" /></span>}
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-12 h-12 rounded-2xl flex items-center justify-center text-2xl" style={{ background: `${a.color}22`, border: `1px solid ${a.color}55` }}>{a.emoji}</div>
                  <div>
                    <p className="text-white font-semibold leading-tight flex items-center gap-1.5">{a.name}
                      {a.adult && <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/40">18+</span>}
                    </p>
                    <span className="text-[11px] text-[#64748B]">{genderPill(a.gender)}</span>
                  </div>
                </div>
                <p className="text-xs text-[#94A3B8] min-h-[32px] leading-snug">{a.tagline}</p>
                <span onClick={(e) => preview(a, e)}
                  className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg bg-black/30 text-white hover:bg-black/50 transition-colors cursor-pointer"
                  data-testid={`voice-preview-${a.id}`}>
                  {previewId === a.id ? <><Pause className="w-3.5 h-3.5" /> Playing…</> : <><Play className="w-3.5 h-3.5" /> Preview voice</>}
                </span>
              </button>
            );
          })}
        </div>

        <div className="px-6 pb-6 pt-4 border-t border-[rgba(255,255,255,0.06)] space-y-4">
          {selected && (
            <div className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
              <div className="flex items-center gap-2 text-sm text-[#94A3B8]">
                <Mic className="w-4 h-4 text-[#A855F7]" /> Voice for <span className="text-white font-medium">{selected.name}</span>:
                <select data-testid="onboarding-voice-select" value={voice || ""} onChange={(e) => setVoice(e.target.value)}
                  className="bg-[#12121C] border border-[rgba(255,255,255,0.14)] text-white rounded-lg px-2.5 py-1.5 capitalize focus:outline-none focus:border-[#A855F7]">
                  {voices.map((v) => <option key={v} value={v} className="capitalize">{v}</option>)}
                </select>
              </div>
              {selected.adult && (
                <label className="flex items-center gap-2 text-xs text-red-300 cursor-pointer" data-testid="adult-confirm">
                  <input type="checkbox" checked={adult} onChange={(e) => setAdult(e.target.checked)} className="accent-red-500 w-4 h-4" />
                  <ShieldAlert className="w-4 h-4" /> I confirm I am 18 years or older
                </label>
              )}
            </div>
          )}
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] text-[#64748B] max-w-xs hidden sm:block">Voices are studio-quality (HD). Adult companions use bolder, unfiltered language.</p>
            <Button data-testid="onboarding-continue" onClick={save} disabled={!selected || saving || (selected?.adult && !adult)}
              className="rounded-xl h-11 px-7 ai-gradient-bg text-white border-0 hover:opacity-90 disabled:opacity-40">
              {saving ? <Loader2 className="w-4 h-4 me-2 animate-spin" /> : <Check className="w-4 h-4 me-2" />} Start talking
            </Button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
