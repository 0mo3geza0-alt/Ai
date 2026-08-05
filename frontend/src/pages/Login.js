import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { useApp, formatApiErrorDetail } from "@/context/AppContext";
import { Logo, LangSwitcher, Dots } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function Login() {
  const { t, login } = useApp();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      nav("/app");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || t.common.error);
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen flex flex-col text-[#F8FAFC]">
      <div className="p-5 flex items-center justify-between">
        <Logo />
        <LangSwitcher />
      </div>
      <div className="flex-1 flex items-center justify-center px-5 py-10">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
          className="w-full max-w-md p-8 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.08)]">
          <h1 className="font-display text-2xl font-bold mb-1">{t.auth.loginTitle}</h1>
          <p className="text-[#94A3B8] text-sm mb-8">{t.auth.loginSub}</p>
          <form onSubmit={submit} className="space-y-5">
            <div className="space-y-2">
              <Label className="text-[#94A3B8]">{t.auth.email}</Label>
              <Input data-testid="login-email-input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" placeholder="you@email.com" />
            </div>
            <div className="space-y-2">
              <Label className="text-[#94A3B8]">{t.auth.password}</Label>
              <Input data-testid="login-password-input" type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" placeholder="••••••••" />
            </div>
            <Button data-testid="login-submit-btn" type="submit" disabled={loading}
              className="w-full rounded-full h-11 ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity">
              {loading ? <Dots /> : t.auth.loginBtn}
            </Button>
          </form>
          <p className="text-sm text-[#94A3B8] mt-6 text-center">
            {t.auth.noAccount} <Link to="/register" data-testid="go-register-link" className="text-[#A855F7] hover:underline">{t.auth.signUp}</Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
