import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";

export default function AuthCallback() {
  const { oauthExchange } = useAuth();
  const nav = useNavigate();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;
    const hash = window.location.hash || "";
    const match = hash.match(/session_id=([^&]+)/);
    const sessionId = match ? decodeURIComponent(match[1]) : null;
    (async () => {
      if (!sessionId) { nav("/login", { replace: true }); return; }
      try {
        await oauthExchange(sessionId);
        window.history.replaceState(null, "", "/app");
        nav("/app", { replace: true });
      } catch {
        toast.error("Google sign-in failed. Please try again.");
        nav("/login", { replace: true });
      }
    })();
  }, [oauthExchange, nav]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#05050A]">
      <span className="flex gap-2"><span className="dot" /><span className="dot" /><span className="dot" /></span>
    </div>
  );
}
