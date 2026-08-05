import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Check, Sparkles, Zap, Crown } from "lucide-react";
import { api, formatApiErrorDetail } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";

const PLAN_ICONS = { free: Sparkles, pro: Zap, business: Crown };

export default function Billing() {
  const { activeOrg, refreshUsage, usage } = useOutletContext();
  const oid = activeOrg.id;
  const [plans, setPlans] = useState([]);
  const [cycle, setCycle] = useState("monthly");
  const [loadingKey, setLoadingKey] = useState(null);
  const currentPlan = usage?.plan || "free";

  useEffect(() => { api.get("/billing/plans").then(({ data }) => setPlans(data.plans)).catch(() => {}); }, []);
  useEffect(() => { refreshUsage(); }, []); // eslint-disable-line

  const subscribe = async (plan) => {
    const lookup = cycle === "monthly" ? plan.monthly_lookup : plan.yearly_lookup;
    if (!lookup) return;
    setLoadingKey(plan.id);
    try {
      const { data } = await api.post(`/billing/orgs/${oid}/checkout`, { lookup_key: lookup, origin_url: window.location.origin });
      window.location.href = data.checkout_url;
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Could not start checkout");
      setLoadingKey(null);
    }
  };

  return (
    <div className="px-5 lg:px-8 py-8 max-w-5xl">
      <h1 className="font-display text-2xl md:text-3xl font-bold mb-1">Billing & Plans</h1>
      <p className="text-[#94A3B8] mb-6">You are on the <span className="capitalize text-white font-medium">{currentPlan}</span> plan · <span className="text-white font-medium">{usage?.credits ?? "…"}</span> credits left.</p>

      <div className="inline-flex items-center gap-1 p-1 rounded-full bg-[#12121C] border border-[rgba(255,255,255,0.08)] mb-8">
        {["monthly", "yearly"].map((c) => (
          <button key={c} data-testid={`billing-cycle-${c}`} onClick={() => setCycle(c)}
            className={`px-4 py-1.5 rounded-full text-sm capitalize transition-colors ${cycle === c ? "ai-gradient-bg text-white" : "text-[#94A3B8] hover:text-white"}`}>
            {c}{c === "yearly" && <span className="ms-1 text-xs opacity-80">-20%</span>}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {plans.map((p, i) => {
          const Icon = PLAN_ICONS[p.id] || Sparkles;
          const price = cycle === "monthly" ? p.monthly : p.yearly;
          const isCurrent = currentPlan === p.id;
          const isFree = p.id === "free";
          return (
            <motion.div key={p.id} data-testid={`plan-card-${p.id}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: i * 0.06 }}
              className={`relative p-6 rounded-2xl border flex flex-col ${p.highlight ? "border-[#A855F7] bg-[#12101C]" : "border-[rgba(255,255,255,0.08)] bg-[#0C0C14]"}`}>
              {p.highlight && <span className="absolute -top-3 left-6 px-3 py-1 rounded-full text-xs ai-gradient-bg text-white">Most popular</span>}
              <div className="flex items-center gap-2 mb-3"><Icon className="w-5 h-5 text-[#A855F7]" /><h3 className="font-display text-lg font-bold">{p.name}</h3></div>
              <div className="mb-4"><span className="text-3xl font-bold">${price}</span><span className="text-[#64748B] text-sm">{isFree ? "" : cycle === "monthly" ? "/mo" : "/yr"}</span></div>
              <ul className="space-y-2 mb-6 flex-1">
                {p.features.map((f, j) => <li key={j} className="flex items-start gap-2 text-sm text-[#94A3B8]"><Check className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" /> {f}</li>)}
              </ul>
              {isCurrent ? (
                <Button data-testid={`plan-current-${p.id}`} disabled className="w-full rounded-full bg-white/5 text-[#94A3B8] border border-[rgba(255,255,255,0.12)]">Current plan</Button>
              ) : isFree ? (
                <Button data-testid={`plan-free-${p.id}`} disabled className="w-full rounded-full bg-white/5 text-[#64748B]">Free</Button>
              ) : (
                <Button data-testid={`plan-subscribe-${p.id}`} onClick={() => subscribe(p)} disabled={loadingKey === p.id}
                  className={`w-full rounded-full ${p.highlight ? "ai-gradient-bg text-white border-0" : "bg-white/10 text-white border border-[rgba(255,255,255,0.12)]"} hover:opacity-90 transition-opacity`}>
                  {loadingKey === p.id ? "Redirecting…" : `Upgrade to ${p.name}`}
                </Button>
              )}
            </motion.div>
          );
        })}
      </div>
      <p className="text-xs text-[#64748B] mt-6">Test mode · use card 4242 4242 4242 4242, any future expiry & CVC. Taxes handled at checkout.</p>
    </div>
  );
}
