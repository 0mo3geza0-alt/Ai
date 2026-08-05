import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Brain, Plus, Search, Trash2, Tag } from "lucide-react";
import { api, formatApiErrorDetail } from "@/context/AuthContext";
import { Dots } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";

function AddMemory({ open, onOpenChange, onSaved, oid }) {
  const [text, setText] = useState("");
  const [tags, setTags] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (open) { setText(""); setTags(""); } }, [open]);

  const save = async () => {
    if (!text.trim()) { toast.error("Enter some knowledge text."); return; }
    setSaving(true);
    try {
      await api.post(`/orgs/${oid}/memories`, { text: text.trim(), tags: tags.split(",").map((t) => t.trim()).filter(Boolean), source: "manual" });
      toast.success("Knowledge added"); onSaved(); onOpenChange(false);
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#0C0C14] border-[rgba(255,255,255,0.1)] text-white max-w-lg">
        <DialogHeader><DialogTitle className="font-display">Add knowledge</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div>
            <Label className="text-[#94A3B8]">Text</Label>
            <Textarea data-testid="memory-text-input" value={text} onChange={(e) => setText(e.target.value)} rows={5} placeholder="Paste a fact, policy, doc snippet or note..." className="mt-1.5 resize-none bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white" />
          </div>
          <div>
            <Label className="text-[#94A3B8]">Tags (comma separated)</Label>
            <Input data-testid="memory-tags-input" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="policy, support" className="mt-1.5 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white" />
          </div>
        </div>
        <DialogFooter>
          <Button data-testid="memory-save-btn" onClick={save} disabled={saving} className="rounded-xl ai-gradient-bg text-white border-0 hover:opacity-90">{saving ? <Dots /> : "Add to knowledge base"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function Memory() {
  const { activeOrg } = useOutletContext();
  const oid = activeOrg.id;
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);

  const load = async () => { setLoading(true); try { const { data } = await api.get(`/orgs/${oid}/memories`); setItems(data); } catch { /* ignore */ } finally { setLoading(false); } };
  useEffect(() => { setResults(null); setQuery(""); load(); }, [oid]); // eslint-disable-line

  const del = async (id) => { if (!window.confirm("Delete this knowledge item?")) return; await api.delete(`/orgs/${oid}/memories/${id}`); load(); if (results) setResults((r) => r.filter((x) => x.id !== id)); };

  const search = async () => {
    if (!query.trim()) { setResults(null); return; }
    setSearching(true);
    try { const { data } = await api.post(`/orgs/${oid}/memories/search`, { query: query.trim(), limit: 8 }); setResults(data.results); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSearching(false); }
  };

  const list = results ?? items;

  return (
    <div className="px-5 lg:px-8 py-8 max-w-4xl">
      <div className="flex items-start justify-between gap-4 mb-1">
        <h1 className="font-display text-2xl md:text-3xl font-bold">Knowledge Base</h1>
        <Button data-testid="add-memory-btn" onClick={() => setAddOpen(true)} className="rounded-xl ai-gradient-bg text-white border-0 hover:opacity-90"><Plus className="w-4 h-4 me-2" /> Add</Button>
      </div>
      <p className="text-[#94A3B8] mb-6">Semantic memory (vector search) your agents can recall via the Knowledge tool.</p>

      <div className="flex items-center gap-3 mb-6">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-[#64748B] absolute start-3 top-1/2 -translate-y-1/2" />
          <Input data-testid="memory-search-input" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") search(); }} placeholder="Semantic search across your knowledge..." className="ps-9 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white" />
        </div>
        <Button data-testid="memory-search-btn" onClick={search} disabled={searching} className="rounded-xl bg-[#12121C] border border-[rgba(255,255,255,0.1)] text-white hover:bg-white/5">{searching ? <Dots /> : "Search"}</Button>
        {results && <button data-testid="memory-clear-search" onClick={() => { setResults(null); setQuery(""); }} className="text-sm text-[#94A3B8] hover:text-white">Clear</button>}
      </div>

      {results && <p className="text-sm text-[#64748B] mb-3">{results.length} match(es) by semantic relevance</p>}

      {loading ? <div className="flex justify-center py-10"><Dots /></div> : list.length === 0 ? (
        <div className="text-center py-14 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
          <span className="w-14 h-14 rounded-2xl ai-gradient-bg inline-flex items-center justify-center mb-4 glow-border"><Brain className="w-6 h-6 text-white" /></span>
          <p className="text-[#94A3B8]">{results ? "No matches found." : "No knowledge yet. Add your first item."}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {list.map((m, i) => (
            <motion.div key={m.id} data-testid={`memory-item-${m.id}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.02 }}
              className="group p-4 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm text-[#F8FAFC] whitespace-pre-wrap">{m.text}</p>
                <div className="flex flex-wrap items-center gap-2 mt-2">
                  {(m.tags || []).map((t) => <span key={t} className="text-[10px] px-2 py-0.5 rounded-full bg-[#12121C] border border-[rgba(255,255,255,0.1)] text-[#94A3B8]"><Tag className="w-2.5 h-2.5 me-1 inline" />{t}</span>)}
                  {m.agent_id && <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#12121C] border border-[rgba(255,255,255,0.1)] text-[#94A3B8]">agent knowledge</span>}
                  {typeof m.score === "number" && <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#A855F7]/20 border border-[#A855F7]/40 text-[#D8B4FE]">score {m.score}</span>}
                </div>
              </div>
              <button data-testid={`memory-delete-${m.id}`} onClick={() => del(m.id)} className="opacity-0 group-hover:opacity-100 text-[#64748B] hover:text-red-400 transition-opacity shrink-0"><Trash2 className="w-4 h-4" /></button>
            </motion.div>
          ))}
        </div>
      )}

      <AddMemory open={addOpen} onOpenChange={setAddOpen} onSaved={load} oid={oid} />
    </div>
  );
}
