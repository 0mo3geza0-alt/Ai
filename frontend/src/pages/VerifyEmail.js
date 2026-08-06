import { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useLocation, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { useAuth, formatApiErrorDetail } from "@/context/AuthContext";
import { Logo, Dots } from "@/components/shared";
import { Button } from "@/components/ui/button";

export default function VerifyEmail() {
  const { verifyEmail, resendCode } = useAuth();
  const nav = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const email = location.state?.email || params.get("email") || "";

  const [digits, setDigits] = useState(["", "", "", "", "", ""]);
  const [loading, setLoading] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const inputsRef = useRef([]);

  useEffect(() => {
    if (!email) nav("/register", { replace: true });
  }, [email, nav]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  const code = digits.join("");

  const handleChange = (i, val) => {
    const v = val.replace(/\D/g, "");
    if (!v) {
      setDigits((d) => d.map((x, idx) => (idx === i ? "" : x)));
      return;
    }
    // support pasting the full code into one field
    if (v.length > 1) {
      const chars = v.slice(0, 6).split("");
      const next = ["", "", "", "", "", ""];
      chars.forEach((c, idx) => (next[idx] = c));
      setDigits(next);
      const last = Math.min(chars.length, 6) - 1;
      inputsRef.current[last]?.focus();
      return;
    }
    setDigits((d) => d.map((x, idx) => (idx === i ? v : x)));
    if (i < 5) inputsRef.current[i + 1]?.focus();
  };

  const handleKeyDown = (i, e) => {
    if (e.key === "Backspace" && !digits[i] && i > 0) {
      inputsRef.current[i - 1]?.focus();
    }
  };

  const submit = async (e) => {
    e?.preventDefault();
    if (code.length !== 6) {
      toast.error("يرجى إدخال الكود المكوّن من 6 أرقام");
      return;
    }
    setLoading(true);
    try {
      await verifyEmail(email, code);
      toast.success("تم تفعيل حسابك بنجاح! أهلاً بك في VibeVerse");
      nav("/app");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
      setDigits(["", "", "", "", "", ""]);
      inputsRef.current[0]?.focus();
    } finally {
      setLoading(false);
    }
  };

  const resend = async () => {
    if (cooldown > 0) return;
    try {
      const data = await resendCode(email);
      toast.success(data?.message || "تم إرسال كود جديد");
      setCooldown(60);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
      const m = String(err.response?.data?.detail || "").match(/(\d+)/);
      if (m) setCooldown(parseInt(m[1], 10));
    }
  };

  return (
    <div className="min-h-screen flex flex-col text-[#F8FAFC]" dir="rtl">
      <div className="p-5"><Logo /></div>
      <div className="flex-1 flex items-center justify-center px-5 py-10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md p-8 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.08)] text-center"
        >
          <div className="mx-auto mb-5 w-14 h-14 rounded-2xl ai-gradient-bg flex items-center justify-center text-2xl">
            ✉️
          </div>
          <h1 className="font-display text-2xl font-bold mb-2">فعّل بريدك الإلكتروني</h1>
          <p className="text-[#94A3B8] text-sm mb-1">
            أرسلنا كوداً مكوّناً من 6 أرقام إلى
          </p>
          <p className="text-[#A855F7] text-sm font-medium mb-7 break-all" data-testid="verify-email-address">
            {email}
          </p>

          <form onSubmit={submit}>
            <div className="flex justify-center gap-2 mb-7" dir="ltr">
              {digits.map((d, i) => (
                <input
                  key={i}
                  ref={(el) => (inputsRef.current[i] = el)}
                  data-testid={`code-input-${i}`}
                  inputMode="numeric"
                  maxLength={6}
                  value={d}
                  onChange={(e) => handleChange(i, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(i, e)}
                  className="w-11 h-14 text-center text-2xl font-bold rounded-xl bg-[#12121C] border border-[rgba(255,255,255,0.1)] text-white focus:border-[#A855F7] focus:outline-none transition-colors"
                />
              ))}
            </div>
            <Button
              type="submit"
              data-testid="verify-submit-btn"
              disabled={loading || code.length !== 6}
              className="w-full rounded-full h-11 ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity disabled:opacity-40"
            >
              {loading ? <Dots /> : "تفعيل الحساب"}
            </Button>
          </form>

          <div className="mt-6 text-sm text-[#94A3B8]">
            لم يصلك الكود؟{" "}
            <button
              type="button"
              onClick={resend}
              data-testid="resend-code-btn"
              disabled={cooldown > 0}
              className="text-[#A855F7] hover:underline disabled:text-[#64748B] disabled:no-underline"
            >
              {cooldown > 0 ? `إعادة الإرسال خلال ${cooldown}ث` : "إعادة إرسال الكود"}
            </button>
          </div>
          <p className="text-xs text-[#64748B] mt-3">
            تحقّق من مجلد الرسائل غير المرغوب فيها (Spam) إذا لم تجد الرسالة.
          </p>

          <p className="text-sm text-[#94A3B8] mt-6">
            <Link to="/register" className="text-[#A855F7] hover:underline">
              العودة للتسجيل ببريد آخر
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
