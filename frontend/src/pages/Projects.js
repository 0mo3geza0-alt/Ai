import { useEffect, useState } from "react";
import { useOutletContext, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { FolderGit2, Plus, ArrowRight } from "lucide-react";
import { api, formatApiErrorDetail } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

export default function Projects() {
  const { activeOrg } = useOutletContext();
  const oid = activeOrg.id;
  const canCreate = ["owner", "admin", "member"].includes(activeOrg.role);
  const nav = useNavigate();
  const [projects, setProjects] = useState([]);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [openDlg, setOpenDlg] = useState(false);

  const load = async () => {
    try { const { data } = await api.get(`/orgs/${oid}/projects`); setProjects(data); } catch { setProjects([]); }
  };
  useEffect(() => { load(); }, [oid]); // eslint-disable-line

  const create = async (e) => {
    e.preventDefault();
    try { await api.post(`/orgs/${oid}/projects`, { name, description: desc }); setName(""); setDesc(""); setOpenDlg(false); toast.success("Project created"); load(); }
    catch (err) { toast.error(formatApiErrorDetail(err.response?.data?.detail)); }
  };

  return (
    <div className="px-5 lg:px-8 py-8 max-w-5xl">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display text-2xl md:text-3xl font-bold mb-1">Projects</h1>
          <p className="text-[#94A3B8]">Workspaces for files, artifacts and versions.</p>
        </div>
        {canCreate && (
          <Dialog open={openDlg} onOpenChange={setOpenDlg}>
            <DialogTrigger asChild>
              <Button data-testid="new-project-btn" className="rounded-full ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity"><Plus className="w-4 h-4 me-2" /> New project</Button>
            </DialogTrigger>
            <DialogContent className="bg-[#0C0C14] border border-[rgba(255,255,255,0.12)] text-white">
              <DialogHeader><DialogTitle className="font-display">Create project</DialogTitle></DialogHeader>
              <form onSubmit={create} className="space-y-4 mt-2">
                <Input data-testid="project-name-input" required placeholder="Project name" value={name} onChange={(e) => setName(e.target.value)}
                  className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" />
                <Textarea data-testid="project-desc-input" placeholder="Description (optional)" value={desc} onChange={(e) => setDesc(e.target.value)}
                  className="resize-none bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" />
                <Button data-testid="submit-project-btn" type="submit" className="w-full rounded-full ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity">Create</Button>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {projects.length === 0 ? (
        <div className="flex flex-col items-center justify-center text-center py-20 text-[#64748B]">
          <FolderGit2 className="w-10 h-10 mb-3 opacity-40" /><p>No projects yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {projects.map((p, i) => (
            <motion.button key={p.id} data-testid={`project-card-${p.id}`} onClick={() => nav(`/app/projects/${p.id}`)}
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: i * 0.04 }}
              className="group text-start p-6 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] hover:border-[rgba(255,255,255,0.18)] transition-colors">
              <div className="flex items-start justify-between mb-3">
                <span className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center group-hover:ai-gradient-bg transition-colors">
                  <FolderGit2 className="w-5 h-5 text-[#A855F7] group-hover:text-white transition-colors" />
                </span>
                <ArrowRight className="w-4 h-4 text-[#64748B] group-hover:text-white transition-colors" />
              </div>
              <p className="font-display font-semibold mb-1">{p.name}</p>
              <p className="text-sm text-[#64748B] line-clamp-2">{p.description || "No description"}</p>
            </motion.button>
          ))}
        </div>
      )}
    </div>
  );
}
