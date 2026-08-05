import { Languages, Sparkles } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { Link } from "react-router-dom";

export function Logo({ size = "text-xl" }) {
  const { t } = useApp();
  return (
    <Link to="/" data-testid="logo-link" className="flex items-center gap-2 group">
      <span className="w-8 h-8 rounded-lg ai-gradient-bg flex items-center justify-center glow-border">
        <Sparkles className="w-4 h-4 text-white" />
      </span>
      <span className={`font-display font-bold ${size} tracking-tight`}>{t.brand}</span>
    </Link>
  );
}

export function LangSwitcher({ className = "" }) {
  const { lang, toggleLang } = useApp();
  return (
    <button
      data-testid="language-switcher-toggle"
      onClick={toggleLang}
      className={`flex items-center gap-2 px-3 py-2 rounded-full text-sm text-[#94A3B8] hover:text-white border border-[rgba(255,255,255,0.08)] hover:border-[rgba(255,255,255,0.2)] transition-colors ${className}`}
    >
      <Languages className="w-4 h-4" />
      {lang === "ar" ? "EN" : "ع"}
    </button>
  );
}

export function Dots() {
  return <span className="inline-flex gap-1.5 items-center"><span className="dot" /><span className="dot" /><span className="dot" /></span>;
}
