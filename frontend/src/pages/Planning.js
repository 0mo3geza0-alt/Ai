import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Workflow, Play, Search, Link2, Brain, History, X, ChevronDown, ChevronRight } from "lucide-react";
import { api, formatApiErrorDetail } from "@/context/AuthContext";
import { Dots } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const ACTION_META = {
  research: { icon: Search, label: "Research", color: "#06B6D4" },
  browse: { icon: Link2, label: "Browse", color: "#A855F7" },
  reason: { icon: Brain, label: "Reason", color: "#F59E0B" },
};

function StepCard({ step, index, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen);
  const meta = ACTION_META[step.action] || ACTION_META.reason;
  const Icon = meta.icon;
  return (
    <div className="rounded-xl bg-[#12121C] border border-[rgba(255,255,255,0.06)] overflow-hidden">
      <button data-testid={`plan-step-${index}`} onClick={() => setOpen((o) => !o)} className="w-full flex items-center gap-3 p-3 text-left hover:bg-white/[0.02] transition-colors">
        <span className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0" style={{ background: meta.color + "22", color: meta.color }}><Icon className="w-4 h-4" /></span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-white truncate">Step {index + 1}: {step.title}</p>
          <p className="text-[11px] uppercase tracking-wide" style={{ color: meta.color }}>{meta.label}{step.tool_used ? ` · ${step.tool_used}` : ""}</p>
        </div>
        {open ? <ChevronDown className="w-4 h-4 text-[#64748B]" /> : <ChevronRight className="w-4 h-4 text-[#64748B]" />}
      </button>
      {open && (
        <div className="px-3 pb-3 pt-0">
          {step.query && <p className="text-xs text-[#64748B] mb-2 italic">→ {step.query}</p>}
          <p className="text-sm text-[#CBD5E1] whitespace-pre-wrap leading-relaxed">{step.output}</p>
        </div>
      )}
    </div>
  );
}

export default function Planning() {
  const { activeOrg, refreshUsage } = useOutletContext();
  const oid = activeOrg.id;
  const [goal, setGoal] = useState("");
  const [maxSteps, setMaxSteps] = useState("5");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => { setResult(null); setHistory([]); setShowHistory(false); }, [oid]);

  const run = async () => {
    if (!goal.trim()) { toast.error("Enter a goal for the planner."); return; }
    setRunning(true); setResult(null);
    try {
      const { data } = await api.post(`/orgs/${oid}/plan/run`, { goal: goal.trim(), max_steps: Number(maxSteps) });
      setResult(data);
      refreshUsage();
    } catch (e) {
      toast.error(e.response?.status === 402 ? "Out of credits — upgrade the org plan." : formatApiErrorDetail(e.response?.data?.detail));
    } finally { setRunning(false); }
  };

  const loadHistory = async () => {
    try { const { data } = await api.get(`/orgs/${oid}/plan/runs`); setHistory(data); setShowHistory(true); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  return (
    <div className="px-5 lg:px-8 py-8 max-w-4xl">
      <div className="flex items-start justify-between gap-4 mb-1">
        <h1 className="font-display text-2xl md:text-3xl font-bold flex items-center gap-2"><Workflow className="w-7 h-7 text-[#A855F7]" /> Planning Engine</h1>
        <button data-testid="plan-history-btn" onClick={loadHistory} className="text-xs text-[#94A3B8] hover:text-white flex items-center gap-1 mt-2"><History className="w-3.5 h-3.5" /> History</button>
      </div>
      <p className="text-[#94A3B8] mb-6">Give a complex goal — the planner breaks it into steps (research, browse, reason), executes each one, and synthesizes a final result.</p>

      <div className="p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
        <Label className="text-[#94A3B8]">Goal</Label>
        <Textarea data-testid="plan-goal-input" value={goal} onChange={(e) => setGoal(e.target.value)} rows={3} placeholder="e.g. Research the latest on electric cars and write a short buyer's guide with 5 tips." className="mt-1.5 resize-none bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white" />
        <div className="flex flex-wrap items-end gap-3 mt-3">
          <div>
            <Label className="text-[#94A3B8] text-xs">Max steps</Label>
            <Select value={maxSteps} onValueChange={setMaxSteps}>
              <SelectTrigger data-testid="plan-maxsteps-select" className="mt-1.5 w-28 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#12121C] border-[rgba(255,255,255,0.12)] text-white">{[2, 3, 4, 5, 6, 7, 8].map((n) => <SelectItem key={n} value={String(n)} className="focus:bg-white/5">{n} steps</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <Button data-testid="plan-run-btn" onClick={run} disabled={running || !goal.trim()} className="rounded-full h-11 px-8 ai-gradient-bg text-white border-0 hover:opacity-90">{running ? <Dots /> : <><Play className="w-4 h-4 me-2" /> Run planner</>}</Button>
        </div>
      </div>

      {running && (
        <div className="mt-4 p-6 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] text-center">
          <div className="flex justify-center mb-2"><Dots /></div>
          <p className="text-sm text-[#64748B]">Planning and executing steps… this can take up to a minute.</p>
        </div>
      )}

      {!running && result && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mt-6">
          <p className="text-sm font-medium text-[#94A3B8] mb-2">Execution plan ({result.steps?.length || 0} steps)</p>
          <div className="space-y-2">
            {result.steps?.map((s, i) => <StepCard key={i} step={s} index={i} defaultOpen={false} />)}
          </div>
          <div className="mt-5 p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(168,85,247,0.25)]">
            <p className="text-xs text-[#A855F7] font-medium mb-2 flex items-center gap-1"><Sparkle /> Final result</p>
            <pre data-testid="plan-output" className="text-sm text-[#F8FAFC] whitespace-pre-wrap leading-relaxed font-sans">{result.output}</pre>
          </div>
        </motion.div>
      )}

      {showHistory && (
        <div className="mt-6 p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
          <div className="flex items-center justify-between mb-3"><p className="text-sm text-[#94A3B8]">Recent plans</p><button onClick={() => setShowHistory(false)} className="text-[#64748B] hover:text-white"><X className="w-4 h-4" /></button></div>
          {history.length === 0 ? <p className="text-xs text-[#64748B]">No plans yet.</p> : (
            <div className="space-y-2">
              {history.map((h) => (
                <button key={h.id} data-testid={`plan-history-${h.id}`} onClick={() => { setResult(h); setShowHistory(false); window.scrollTo({ top: 0, behavior: "smooth" }); }} className="w-full text-left py-2.5 px-3 rounded-xl bg-[#12121C] border border-[rgba(255,255,255,0.04)] hover:border-[rgba(255,255,255,0.15)] transition-colors">
                  <p className="text-sm text-white truncate">{h.goal}</p>
                  <p className="text-xs text-[#64748B] mt-0.5">{(h.steps?.length || 0)} steps · {new Date(h.created_at).toLocaleString()}</p>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Sparkle() {
  return <svg className="w-3.5 h-3.5 inline" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.9 5.8L20 9.7l-4.9 3.6L17 20l-5-3.7L7 20l1.9-6.7L4 9.7l6.1-1.9L12 2z" /></svg>;
}
