import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  Save, Loader2, RefreshCw, KeyRound, ShieldCheck, Info, ExternalLink, RotateCcw, CheckCircle2,
} from "lucide-react";
import { api, formatApiErrorDetail } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

const err = (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Something went wrong");

export default function AdminProviders() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newKey, setNewKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/admin/providers/universal-key");
      setData(data);
    } catch (e) { err(e); } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    const key = newKey.trim();
    if (!key) { toast.error("Paste a Universal Key first"); return; }
    setSaving(true);
    try {
      const { data } = await api.put("/admin/providers/universal-key", { api_key: key });
      setData(data);
      setNewKey("");
      toast.success("Universal Key updated — applied instantly, no restart");
    } catch (e) { err(e); } finally { setSaving(false); }
  };

  const reset = async () => {
    setResetting(true);
    try {
      const { data } = await api.post("/admin/providers/universal-key/reset");
      setData(data);
      setNewKey("");
      toast.success("Reverted to the platform default key");
    } catch (e) { err(e); } finally { setResetting(false); }
  };

  if (loading) {
    return (
      <div className="py-10 text-[#64748B] flex items-center gap-2">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading…
      </div>
    );
  }

  const isCustom = data?.source === "custom";

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <div>
          <h2 className="text-white font-semibold text-lg">Emergent Universal Key</h2>
          <p className="text-[#64748B] text-sm">
            The whole platform runs on a single Emergent Universal Key. Replace it any time — changes apply instantly, no restart.
          </p>
        </div>
        <Button onClick={load} variant="outline" data-testid="providers-refresh"
          className="rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10">
          <RefreshCw className="w-4 h-4" /> Refresh
        </Button>
      </div>

      <div data-testid="universal-key-card"
        className="rounded-2xl border border-[#A855F7]/30 bg-gradient-to-br from-[#1a1030] to-[#0C0C14] p-6 max-w-2xl">
        <div className="flex items-center justify-between gap-3 flex-wrap mb-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#A855F7]/15 border border-[#A855F7]/30 flex items-center justify-center">
              <ShieldCheck className="w-5 h-5 text-[#A855F7]" />
            </div>
            <div>
              <div className="text-white font-semibold">Active Key</div>
              <div className="text-xs text-[#94A3B8]">Powers all AI: chat, images, voice & music.</div>
            </div>
          </div>
          <Badge variant="outline"
            data-testid="key-source-badge"
            className={`rounded-full text-[11px] ${isCustom
              ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
              : "bg-white/10 text-[#94A3B8] border-white/15"}`}>
            {isCustom ? "Custom key" : "Platform default"}
          </Badge>
        </div>

        <div className="rounded-xl bg-[#12121C] border border-white/10 px-4 py-3 mb-5 flex items-center gap-3">
          <KeyRound className="w-4 h-4 text-[#A855F7] shrink-0" />
          <code data-testid="key-masked" className="text-sm text-white font-mono truncate">
            {data?.key_masked || "— no key set —"}
          </code>
          {data?.has_key && <CheckCircle2 className="w-4 h-4 text-emerald-400 ml-auto shrink-0" />}
        </div>

        <div className="mb-2">
          <Label className="text-[#94A3B8] text-xs">Replace with another Universal Key</Label>
          <Input type="password" autoComplete="new-password" value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            placeholder="sk-emergent-…"
            data-testid="universal-key-input"
            className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white mt-1 font-mono" />
        </div>

        <div className="text-[11px] text-amber-300/90 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2 mb-5 flex items-start gap-2">
          <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span>Paste a full Emergent Universal Key. It is stored encrypted and applied to every new request immediately.</span>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <Button onClick={save} disabled={saving || !newKey.trim()} data-testid="universal-key-save"
            className="rounded-full ai-gradient-bg text-white border-0">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Save Key
          </Button>
          {isCustom && (
            <Button onClick={reset} disabled={resetting} variant="outline" data-testid="universal-key-reset"
              className="rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10">
              {resetting ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />} Reset to default
            </Button>
          )}
          {data?.dashboard_url && (
            <a href={data.dashboard_url} target="_blank" rel="noreferrer" data-testid="emergent-dashboard-link" className="ml-auto">
              <Button variant="outline" className="rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10">
                <ExternalLink className="w-4 h-4" /> Emergent Dashboard
              </Button>
            </a>
          )}
        </div>

        {data?.updated_at && (
          <div className="text-[11px] text-[#64748B] mt-4">
            Last updated: {new Date(data.updated_at).toLocaleString()}
          </div>
        )}
      </div>
    </motion.div>
  );
}
