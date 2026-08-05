import { useEffect, useState } from "react";
import axios from "axios";
import { motion } from "framer-motion";
import { Activity, Database, Cpu, CheckCircle2, Circle, GitBranch } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PHASES = [
  { n: 1, label: "Foundation", done: true },
  { n: 2, label: "Authentication" },
  { n: 3, label: "Workspace" },
  { n: 4, label: "Tool Framework" },
  { n: 5, label: "Memory System" },
  { n: 6, label: "Planning Engine" },
  { n: 7, label: "Multi-Agent System" },
  { n: 8, label: "Browser Automation" },
  { n: 9, label: "LLM Gateway" },
  { n: 10, label: "Frontend" },
  { n: 11, label: "Infrastructure" },
  { n: 12, label: "Security" },
  { n: 13, label: "Testing" },
  { n: 14, label: "Production" },
];

export default function Foundation() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    axios.get(`${API}/health`)
      .then(({ data }) => setHealth(data))
      .catch(() => setError(true));
  }, []);

  const dbConnected = health?.database === "connected";

  return (
    <div className="min-h-screen text-[#F8FAFC] px-5 py-16 relative z-10">
      <div className="max-w-4xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full glass border border-[rgba(255,255,255,0.1)] text-xs text-[#94A3B8] mb-6">
            <GitBranch className="w-3.5 h-3.5" /> {health?.phase || "Phase 1 — Foundation"}
          </div>
          <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-4">
            Autonomous <span className="ai-gradient-text">AI Agent</span> Platform
          </h1>
          <p className="text-[#94A3B8] text-base md:text-lg max-w-2xl leading-relaxed mb-12">
            Production-grade multi-agent system. Built phase by phase — each milestone fully runnable and tested. This is the Foundation boot screen.
          </p>
        </motion.div>

        {/* system status */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-14">
          {[
            { icon: Activity, label: "API Service", value: error ? "offline" : health?.status || "…", ok: !error && health?.status === "ok" },
            { icon: Database, label: "MongoDB", value: error ? "unknown" : health?.database || "…", ok: dbConnected },
            { icon: Cpu, label: "Version", value: health?.version || "…", ok: !!health },
          ].map((s, i) => (
            <motion.div key={i} data-testid={`status-${s.label.toLowerCase().replace(/\s/g, "-")}`}
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.1 + i * 0.08 }}
              className="p-5 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
              <div className="flex items-center justify-between mb-3">
                <s.icon className="w-5 h-5 text-[#A855F7]" />
                <span className={`w-2.5 h-2.5 rounded-full ${s.ok ? "bg-emerald-400" : "bg-amber-400"}`} />
              </div>
              <p className="font-display text-lg font-semibold capitalize">{s.value}</p>
              <p className="text-[#64748B] text-sm mt-1">{s.label}</p>
            </motion.div>
          ))}
        </div>

        {/* roadmap progress */}
        <h2 className="font-display text-lg font-semibold mb-5">Roadmap Progress</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {PHASES.map((p, i) => (
            <motion.div key={p.n} data-testid={`phase-${p.n}`}
              initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3, delay: i * 0.03 }}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl border transition-colors ${p.done ? "bg-[#12121C] border-[#4F46E5]/30" : "bg-[#0C0C14] border-[rgba(255,255,255,0.06)]"}`}>
              {p.done ? <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" /> : <Circle className="w-5 h-5 text-[#64748B] shrink-0" />}
              <span className="text-sm text-[#64748B]">Phase {p.n}</span>
              <span className={`text-sm font-medium ${p.done ? "text-white" : "text-[#94A3B8]"}`}>{p.label}</span>
              {p.done && <span className="ms-auto text-xs text-emerald-400">done</span>}
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
