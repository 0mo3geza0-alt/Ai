import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ShieldAlert, Activity, Ban, AlertTriangle, RefreshCw } from "lucide-react";
import { api } from "@/context/AuthContext";
import { Dots } from "@/components/shared";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const METHOD_COLORS = { GET: "#64748B", POST: "#10B981", PATCH: "#F59E0B", PUT: "#F59E0B", DELETE: "#EF4444" };

export default function Security() {
  const [overview, setOverview] = useState(null);
  const [logs, setLogs] = useState([]);
  const [filter, setFilter] = useState("all"); // all | blocked | errors
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(false);

  const load = async () => {
    setLoading(true);
    const params = {};
    if (filter === "blocked") params.blocked = true;
    try {
      const [ov, lg] = await Promise.all([
        api.get("/admin/security/overview").then((r) => r.data),
        api.get("/admin/audit-logs", { params: { limit: 200, ...params } }).then((r) => r.data),
      ]);
      setOverview(ov);
      setLogs(filter === "errors" ? lg.filter((l) => l.status >= 400) : lg);
    } catch { setErr(true); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [filter]); // eslint-disable-line

  if (err) return <div className="px-5 lg:px-8 py-8 text-[#64748B]">Admin access required.</div>;

  const cards = overview ? [
    { label: "Total events", value: overview.total_events, icon: Activity },
    { label: "Blocked", value: overview.blocked_events, icon: Ban },
    { label: "Errors (4xx/5xx)", value: overview.error_events, icon: AlertTriangle },
    { label: "Write ops", value: Object.values(overview.by_method || {}).reduce((a, b) => a + b, 0), icon: ShieldAlert },
  ] : [];

  return (
    <div className="px-5 lg:px-8 py-8 max-w-5xl">
      <div className="flex items-start justify-between gap-4 mb-1">
        <h1 className="font-display text-2xl md:text-3xl font-bold">Security & Audit</h1>
        <button data-testid="security-refresh-btn" onClick={load} className="text-sm text-[#94A3B8] hover:text-white flex items-center gap-1.5"><RefreshCw className="w-4 h-4" /> Refresh</button>
      </div>
      <p className="text-[#94A3B8] mb-8">Platform-wide audit trail, rate-limit policy and blocked requests.</p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {cards.map((c, i) => (
          <motion.div key={i} data-testid={`security-stat-${c.label.toLowerCase().replace(/[^a-z]+/g, "-").replace(/^-|-$/g, "")}`} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: i * 0.03 }}
            className="p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
            <c.icon className="w-5 h-5 mb-3 text-[#A855F7]" />
            <p className="font-display text-2xl font-bold">{c.value}</p>
            <p className="text-[#64748B] text-sm mt-1">{c.label}</p>
          </motion.div>
        ))}
      </div>

      {overview?.rate_limit && (
        <div className="p-4 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] mb-8 text-sm text-[#94A3B8]">
          <span className="text-white font-medium">Rate limit:</span> {overview.rate_limit.limit} requests / {overview.rate_limit.window_seconds}s on {overview.rate_limit.scope}.
        </div>
      )}

      <div className="flex items-center justify-between mb-4">
        <h2 className="font-display text-lg font-semibold">Audit log</h2>
        <Select value={filter} onValueChange={setFilter}>
          <SelectTrigger data-testid="security-filter-select" className="w-40 bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white"><SelectValue /></SelectTrigger>
          <SelectContent className="bg-[#12121C] border-[rgba(255,255,255,0.12)] text-white">
            <SelectItem value="all" className="focus:bg-white/5">All events</SelectItem>
            <SelectItem value="blocked" className="focus:bg-white/5">Blocked only</SelectItem>
            <SelectItem value="errors" className="focus:bg-white/5">Errors only</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {loading ? <div className="flex justify-center py-10"><Dots /></div> : logs.length === 0 ? (
        <div className="text-center py-14 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]"><p className="text-[#94A3B8]">No events recorded.</p></div>
      ) : (
        <div className="rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] overflow-hidden">
          {logs.map((l) => (
            <div key={l.id} data-testid={`audit-log-${l.id}`} className={`flex items-center gap-3 px-4 py-2.5 border-b border-[rgba(255,255,255,0.04)] last:border-0 text-sm ${l.blocked ? "bg-red-500/5" : ""}`}>
              <span className="font-mono text-xs w-14 shrink-0" style={{ color: METHOD_COLORS[l.method] || "#64748B" }}>{l.method}</span>
              <span className="font-mono text-xs text-[#CBD5E1] truncate flex-1 min-w-0">{l.path}</span>
              {l.blocked && <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/20 text-red-300 border border-red-500/40 shrink-0">blocked</span>}
              <span className={`text-xs shrink-0 ${l.status >= 400 ? "text-red-400" : "text-emerald-400"}`}>{l.status}</span>
              <span className="text-xs text-[#64748B] truncate w-40 shrink-0 hidden md:block">{l.user_email || l.client || "—"}</span>
              <span className="text-xs text-[#64748B] shrink-0 hidden lg:block">{l.created_at ? new Date(l.created_at).toLocaleTimeString() : ""}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
