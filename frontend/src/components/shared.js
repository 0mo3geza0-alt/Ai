import { Link } from "react-router-dom";
import { Hexagon } from "lucide-react";

export const BRAND = "VibeVerse";

export function Logo({ size = "text-xl", to = "/" }) {
  return (
    <Link to={to} data-testid="logo-link" className="flex items-center gap-2 group">
      <span className="w-8 h-8 rounded-lg ai-gradient-bg flex items-center justify-center glow-border">
        <Hexagon className="w-4 h-4 text-white" />
      </span>
      <span className={`font-display font-bold ${size} tracking-tight`}>{BRAND}</span>
    </Link>
  );
}

export function Dots() {
  return <span className="inline-flex gap-1.5 items-center"><span className="dot" /><span className="dot" /><span className="dot" /></span>;
}
