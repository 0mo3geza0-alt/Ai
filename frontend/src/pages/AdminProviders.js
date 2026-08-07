import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  Zap, CheckCircle2, XCircle, Save, Loader2, Activity, DollarSign, Gauge,
  ListChecks, KeyRound, RefreshCw, Plug, Timer, Coins,
} from "lucide-react";
import { api, formatApiErrorDetail } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const err = (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Something went wrong");

const STATUS = {
  active: { label: "Active", cls: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" },
  connected: { label: "Connected", cls: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" },
  error: { label: "Error", cls: "bg-red-500/15 text-red-400 border-red-500/30" },
  failed: { label: "Failed", cls: "bg-red-500/15 text-red-400 border-red-500/30" },
  untested: { label: "Untested", cls: "bg-white/10 text-[#94A3B8] border-white/15" },
};

function StatusBadge({ status }) {
  const s = STATUS[status] || STATUS.untested;
  return <Badge variant="outline" className={`rounded-full text-[11px] ${s.cls}`}>{s.label}</Badge>;
}

const money = (n) => (n == null ? "—" : `$${Number(n).toLocaleString(undefined, { maximumFractionDigits: 4 })}`);

function StatCard({ icon: Icon, label, value, tint }) {
  return (
    <div className="rounded-xl bg-[#12121C] border border-[rgba(255,255,255,0.08)] p-4">
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center mb-3 ${tint}`}>
        <Icon className="w-4 h-4" />
      </div>
      <div className="text-xl font-bold text-white">{value}</div>
      <div className="text-xs text-[#64748B] mt-0.5">{label}</div>
    </div>
  );
}

function ProviderCard({ p, onSaved }) {
  const [draft, setDraft] = useState({
    name: p.name, model: p.model, base_url: p.base_url,
    priority: p.priority, monthly_budget: p.monthly_budget,
    price_in: p.price_in, price_out: p.price_out, api_key: "",
  });
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testRes, setTestRes] = useState(null);
  const [enabled, setEnabled] = useState(p.enabled);
  const set = (k, v) => setDraft((d) => ({ ...d, [k]: v }));

  const save = async (extra = {}) => {
    setSaving(true);
    try {
      const body = { ...draft, ...extra };
      if (!body.api_key) delete body.api_key; // don't touch key unless a new one is typed
      const { data } = await api.put(`/admin/providers/${p.id}`, body);
      toast.success(`${data.name} saved`);
      setDraft((d) => ({ ...d, api_key: "" }));
      onSaved && onSaved();
    } catch (e) { err(e); } finally { setSaving(false); }
  };

  const toggle = async (v) => {
    setEnabled(v);
    try { await api.put(`/admin/providers/${p.id}`, { enabled: v }); toast.success(v ? "Enabled" : "Disabled"); onSaved && onSaved(); }
    catch (e) { setEnabled(!v); err(e); }
  };

  const test = async () => {
    setTesting(true); setTestRes(null);
    try {
      // Save any pending edits first so we test what's on screen.
      const body = { ...draft }; if (!body.api_key) delete body.api_key;
      await api.put(`/admin/providers/${p.id}`, body);
      const { data } = await api.post(`/admin/providers/${p.id}/test`);
      setTestRes(data);
      data.connected ? toast.success(`Connected (${data.latency_ms}ms)`) : toast.error("Connection failed");
      setDraft((d) => ({ ...d, api_key: "" }));
      onSaved && onSaved();
    } catch (e) { err(e); } finally { setTesting(false); }
  };

  return (
    <div data-testid={`provider-card-${p.slug}`} className="rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.08)] p-5">
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center">
            <Plug className="w-4 h-4 text-[#A855F7]" />
          </div>
          <div>
            <div className="text-white font-semibold flex items-center gap-2">
              {p.name} <span className="text-[10px] uppercase tracking-wide text-[#64748B]">{p.slug}</span>
            </div>
            <div className="text-xs text-[#64748B]">{p.has_key ? `Key: ${p.key_masked}` : (p.key_optional ? "No key required" : "No key set")}</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={p.status} />
          <div className="flex items-center gap-2">
            <span className="text-xs text-[#94A3B8]">{enabled ? "On" : "Off"}</span>
            <Switch checked={enabled} onCheckedChange={toggle} data-testid={`provider-toggle-${p.slug}`} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="md:col-span-2">
          <Label className="text-[#94A3B8] text-xs">API Key {p.has_key && <span className="text-[#64748B]">(leave blank to keep current)</span>}</Label>
          <Input type="password" autoComplete="new-password" value={draft.api_key}
            onChange={(e) => set("api_key", e.target.value)}
            placeholder={p.has_key ? p.key_masked : (p.key_optional ? "Optional" : "Paste new API key")}
            data-testid={`provider-key-${p.slug}`}
            className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white mt-1" />
        </div>
        <div>
          <Label className="text-[#94A3B8] text-xs">Model</Label>
          <Input value={draft.model} onChange={(e) => set("model", e.target.value)}
            className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white mt-1" />
        </div>
        <div>
          <Label className="text-[#94A3B8] text-xs">Base URL</Label>
          <Input value={draft.base_url} onChange={(e) => set("base_url", e.target.value)}
            className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white mt-1" />
        </div>
        <div>
          <Label className="text-[#94A3B8] text-xs">Priority (1 = first)</Label>
          <Input type="number" value={draft.priority} onChange={(e) => set("priority", e.target.value)}
            className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white mt-1" />
        </div>
        <div>
          <Label className="text-[#94A3B8] text-xs">Monthly Budget (USD, 0 = unlimited)</Label>
          <Input type="number" step="0.01" value={draft.monthly_budget} onChange={(e) => set("monthly_budget", e.target.value)}
            className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white mt-1" />
        </div>
        <div>
          <Label className="text-[#94A3B8] text-xs">Price / 1M input tokens (USD)</Label>
          <Input type="number" step="0.001" value={draft.price_in} onChange={(e) => set("price_in", e.target.value)}
            className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white mt-1" />
        </div>
        <div>
          <Label className="text-[#94A3B8] text-xs">Price / 1M output tokens (USD)</Label>
          <Input type="number" step="0.001" value={draft.price_out} onChange={(e) => set("price_out", e.target.value)}
            className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white mt-1" />
        </div>
      </div>

      {testRes && (
        <div className={`mt-3 text-xs rounded-lg px-3 py-2 border ${testRes.connected ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300" : "bg-red-500/10 border-red-500/30 text-red-300"}`}>
          {testRes.connected
            ? `✓ Connected in ${testRes.latency_ms}ms · model ${testRes.model}${testRes.sample ? ` · "${testRes.sample}"` : ""}`
            : `✗ ${testRes.error || "Failed"}`}
        </div>
      )}

      <div className="flex items-center gap-3 mt-4">
        <Button onClick={test} disabled={testing} variant="outline" data-testid={`provider-test-${p.slug}`}
          className="rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10">
          {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />} Test Connection
        </Button>
        <Button onClick={() => save()} disabled={saving} data-testid={`provider-save-${p.slug}`}
          className="rounded-full ai-gradient-bg text-white border-0">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Save
        </Button>
      </div>
    </div>
  );
}

export default function AdminProviders() {
  const [providers, setProviders] = useState([]);
  const [usage, setUsage] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const [pr, us, lg] = await Promise.all([
        api.get("/admin/providers"),
        api.get("/admin/providers/usage"),
        api.get("/admin/providers/logs?limit=60"),
      ]);
      setProviders(pr.data); setUsage(us.data); setLogs(lg.data);
    } catch (e) { err(e); } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  if (loading) return <div className="py-10 text-[#64748B] flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Loading providers…</div>;

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <div>
          <h2 className="text-white font-semibold text-lg">AI Providers</h2>
          <p className="text-[#64748B] text-sm">Manage LLM provider keys — changes apply instantly, no restart. On failure the platform auto-falls back down the priority list (last resort: built-in Emergent key).</p>
        </div>
        <Button onClick={load} variant="outline" data-testid="providers-refresh"
          className="rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10">
          <RefreshCw className="w-4 h-4" /> Refresh
        </Button>
      </div>

      {usage && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard icon={Activity} label="Requests today" value={usage.today_requests} tint="bg-sky-500/15 text-sky-400" />
          <StatCard icon={ListChecks} label="Requests this month" value={usage.month_requests} tint="bg-indigo-500/15 text-indigo-400" />
          <StatCard icon={DollarSign} label="Est. cost (month)" value={money(usage.estimated_cost_month)} tint="bg-emerald-500/15 text-emerald-400" />
          <StatCard icon={Coins} label="Est. cost (today)" value={money(usage.estimated_cost_today)} tint="bg-amber-500/15 text-amber-400" />
          <StatCard icon={Timer} label="Avg response" value={`${usage.avg_response_ms}ms`} tint="bg-fuchsia-500/15 text-fuchsia-400" />
          <StatCard icon={Gauge} label="Success rate" value={`${usage.success_rate}%`} tint="bg-teal-500/15 text-teal-400" />
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {providers.map((p) => <ProviderCard key={p.id} p={p} onSaved={load} />)}
      </div>

      <div className="mt-10">
        <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><KeyRound className="w-4 h-4 text-[#A855F7]" /> Request Logs</h3>
        <div className="rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.08)] overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="border-white/10 hover:bg-transparent">
                <TableHead className="text-[#64748B]">Time</TableHead>
                <TableHead className="text-[#64748B]">Provider</TableHead>
                <TableHead className="text-[#64748B]">Model</TableHead>
                <TableHead className="text-[#64748B]">Type</TableHead>
                <TableHead className="text-[#64748B]">Status</TableHead>
                <TableHead className="text-[#64748B]">Latency</TableHead>
                <TableHead className="text-[#64748B]">Tokens</TableHead>
                <TableHead className="text-[#64748B]">Cost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.length === 0 && (
                <TableRow className="border-white/10 hover:bg-transparent">
                  <TableCell colSpan={8} className="text-center text-[#64748B] py-8">No requests yet.</TableCell>
                </TableRow>
              )}
              {logs.map((l) => (
                <TableRow key={l.id} className="border-white/10 hover:bg-white/[0.02]">
                  <TableCell className="text-[#94A3B8] text-xs">{l.ts ? new Date(l.ts).toLocaleString() : "—"}</TableCell>
                  <TableCell className="text-white text-xs">{l.provider_name}</TableCell>
                  <TableCell className="text-[#94A3B8] text-xs">{l.model}</TableCell>
                  <TableCell className="text-[#94A3B8] text-xs">{l.request_type}</TableCell>
                  <TableCell>
                    {l.success
                      ? <span className="text-emerald-400 text-xs flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> OK</span>
                      : <span className="text-red-400 text-xs flex items-center gap-1" title={l.error}><XCircle className="w-3 h-3" /> Fail</span>}
                  </TableCell>
                  <TableCell className="text-[#94A3B8] text-xs">{l.latency_ms}ms</TableCell>
                  <TableCell className="text-[#94A3B8] text-xs">{l.total_tokens}{l.estimated ? "~" : ""}</TableCell>
                  <TableCell className="text-[#94A3B8] text-xs">{money(l.cost)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </motion.div>
  );
}
