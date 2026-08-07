import { Link } from "react-router-dom";
import logoImg from "../assets/logo.png";

export const BRAND = "VibeVerse";

export function Logo({ size = "text-xl", to = "/", showText = true }) {
  return (
    <Link to={to} data-testid="logo-link" className="flex items-center gap-2 group">
      <img
        src={logoImg}
        alt="VibeVerse"
        className="h-9 w-auto object-contain drop-shadow-[0_0_10px_rgba(168,85,247,0.35)] transition-transform group-hover:scale-105"
      />
      {showText && (
        <span className={`font-display font-bold ${size} tracking-tight`}>{BRAND}</span>
      )}
    </Link>
  );
}

export function Dots() {
  return <span className="inline-flex gap-1.5 items-center"><span className="dot" /><span className="dot" /><span className="dot" /></span>;
}
