import { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Bot, Plus, Play, Trash2, Pencil, Users, Sparkles, Globe, Brain, History, X } from "lucide-react";
import { api, formatApiErrorDetail } from "@/context/AuthContext";
import { Dots } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";

const ROLES = ["assistant", "researcher", "coder", "writer", "analyst", "manager"];
const PROVIDERS = [{ v: "auto", l: "Auto (smart routing)" }, { v: "openai", l: "OpenAI" }, { v: "anthropic", l: "Anthropic" }, { v: "gemini", l: "Gemini" }];
const COLORS = ["#A855F7", "#4F46E5", "#EC4899", "#10B981", "#F59E0B", "#06B6D4"];
const EMPTY = { name: "", description: "", role: "assistant", provider: "auto", model: "", system_prompt: "", tools: [], knowledge: "", color: "#A855F7" };

function AgentForm({ open, onOpenChange, initial, onSaved, oid }) {
  const [f, setF] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (open) setF(initial || EMPTY); }, [open, initial]);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const toggleTool = (t) => setF((p) => ({ ...p, tools: p.tools.includes(t) ? p.tools.filter((x) => x !== t) : [...p.tools, t] }));

  const save = async () => {
    if (!f.name.trim() || !f.system_prompt.trim()) { toast.error("Name and system prompt are required."); return; }
    setSaving(true);
    const body = {
      name: f.name.trim(), description: f.description, role: f.role,
      provider: f.provider === "auto" ? null : f.provider, model: f.model.trim() || null,
      system_prompt: f.system_prompt, tools: f.tools, color: f.color,
      knowledge: (f.knowledge || "").split("\n").map((s) => s.trim()).filter(Boolean),
    };
    try {
      if (initial?.id) await api.patch(`/orgs/${oid}/agents/${initial.id}`, body);
      else await api.post(`/orgs/${oid}/agents`, body);
      toast.success(initial?.id ? "Agent updated" : "Agent created");
      onSaved(); onOpenChange(false);
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#0C0C14] border-[rgba(255,255,255,0.1)] text-white max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="font-display">{initial?.id ? "Edit agent" : "New agent"}</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div>
            <Label className="text-[#94A3B8]">Name</Label>
            <Input data-testid="agent-name-input" value={f.name} onChange={(e) => set("name", e.target.value)} placeholder="Research Assistant" className="mt-1.5 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white" />
          </div>
          <div>
            <Label className="text-[#94A3B8]">Description</Label>
            <Input data-testid="agent-desc-input" value={f.description} onChange={(e) => set("description", e.target.value)} placeholder="What does this agent do?" className="mt-1.5 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-[#94A3B8]">Role</Label>
              <Select value={f.role} onValueChange={(v) => set("role", v)}>
                <SelectTrigger data-testid="agent-role-select" className="mt-1.5 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white capitalize"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-[#12121C] border-[rgba(255,255,255,0.12)] text-white">{ROLES.map((r) => <SelectItem key={r} value={r} className="capitalize focus:bg-white/5">{r}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-[#94A3B8]">Model</Label>
              <Select value={f.provider} onValueChange={(v) => set("provider", v)}>
                <SelectTrigger data-testid="agent-provider-select" className="mt-1.5 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-[#12121C] border-[rgba(255,255,255,0.12)] text-white">{PROVIDERS.map((p) => <SelectItem key={p.v} value={p.v} className="focus:bg-white/5">{p.l}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <Label className="text-[#94A3B8]">System prompt</Label>
            <Textarea data-testid="agent-prompt-input" value={f.system_prompt} onChange={(e) => set("system_prompt", e.target.value)} rows={4} placeholder="You are an expert researcher. Always cite sources..." className="mt-1.5 resize-none bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white" />
          </div>
          <div>
            <Label className="text-[#94A3B8]">Tools</Label>
            <div className="flex gap-4 mt-2">
              <label className="flex items-center gap-2 text-sm cursor-pointer"><Checkbox data-testid="agent-tool-web" checked={f.tools.includes("web_search")} onCheckedChange={() => toggleTool("web_search")} /> <Globe className="w-4 h-4 text-[#A855F7]" /> Web search</label>
              <label className="flex items-center gap-2 text-sm cursor-pointer"><Checkbox data-testid="agent-tool-memory" checked={f.tools.includes("memory")} onCheckedChange={() => toggleTool("memory")} /> <Brain className="w-4 h-4 text-[#A855F7]" /> Knowledge (RAG)</label>
            </div>
          </div>
          <div>
            <Label className="text-[#94A3B8]">Knowledge (one fact per line)</Label>
            <Textarea data-testid="agent-knowledge-input" value={f.knowledge} onChange={(e) => set("knowledge", e.target.value)} rows={3} placeholder="Our refund policy is 30 days.&#10;Support email is help@acme.com." className="mt-1.5 resize-none bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white" />
          </div>
          <div>
            <Label className="text-[#94A3B8]">Color</Label>
            <div className="flex gap-2 mt-2">{COLORS.map((c) => <button key={c} type="button" onClick={() => set("color", c)} className={`w-7 h-7 rounded-full transition-transform ${f.color === c ? "ring-2 ring-white scale-110" : ""}`} style={{ background: c }} />)}</div>
          </div>
        </div>
        <DialogFooter>
          <Button data-testid="agent-save-btn" onClick={save} disabled={saving} className="rounded-xl ai-gradient-bg text-white border-0 hover:opacity-90">{saving ? <Dots /> : (initial?.id ? "Save changes" : "Create agent")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function OutputBox({ output, sources, steps }) {
  if (!output && !steps) return null;
  return (
    <div className="mt-4 p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
      {steps?.length > 0 && (
        <div className="mb-4 space-y-3">
          {steps.map((s, i) => (
            <div key={i} className="p-3 rounded-xl bg-[#12121C] border border-[rgba(255,255,255,0.06)]">
              <p className="text-xs text-[#A855F7] font-medium mb-1">{s.agent_name} · {s.task}</p>
              <p className="text-sm text-[#CBD5E1] whitespace-pre-wrap">{s.output}</p>
            </div>
          ))}
          <p className="text-xs text-[#64748B] font-medium">Final result</p>
        </div>
      )}
      <pre data-testid="agent-output" className="text-sm text-[#F8FAFC] whitespace-pre-wrap leading-relaxed">{output}</pre>
      {sources?.length > 0 && (
        <div className="mt-4 pt-4 border-t border-[rgba(255,255,255,0.06)]">
          <p className="text-xs text-[#64748B] mb-2">Sources</p>
          {sources.map((s, i) => <a key={i} href={s.url} target="_blank" rel="noreferrer" className="block text-xs text-[#A855F7] hover:underline truncate">[{i + 1}] {s.title}</a>)}
        </div>
      )}
    </div>
  );
}

export default function Agents() {
  const { activeOrg, refreshUsage } = useOutletContext();
  const oid = activeOrg.id;
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [mode, setMode] = useState("single"); // single | team
  const [selected, setSelected] = useState(null); // single agent id
  const [teamIds, setTeamIds] = useState([]);
  const [input, setInput] = useState("");
  const [goal, setGoal] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  const load = async () => { setLoading(true); try { const { data } = await api.get(`/orgs/${oid}/agents`); setAgents(data); } catch { /* ignore */ } finally { setLoading(false); } };
  useEffect(() => { setSelected(null); setTeamIds([]); setResult(null); setHistory([]); load(); }, [oid]); // eslint-disable-line

  const selectedAgent = useMemo(() => agents.find((a) => a.id === selected), [agents, selected]);

  const del = async (id, e) => { e.stopPropagation(); if (!window.confirm("Delete this agent?")) return; await api.delete(`/orgs/${oid}/agents/${id}`); if (selected === id) setSelected(null); setTeamIds((t) => t.filter((x) => x !== id)); load(); };
  const edit = (a, e) => { e.stopPropagation(); setEditing(a); setFormOpen(true); };
  const openNew = () => { setEditing(null); setFormOpen(true); };

  const pickCard = (a) => {
    if (mode === "team") setTeamIds((t) => t.includes(a.id) ? t.filter((x) => x !== a.id) : [...t, a.id]);
    else { setSelected(a.id); setResult(null); setShowHistory(false); }
  };

  const loadHistory = async () => { if (!selected) return; const { data } = await api.get(`/orgs/${oid}/agents/${selected}/runs`); setHistory(data); setShowHistory(true); };

  const runSingle = async () => {
    if (!selected || !input.trim()) return;
    setRunning(true); setResult(null);
    try {
      const { data } = await api.post(`/orgs/${oid}/agents/${selected}/run`, { input: input.trim() });
      setResult({ output: data.output, sources: data.sources, tools_used: data.tools_used });
      refreshUsage();
    } catch (e) { toast.error(e.response?.status === 402 ? "Out of credits — upgrade the org plan." : formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setRunning(false); }
  };

  const runTeam = async () => {
    if (teamIds.length === 0 || !goal.trim()) { toast.error("Pick agents and enter a goal."); return; }
    setRunning(true); setResult(null);
    try {
      const { data } = await api.post(`/orgs/${oid}/agents/team/run`, { goal: goal.trim(), agent_ids: teamIds });
      setResult({ output: data.output, steps: data.steps });
      refreshUsage();
    } catch (e) { toast.error(e.response?.status === 402 ? "Out of credits — upgrade the org plan." : formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setRunning(false); }
  };

  return (
    <div className="px-5 lg:px-8 py-8 max-w-5xl">
      <div className="flex items-start justify-between gap-4 mb-1">
        <h1 className="font-display text-2xl md:text-3xl font-bold">AI Agents</h1>
        <Button data-testid="new-agent-btn" onClick={openNew} className="rounded-xl ai-gradient-bg text-white border-0 hover:opacity-90"><Plus className="w-4 h-4 me-2" /> New Agent</Button>
      </div>
      <p className="text-[#94A3B8] mb-6">Build custom agents with roles, tools & knowledge — or orchestrate a team on one goal.</p>

      <div className="inline-flex rounded-xl bg-[#0C0C14] border border-[rgba(255,255,255,0.08)] p-1 mb-6">
        <button data-testid="mode-single-btn" onClick={() => { setMode("single"); setResult(null); }} className={`px-4 py-1.5 rounded-lg text-sm transition-colors ${mode === "single" ? "ai-gradient-bg text-white" : "text-[#94A3B8] hover:text-white"}`}><Bot className="w-4 h-4 me-1.5 inline" /> Single</button>
        <button data-testid="mode-team-btn" onClick={() => { setMode("team"); setResult(null); }} className={`px-4 py-1.5 rounded-lg text-sm transition-colors ${mode === "team" ? "ai-gradient-bg text-white" : "text-[#94A3B8] hover:text-white"}`}><Users className="w-4 h-4 me-1.5 inline" /> Team</button>
      </div>

      {loading ? <div className="flex justify-center py-10"><Dots /></div> : agents.length === 0 ? (
        <div className="text-center py-14 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
          <span className="w-14 h-14 rounded-2xl ai-gradient-bg inline-flex items-center justify-center mb-4 glow-border"><Bot className="w-6 h-6 text-white" /></span>
          <p className="text-[#94A3B8]">No agents yet. Create your first agent.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          {agents.map((a, i) => {
            const active = mode === "single" ? selected === a.id : teamIds.includes(a.id);
            return (
              <motion.div key={a.id} data-testid={`agent-card-${a.id}`} onClick={() => pickCard(a)} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}
                className={`group p-4 rounded-2xl cursor-pointer transition-colors bg-[#0C0C14] border ${active ? "border-[#A855F7]" : "border-[rgba(255,255,255,0.06)] hover:border-[rgba(255,255,255,0.2)]"}`}>
                <div className="flex items-start justify-between">
                  <span className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: a.color }}><Bot className="w-5 h-5 text-white" /></span>
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button data-testid={`agent-edit-${a.id}`} onClick={(e) => edit(a, e)} className="text-[#64748B] hover:text-white p-1"><Pencil className="w-4 h-4" /></button>
                    <button data-testid={`agent-delete-${a.id}`} onClick={(e) => del(a.id, e)} className="text-[#64748B] hover:text-red-400 p-1"><Trash2 className="w-4 h-4" /></button>
                  </div>
                </div>
                <p className="font-medium text-white mt-3 truncate">{a.name}</p>
                <p className="text-xs text-[#64748B] capitalize">{a.role}</p>
                {a.description && <p className="text-sm text-[#94A3B8] mt-2 line-clamp-2">{a.description}</p>}
                <div className="flex flex-wrap gap-1.5 mt-3">
                  {a.tools.includes("web_search") && <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#12121C] border border-[rgba(255,255,255,0.1)] text-[#94A3B8]"><Globe className="w-3 h-3 me-1 inline" />web</span>}
                  {a.tools.includes("memory") && <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#12121C] border border-[rgba(255,255,255,0.1)] text-[#94A3B8]"><Brain className="w-3 h-3 me-1 inline" />{a.knowledge_count} facts</span>}
                </div>
              </motion.div>
            );
          })}
        </div>
      )}

      {mode === "single" && selectedAgent && (
        <div className="p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
          <div className="flex items-center justify-between mb-3">
            <p className="font-medium text-white flex items-center gap-2"><span className="w-6 h-6 rounded-lg flex items-center justify-center" style={{ background: selectedAgent.color }}><Bot className="w-3.5 h-3.5 text-white" /></span> Run {selectedAgent.name}</p>
            <button data-testid="agent-history-btn" onClick={loadHistory} className="text-xs text-[#94A3B8] hover:text-white flex items-center gap-1"><History className="w-3.5 h-3.5" /> History</button>
          </div>
          <Textarea data-testid="agent-run-input" value={input} onChange={(e) => setInput(e.target.value)} rows={3} placeholder="Ask this agent to do something..." className="resize-none bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white" />
          <Button data-testid="agent-run-btn" onClick={runSingle} disabled={running || !input.trim()} className="mt-3 rounded-full h-11 px-8 ai-gradient-bg text-white border-0 hover:opacity-90">{running ? <Dots /> : <><Play className="w-4 h-4 me-2" /> Run agent</>}</Button>
          {running ? <div className="mt-4 flex justify-center"><Dots /></div> : <OutputBox output={result?.output} sources={result?.sources} />}
          {showHistory && (
            <div className="mt-5 pt-4 border-t border-[rgba(255,255,255,0.06)]">
              <div className="flex items-center justify-between mb-2"><p className="text-sm text-[#94A3B8]">Recent runs</p><button onClick={() => setShowHistory(false)} className="text-[#64748B] hover:text-white"><X className="w-4 h-4" /></button></div>
              {history.length === 0 ? <p className="text-xs text-[#64748B]">No runs yet.</p> : history.map((h) => (
                <div key={h.id} data-testid={`agent-run-history-${h.id}`} className="py-2 border-b border-[rgba(255,255,255,0.04)] last:border-0">
                  <p className="text-xs text-white truncate">{h.input}</p>
                  <p className="text-xs text-[#64748B] mt-0.5 line-clamp-2">{h.output}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {mode === "team" && (
        <div className="p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
          <p className="font-medium text-white mb-1 flex items-center gap-2"><Users className="w-4 h-4 text-[#A855F7]" /> Team run</p>
          <p className="text-xs text-[#64748B] mb-3">{teamIds.length} agent(s) selected. A manager AI will delegate subtasks and synthesize a final result.</p>
          <Textarea data-testid="team-goal-input" value={goal} onChange={(e) => setGoal(e.target.value)} rows={3} placeholder="Describe the overall goal for the team..." className="resize-none bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white" />
          <Button data-testid="team-run-btn" onClick={runTeam} disabled={running || teamIds.length === 0 || !goal.trim()} className="mt-3 rounded-full h-11 px-8 ai-gradient-bg text-white border-0 hover:opacity-90">{running ? <Dots /> : <><Sparkles className="w-4 h-4 me-2" /> Run team</>}</Button>
          {running ? <p className="mt-4 text-sm text-[#64748B] flex items-center gap-2"><Dots /> Coordinating agents…</p> : <OutputBox output={result?.output} steps={result?.steps} />}
        </div>
      )}

      <AgentForm open={formOpen} onOpenChange={setFormOpen} initial={editing ? { ...editing, provider: editing.provider || "auto", model: editing.model || "", knowledge: "" } : null} onSaved={load} oid={oid} />
    </div>
  );
}
