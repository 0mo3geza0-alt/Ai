import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { MessageSquare, PenLine, Image as ImageIcon, History as HistoryIcon, Gauge, ShieldCheck, ArrowRight, Check } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { Logo, LangSwitcher } from "@/components/shared";
import { Button } from "@/components/ui/button";

const HERO_IMG = "https://images.unsplash.com/photo-1654198340681-a2e0fc449f1b";

export default function Landing() {
  const { t, user } = useApp();
  const nav = useNavigate();
  const goApp = () => nav(user ? "/app" : "/register");

  const features = [
    { icon: MessageSquare, ...t.features.chat, span: "md:col-span-2" },
    { icon: PenLine, ...t.features.text, span: "" },
    { icon: ImageIcon, ...t.features.image, span: "" },
    { icon: HistoryIcon, ...t.features.history, span: "" },
    { icon: Gauge, ...t.features.credits, span: "" },
    { icon: ShieldCheck, ...t.features.secure, span: "md:col-span-2" },
  ];

  return (
    <div className="relative min-h-screen text-[#F8FAFC] overflow-hidden">
      {/* header */}
      <header className="fixed top-0 inset-x-0 z-50 glass border-b border-[rgba(255,255,255,0.06)]">
        <div className="max-w-6xl mx-auto px-5 h-16 flex items-center justify-between">
          <Logo />
          <nav className="hidden md:flex items-center gap-8 text-sm text-[#94A3B8]">
            <a href="#features" className="hover:text-white transition-colors">{t.nav.features}</a>
            <a href="#pricing" className="hover:text-white transition-colors">{t.nav.pricing}</a>
          </nav>
          <div className="flex items-center gap-2">
            <LangSwitcher />
            <Link to="/login" data-testid="nav-login-btn" className="text-sm text-[#94A3B8] hover:text-white px-3 py-2 transition-colors">{t.nav.login}</Link>
            <Button data-testid="nav-getstarted-btn" onClick={goApp} className="rounded-full ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity">{t.nav.getStarted}</Button>
          </div>
        </div>
      </header>

      {/* hero */}
      <section className="relative pt-40 pb-28 px-5">
        <div className="absolute inset-0 -z-10">
          <img src={HERO_IMG} alt="" className="w-full h-full object-cover opacity-40" />
          <div className="absolute inset-0 bg-gradient-to-b from-[#05050A]/60 via-[#05050A]/80 to-[#05050A]" />
        </div>
        <div className="max-w-4xl mx-auto text-start">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full glass border border-[rgba(255,255,255,0.1)] text-xs text-[#94A3B8] mb-8">
            <span className="w-2 h-2 rounded-full ai-gradient-bg" /> {t.hero.badge}
          </motion.div>
          <motion.h1 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.1 }}
            className="font-display text-4xl sm:text-5xl lg:text-6xl font-bold leading-tight tracking-tight mb-6">
            {t.hero.title1}<br />
            <span className="ai-gradient-text">{t.hero.title2}</span>
          </motion.h1>
          <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.2 }}
            className="text-[#94A3B8] text-base md:text-lg max-w-2xl leading-relaxed mb-10">{t.hero.subtitle}</motion.p>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.3 }}
            className="flex flex-wrap items-center gap-4">
            <Button data-testid="hero-cta-btn" onClick={goApp} className="rounded-full h-12 px-8 text-base ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity glow-border">
              {t.hero.cta} <ArrowRight className="w-4 h-4 ms-2 rtl:rotate-180" />
            </Button>
            <a href="#features"><Button variant="outline" data-testid="hero-secondary-btn" className="rounded-full h-12 px-8 text-base bg-transparent border-[rgba(255,255,255,0.15)] text-white hover:bg-white/5 transition-colors">{t.hero.secondary}</Button></a>
          </motion.div>
        </div>
      </section>

      {/* features */}
      <section id="features" className="relative py-24 px-5 max-w-6xl mx-auto">
        <div className="mb-14 max-w-2xl">
          <h2 className="font-display text-3xl md:text-4xl font-bold tracking-tight mb-3">{t.features.heading}</h2>
          <p className="text-[#94A3B8] text-base md:text-lg leading-relaxed">{t.features.sub}</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {features.map((f, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.06 }}
              className={`${f.span} group p-7 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] hover:border-[rgba(255,255,255,0.18)] transition-colors`}>
              <span className="w-11 h-11 rounded-xl flex items-center justify-center bg-white/5 border border-[rgba(255,255,255,0.08)] mb-5 group-hover:ai-gradient-bg transition-colors">
                <f.icon className="w-5 h-5 text-[#A855F7] group-hover:text-white transition-colors" />
              </span>
              <h3 className="font-display text-lg font-semibold mb-2">{f.title}</h3>
              <p className="text-[#94A3B8] text-sm leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* pricing */}
      <section id="pricing" className="relative py-24 px-5 max-w-5xl mx-auto">
        <div className="mb-14 max-w-2xl">
          <h2 className="font-display text-3xl md:text-4xl font-bold tracking-tight mb-3">{t.pricing.heading}</h2>
          <p className="text-[#94A3B8] text-base md:text-lg">{t.pricing.sub}</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="p-8 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.08)]">
            <p className="text-[#94A3B8] mb-1">{t.pricing.free}</p>
            <p className="font-display text-4xl font-bold mb-6">$0<span className="text-base text-[#64748B] font-normal">{t.pricing.month}</span></p>
            <ul className="space-y-3 mb-8">
              {t.pricing.freefeat.map((f, i) => <li key={i} className="flex items-center gap-3 text-sm text-[#94A3B8]"><Check className="w-4 h-4 text-[#0EA5E9]" /> {f}</li>)}
            </ul>
            <Button data-testid="pricing-free-btn" onClick={goApp} variant="outline" className="w-full rounded-full bg-transparent border-[rgba(255,255,255,0.15)] text-white hover:bg-white/5 transition-colors">{t.pricing.freecta}</Button>
          </div>
          <div className="relative p-8 rounded-2xl bg-[#12121C] border border-[#4F46E5]/40 glow-border overflow-hidden">
            <div className="absolute top-0 inset-x-0 h-1 ai-gradient-bg" />
            <p className="ai-gradient-text font-semibold mb-1">{t.pricing.pro}</p>
            <p className="font-display text-4xl font-bold mb-6">$19<span className="text-base text-[#64748B] font-normal">{t.pricing.month}</span></p>
            <ul className="space-y-3 mb-8">
              {t.pricing.profeat.map((f, i) => <li key={i} className="flex items-center gap-3 text-sm text-[#F8FAFC]"><Check className="w-4 h-4 text-[#D946EF]" /> {f}</li>)}
            </ul>
            <Button data-testid="pricing-pro-btn" onClick={goApp} className="w-full rounded-full ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity">{t.pricing.procta}</Button>
          </div>
        </div>
      </section>

      <footer className="border-t border-[rgba(255,255,255,0.06)] py-10 px-5">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <Logo size="text-lg" />
          <p className="text-sm text-[#64748B]">{t.footer}</p>
        </div>
      </footer>
    </div>
  );
}
