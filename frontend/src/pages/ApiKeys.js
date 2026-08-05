import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { toast } from "sonner";
import { KeyRound, Plus, Trash2, Copy, Check } from "lucide-react";
import { api, formatApiErrorDetail } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function ApiKeys() {
  const { activeOrg } = useOutletContext();
  const oid = activeOrg.id;
  const canManage = ["owner", "admin"].includes(activeOrg.role);
  const [keys, setKeys] = useState([]);
  const [name, setName] = useState("");
  const [newKey, setNewKey] = useState(null);
  const [copied, setCopied] = useState(false);

  const load = async () => {
    try { const { data } = await api.get(`/orgs/${oid}/api-keys`); setKeys(data); } catch { setKeys([]); }
  };
  useEffect(() => { load(); }, [oid]); // eslint-disable-line

  const create = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post(`/orgs/${oid}/api-keys`, { name, scopes: ["project:read", "file:read"] });
      setNewKey(data.key); setName(""); toast.success("API key created"); load();
    } catch (err) { toast.error(formatApiErrorDetail(err.response?.data?.detail)); }
  };
  const revoke = async (id) => {
    try { await api.delete(`/orgs/${oid}/api-keys/${id}`); toast.success("Revoked"); load(); }
    catch (err) { toast.error(formatApiErrorDetail(err.response?.data?.detail)); }
  };
  const copy = () => { navigator.clipboard.writeText(newKey); setCopied(true); setTimeout(() => setCopied(false), 1500); };

  if (!canManage) return <div className="px-5 lg:px-8 py-8 text-[#64748B]">You need admin access to manage API keys.</div>;

  return (
    <div className="px-5 lg:px-8 py-8 max-w-3xl">
      <h1 className="font-display text-2xl md:text-3xl font-bold mb-1">API Keys</h1>
      <p className="text-[#94A3B8] mb-8">Programmatic access for {activeOrg.name}. Scopes: project:read, file:read.</p>

      <form onSubmit={create} className="flex gap-3 mb-6">
        <Input data-testid="apikey-name-input" required placeholder="Key name (e.g. CI pipeline)" value={name} onChange={(e) => setName(e.target.value)}
          className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" />
        <Button data-testid="create-apikey-btn" type="submit" className="rounded-full ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity"><Plus className="w-4 h-4 me-2" /> Create</Button>
      </form>

      {newKey && (
        <div data-testid="new-apikey-banner" className="p-4 rounded-xl bg-[#12121C] border border-[#4F46E5]/40 mb-6">
          <p className="text-xs text-[#94A3B8] mb-2">Copy this key now — it won't be shown again.</p>
          <div className="flex items-center gap-3">
            <code className="flex-1 text-sm text-emerald-400 break-all font-mono">{newKey}</code>
            <button data-testid="copy-apikey-btn" onClick={copy} className="text-[#94A3B8] hover:text-white transition-colors">{copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}</button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {keys.length === 0 ? <p className="text-sm text-[#64748B]">No API keys yet.</p> : keys.map((k) => (
          <div key={k.id} data-testid={`apikey-${k.id}`} className="flex items-center justify-between px-4 py-3 rounded-xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
            <div className="flex items-center gap-3 min-w-0">
              <KeyRound className="w-4 h-4 text-[#D946EF] shrink-0" />
              <div className="min-w-0">
                <p className="text-sm text-white truncate">{k.name} {k.revoked && <span className="text-red-400 text-xs">(revoked)</span>}</p>
                <p className="text-xs text-[#64748B] font-mono">{k.prefix}··· · {k.scopes.join(", ")}</p>
              </div>
            </div>
            {!k.revoked && <button data-testid={`revoke-apikey-${k.id}`} onClick={() => revoke(k.id)} className="text-[#64748B] hover:text-red-400 transition-colors"><Trash2 className="w-4 h-4" /></button>}
          </div>
        ))}
      </div>
    </div>
  );
}
