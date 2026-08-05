import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { api } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/shared";

export default function PaymentSuccess() {
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const [state, setState] = useState("checking"); // checking | paid | timeout

  useEffect(() => {
    if (!sessionId) { setState("timeout"); return; }
    let tries = 0, alive = true;
    const poll = async () => {
      while (alive && tries < 20) {
        try {
          const { data } = await api.get(`/billing/status/${sessionId}`);
          if (data.payment_status === "paid") { setState("paid"); return; }
        } catch { /* keep trying */ }
        tries++;
        await new Promise((r) => setTimeout(r, 2000));
      }
      if (alive) setState("timeout");
    };
    poll();
    return () => { alive = false; };
  }, [sessionId]);

  return (
    <div className="min-h-screen flex items-center justify-center px-5 text-[#F8FAFC]">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md p-8 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.08)] text-center" data-testid="payment-success-card">
        <div className="mb-6 flex justify-center"><Logo /></div>
        {state === "checking" && (<><Loader2 className="w-12 h-12 mx-auto mb-4 text-[#A855F7] animate-spin" /><h1 className="text-xl font-bold mb-2">Confirming your payment…</h1><p className="text-[#94A3B8] text-sm">Please wait a moment.</p></>)}
        {state === "paid" && (<><CheckCircle2 className="w-12 h-12 mx-auto mb-4 text-emerald-400" /><h1 className="text-xl font-bold mb-2" data-testid="payment-paid-title">Payment successful 🎉</h1><p className="text-[#94A3B8] text-sm mb-6">Your plan is upgraded and credits added.</p><Link to="/app/billing"><Button data-testid="back-to-app-btn" className="rounded-full ai-gradient-bg text-white border-0">Back to dashboard</Button></Link></>)}
        {state === "timeout" && (<><XCircle className="w-12 h-12 mx-auto mb-4 text-amber-400" /><h1 className="text-xl font-bold mb-2">Still processing</h1><p className="text-[#94A3B8] text-sm mb-6">Your payment is taking longer than expected. It will update shortly.</p><Link to="/app/billing"><Button className="rounded-full bg-white/10 text-white border border-[rgba(255,255,255,0.12)]">Back to billing</Button></Link></>)}
      </motion.div>
    </div>
  );
}
