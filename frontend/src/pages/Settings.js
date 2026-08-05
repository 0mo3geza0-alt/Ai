import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { toast } from "sonner";
import { Plus, Building2 } from "lucide-react";
import { useAuth, api, formatApiErrorDetail } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function Settings() {
  const { user } = useAuth();
  const { orgs, refreshOrgs, setActiveOrg } = useOutletContext();
  const [orgName, setOrgName] = useState("");

  const createOrg = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post("/orgs", { name: orgName });
      setOrgName("");
      const list = await refreshOrgs();
      const created = list.find((o) => o.id === data.id);
      if (created) setActiveOrg(created);
      toast.success("Organization created");
    } catch (err) { toast.error(formatApiErrorDetail(err.response?.data?.detail)); }
  };

  return (
    <div className="px-5 lg:px-8 py-8 max-w-2xl">
      <h1 className="font-display text-2xl md:text-3xl font-bold mb-8">Settings</h1>

      <section className="p-6 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] mb-6">
        <h2 className="font-display text-lg font-semibold mb-5">Profile</h2>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label className="text-[#94A3B8]">Full name</Label>
            <Input value={user?.name || ""} disabled className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-[#94A3B8]" />
          </div>
          <div className="space-y-2">
            <Label className="text-[#94A3B8]">Email</Label>
            <Input value={user?.email || ""} disabled className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-[#64748B]" />
          </div>
          <div className="flex items-center gap-2 text-sm text-[#94A3B8]">
            <span className="px-2.5 py-1 rounded-full bg-[#12121C] border border-[rgba(255,255,255,0.1)] capitalize">{user?.global_role}</span>
            <span className="px-2.5 py-1 rounded-full bg-[#12121C] border border-[rgba(255,255,255,0.1)]">via {user?.auth_provider}</span>
          </div>
        </div>
      </section>

      <section className="p-6 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
        <h2 className="font-display text-lg font-semibold mb-5 flex items-center gap-2"><Building2 className="w-5 h-5 text-[#A855F7]" /> Organizations</h2>
        <div className="space-y-2 mb-5">
          {orgs.map((o) => (
            <div key={o.id} className="flex items-center justify-between px-4 py-3 rounded-xl bg-[#12121C] border border-[rgba(255,255,255,0.06)]">
              <span className="text-sm text-white">{o.name}</span>
              <span className="text-xs text-[#64748B] capitalize">{o.role}</span>
            </div>
          ))}
        </div>
        <form onSubmit={createOrg} className="flex gap-3">
          <Input data-testid="new-org-input" required placeholder="New organization name" value={orgName} onChange={(e) => setOrgName(e.target.value)}
            className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" />
          <Button data-testid="create-org-btn" type="submit" className="rounded-full ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity"><Plus className="w-4 h-4 me-2" /> Create</Button>
        </form>
      </section>
    </div>
  );
}
