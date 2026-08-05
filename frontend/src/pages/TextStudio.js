import { useState } from "react";
import { motion } from "framer-motion";
import { Copy, Check, PenLine } from "lucide-react";
import { toast } from "sonner";
import { useApp, api, formatApiErrorDetail } from "@/context/AppContext";
import { Dots } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export default function TextStudio() {
  const { t, updateCredits } = useApp();
  const [mode, setMode] = useState("article");
  const [prompt, setPrompt] = useState("");
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const modes = [
    { id: "article", label: t.text.article },
    { id: "rewrite", label: t.text.rewrite },
    { id: "summarize", label: t.text.summarize },
  ];

  const generate = async () => {
    if (!prompt.trim()) return;
    setLoading(true); setResult("");
    try {
      const { data } = await api.post("/text/generate", { prompt, mode });
      setResult(data.result);
      updateCredits(data.credits);
    } catch (err) {
      toast.error(err.response?.status === 402 ? t.common.noCredits : formatApiErrorDetail(err.response?.data?.detail) || t.common.error);
    } finally { setLoading(false); }
  };

  const copy = () => { navigator.clipboard.writeText(result); setCopied(true); toast.success(t.text.copied); setTimeout(() => setCopied(false), 1500); };

  return (
    <div className="px-5 lg:px-8 py-8 max-w-5xl">
      <h1 className="font-display text-2xl md:text-3xl font-bold mb-1">{t.text.title}</h1>
      <p className="text-[#94A3B8] mb-8">{t.text.sub}</p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div className="flex gap-2 flex-wrap">
            {modes.map((m) => (
              <button key={m.id} onClick={() => setMode(m.id)} data-testid={`text-mode-${m.id}`}
                className={`px-4 py-2 rounded-full text-sm transition-colors border ${mode === m.id ? "ai-gradient-bg text-white border-transparent" : "bg-transparent text-[#94A3B8] border-[rgba(255,255,255,0.12)] hover:text-white"}`}>
                {m.label}
              </button>
            ))}
          </div>
          <Textarea data-testid="text-prompt-input" value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={10}
            placeholder={t.text.placeholder}
            className="resize-none bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors rounded-xl" />
          <Button data-testid="text-generate-btn" onClick={generate} disabled={loading || !prompt.trim()}
            className="rounded-full h-11 px-8 ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity">
            {loading ? <Dots /> : t.text.generate}
          </Button>
        </div>

        <div className="rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] p-5 min-h-[300px] relative">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-[#64748B]">{t.text.result}</span>
            {result && <button onClick={copy} data-testid="text-copy-btn" className="flex items-center gap-1.5 text-xs text-[#94A3B8] hover:text-white transition-colors">{copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />} {copied ? t.text.copied : t.text.copy}</button>}
          </div>
          {loading ? (
            <div className="h-40 flex items-center justify-center"><Dots /></div>
          ) : result ? (
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} data-testid="text-result" className="text-sm text-[#F8FAFC] leading-relaxed whitespace-pre-wrap">{result}</motion.p>
          ) : (
            <div className="h-40 flex flex-col items-center justify-center text-center text-[#64748B]">
              <PenLine className="w-8 h-8 mb-3 opacity-40" /><p className="text-sm">{t.text.empty}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
