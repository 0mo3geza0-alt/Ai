import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { useAuth, formatApiErrorDetail } from "@/context/AuthContext";
import { Logo, Dots } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
function googleLogin() {
  const redirectUrl = window.location.origin + "/app";
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
}

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try { await login(email, password); nav("/app"); }
    catch (err) { toast.error(formatApiErrorDetail(err.response?.data?.detail)); }
    finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen flex flex-col text-[#F8FAFC]">
      <div className="p-5"><Logo /></div>
      <div className="flex-1 flex items-center justify-center px-5 py-10">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
          className="w-full max-w-md p-8 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.08)]">
          <h1 className="font-display text-2xl font-bold mb-1">Welcome back</h1>
          <p className="text-[#94A3B8] text-sm mb-8">Log in to your workspace</p>
          <Button data-testid="google-login-btn" onClick={googleLogin} variant="outline"
            className="w-full rounded-full h-11 mb-5 bg-white text-[#0C0C14] border-0 hover:bg-white/90 transition-colors font-medium">
            Continue with Google
          </Button>
          <div className="flex items-center gap-3 mb-5 text-xs text-[#64748B]">
            <span className="flex-1 h-px bg-[rgba(255,255,255,0.08)]" /> or <span className="flex-1 h-px bg-[rgba(255,255,255,0.08)]" />
          </div>
          <form onSubmit={submit} className="space-y-5">
            <div className="space-y-2">
              <Label className="text-[#94A3B8]">Email</Label>
              <Input data-testid="login-email-input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" placeholder="you@email.com" />
            </div>
            <div className="space-y-2">
              <Label className="text-[#94A3B8]">Password</Label>
              <Input data-testid="login-password-input" type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" placeholder="••••••••" />
            </div>
            <Button data-testid="login-submit-btn" type="submit" disabled={loading}
              className="w-full rounded-full h-11 ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity">
              {loading ? <Dots /> : "Log in"}
            </Button>
          </form>
          <p className="text-sm text-[#94A3B8] mt-6 text-center">
            Don't have an account? <Link to="/register" data-testid="go-register-link" className="text-[#A855F7] hover:underline">Sign up</Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
