import { useState } from "react";
import { Crown } from "lucide-react";
import { toast } from "sonner";
import { useApp, api, formatApiErrorDetail } from "@/context/AppContext";
import { Dots } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function Settings() {
  const { t, user, setUser } = useApp();
  const [name, setName] = useState(user?.name || "");
  const [savingProfile, setSavingProfile] = useState(false);
  const [cur, setCur] = useState("");
  const [np, setNp] = useState("");
  const [savingPass, setSavingPass] = useState(false);

  const saveProfile = async () => {
    setSavingProfile(true);
    try { const { data } = await api.put("/account/profile", { name }); setUser(data); toast.success(t.settings.saved); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSavingProfile(false); }
  };

  const savePass = async () => {
    setSavingPass(true);
    try { await api.post("/account/password", { current_password: cur, new_password: np }); toast.success(t.settings.updated); setCur(""); setNp(""); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSavingPass(false); }
  };

  const upgrade = async () => {
    try { const { data } = await api.post("/billing/upgrade"); setUser(data); toast.success("Pro activated"); }
    catch { toast.error(t.common.error); }
  };

  return (
    <div className="px-5 lg:px-8 py-8 max-w-2xl">
      <h1 className="font-display text-2xl md:text-3xl font-bold mb-8">{t.settings.title}</h1>

      <section className="p-6 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] mb-6">
        <h2 className="font-display text-lg font-semibold mb-5">{t.settings.profile}</h2>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label className="text-[#94A3B8]">{t.settings.name}</Label>
            <Input data-testid="settings-name-input" value={name} onChange={(e) => setName(e.target.value)}
              className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" />
          </div>
          <div className="space-y-2">
            <Label className="text-[#94A3B8]">{t.settings.email}</Label>
            <Input value={user?.email || ""} disabled className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-[#64748B]" />
          </div>
          <Button data-testid="settings-save-profile-btn" onClick={saveProfile} disabled={savingProfile}
            className="rounded-full ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity">
            {savingProfile ? <Dots /> : t.settings.save}
          </Button>
        </div>
      </section>

      <section className="p-6 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] mb-6">
        <h2 className="font-display text-lg font-semibold mb-5">{t.settings.passwordSec}</h2>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label className="text-[#94A3B8]">{t.settings.current}</Label>
            <Input data-testid="settings-current-password" type="password" value={cur} onChange={(e) => setCur(e.target.value)}
              className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" />
          </div>
          <div className="space-y-2">
            <Label className="text-[#94A3B8]">{t.settings.newpass}</Label>
            <Input data-testid="settings-new-password" type="password" value={np} onChange={(e) => setNp(e.target.value)}
              className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" />
          </div>
          <Button data-testid="settings-update-password-btn" onClick={savePass} disabled={savingPass || !cur || !np}
            className="rounded-full ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity">
            {savingPass ? <Dots /> : t.settings.update}
          </Button>
        </div>
      </section>

      <section className="p-6 rounded-2xl bg-[#12121C] border border-[#4F46E5]/30 glow-border">
        <h2 className="font-display text-lg font-semibold mb-2 flex items-center gap-2"><Crown className="w-5 h-5 text-[#D946EF]" /> {t.settings.planSec}</h2>
        <p className="text-[#94A3B8] text-sm mb-5">{t.settings.planText} <span className="text-white font-semibold">{user?.plan === "pro" ? t.pricing.pro : t.pricing.free}</span></p>
        {user?.plan !== "pro" && (
          <Button data-testid="settings-upgrade-btn" onClick={upgrade} className="rounded-full ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity">
            {t.settings.upgrade}
          </Button>
        )}
      </section>
    </div>
  );
}
