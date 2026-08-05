import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/shared";

export default function PaymentCancel() {
  return (
    <div className="min-h-screen flex items-center justify-center px-5 text-[#F8FAFC]">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md p-8 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.08)] text-center" data-testid="payment-cancel-card">
        <div className="mb-6 flex justify-center"><Logo /></div>
        <XCircle className="w-12 h-12 mx-auto mb-4 text-[#64748B]" />
        <h1 className="text-xl font-bold mb-2">Checkout cancelled</h1>
        <p className="text-[#94A3B8] text-sm mb-6">No charge was made. You can pick a plan whenever you're ready.</p>
        <Link to="/app/billing"><Button data-testid="cancel-back-btn" className="rounded-full ai-gradient-bg text-white border-0">Back to plans</Button></Link>
      </motion.div>
    </div>
  );
}
