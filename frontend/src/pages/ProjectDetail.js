import { useEffect, useState, useRef } from "react";
import { useParams, useOutletContext, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Upload, FileText, Download, History, ChevronDown, Trash2, Plus, FileCode2 } from "lucide-react";
import { api, formatApiErrorDetail } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dots } from "@/components/shared";

export default function ProjectDetail() {
  const { pid } = useParams();
  const { activeOrg } = useOutletContext();
  const oid = activeOrg.id;
  const canWrite = ["owner", "admin", "member"].includes(activeOrg.role);
  const canDelete = ["owner", "admin"].includes(activeOrg.role);
  const nav = useNavigate();
  const fileRef = useRef(null);

  const [project, setProject] = useState(null);
  const [files, setFiles] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [versions, setVersions] = useState({});
  const [artName, setArtName] = useState("");
  const [artContent, setArtContent] = useState("");

  const load = async () => {
    try {
      const [p, f, a] = await Promise.all([
        api.get(`/orgs/${oid}/projects/${pid}`).then((r) => r.data),
        api.get(`/orgs/${oid}/projects/${pid}/files`).then((r) => r.data),
        api.get(`/orgs/${oid}/projects/${pid}/artifacts`).then((r) => r.data),
      ]);
      setProject(p); setFiles(f); setArtifacts(a);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
      if (err.response?.status === 404) nav("/app/projects");
    }
  };
  useEffect(() => { load(); }, [pid, oid]); // eslint-disable-line

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    try {
      await api.post(`/orgs/${oid}/projects/${pid}/files`, form, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("File uploaded");
      load();
    } catch (err) { toast.error(formatApiErrorDetail(err.response?.data?.detail)); }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  const toggleVersions = async (fileId) => {
    if (expanded === fileId) { setExpanded(null); return; }
    setExpanded(fileId);
    if (!versions[fileId]) {
      try { const { data } = await api.get(`/orgs/${oid}/projects/${pid}/files/${fileId}/versions`); setVersions((v) => ({ ...v, [fileId]: data })); }
      catch { /* ignore */ }
    }
  };

  const download = async (fileId, name) => {
    try {
      const res = await api.get(`/orgs/${oid}/projects/${pid}/files/${fileId}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = name; a.click();
      URL.revokeObjectURL(url);
    } catch (err) { toast.error(formatApiErrorDetail(err.response?.data?.detail)); }
  };

  const createArtifact = async (e) => {
    e.preventDefault();
    try { await api.post(`/orgs/${oid}/projects/${pid}/artifacts`, { name: artName, type: "text", content: artContent }); setArtName(""); setArtContent(""); toast.success("Artifact saved"); load(); }
    catch (err) { toast.error(formatApiErrorDetail(err.response?.data?.detail)); }
  };

  const deleteProject = async () => {
    if (!window.confirm("Delete this project and all its files?")) return;
    try { await api.delete(`/orgs/${oid}/projects/${pid}`); toast.success("Project deleted"); nav("/app/projects"); }
    catch (err) { toast.error(formatApiErrorDetail(err.response?.data?.detail)); }
  };

  if (!project) return <div className="p-8"><Dots /></div>;

  return (
    <div className="px-5 lg:px-8 py-8 max-w-4xl">
      <button onClick={() => nav("/app/projects")} data-testid="back-btn" className="flex items-center gap-2 text-sm text-[#94A3B8] hover:text-white transition-colors mb-6"><ArrowLeft className="w-4 h-4" /> Projects</button>

      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="font-display text-2xl md:text-3xl font-bold mb-1">{project.name}</h1>
          <p className="text-[#94A3B8]">{project.description || "No description"}</p>
        </div>
        {canDelete && <button data-testid="delete-project-btn" onClick={deleteProject} className="text-[#64748B] hover:text-red-400 transition-colors p-2"><Trash2 className="w-5 h-5" /></button>}
      </div>

      {/* files */}
      <section className="p-6 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] mb-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-display text-lg font-semibold flex items-center gap-2"><FileText className="w-5 h-5 text-[#0EA5E9]" /> Files</h2>
          {canWrite && (
            <>
              <input ref={fileRef} type="file" onChange={upload} className="hidden" data-testid="file-input" />
              <Button data-testid="upload-file-btn" onClick={() => fileRef.current?.click()} disabled={uploading}
                className="rounded-full ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity">
                {uploading ? <Dots /> : <><Upload className="w-4 h-4 me-2" /> Upload</>}
              </Button>
            </>
          )}
        </div>
        {files.length === 0 ? <p className="text-sm text-[#64748B]">No files yet. Upload one — re-uploading the same name creates a new version.</p> : (
          <div className="space-y-2">
            {files.map((f) => (
              <div key={f.id} data-testid={`file-${f.id}`} className="rounded-xl bg-[#12121C] border border-[rgba(255,255,255,0.06)]">
                <div className="flex items-center justify-between px-4 py-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <FileText className="w-4 h-4 text-[#A855F7] shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm text-white truncate">{f.name}</p>
                      <p className="text-xs text-[#64748B]">v{f.version} · {(f.size / 1024).toFixed(1)} KB</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button data-testid={`versions-${f.id}`} onClick={() => toggleVersions(f.id)} className="p-2 text-[#64748B] hover:text-white transition-colors" title="Version history"><History className="w-4 h-4" /></button>
                    <button data-testid={`download-${f.id}`} onClick={() => download(f.id, f.name)} className="p-2 text-[#64748B] hover:text-white transition-colors" title="Download"><Download className="w-4 h-4" /></button>
                    <ChevronDown className={`w-4 h-4 text-[#64748B] transition-transform ${expanded === f.id ? "rotate-180" : ""}`} />
                  </div>
                </div>
                {expanded === f.id && (
                  <div className="px-4 pb-3 border-t border-[rgba(255,255,255,0.06)] pt-3">
                    <p className="text-xs text-[#64748B] mb-2">Version history</p>
                    {(versions[f.id] || []).map((v) => (
                      <div key={v.id} className="flex items-center justify-between py-1.5 text-sm">
                        <span className="text-[#94A3B8]">v{v.version} · {new Date(v.created_at).toLocaleString()}</span>
                        <button onClick={() => download(v.id, `${v.name}.v${v.version}`)} className="text-[#64748B] hover:text-white transition-colors"><Download className="w-3.5 h-3.5" /></button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* artifacts */}
      <section className="p-6 rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)]">
        <h2 className="font-display text-lg font-semibold mb-5 flex items-center gap-2"><FileCode2 className="w-5 h-5 text-[#D946EF]" /> Artifacts</h2>
        {canWrite && (
          <form onSubmit={createArtifact} className="space-y-3 mb-5">
            <Input data-testid="artifact-name-input" required placeholder="Artifact name" value={artName} onChange={(e) => setArtName(e.target.value)}
              className="bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" />
            <Textarea data-testid="artifact-content-input" placeholder="Content (text / code)" value={artContent} onChange={(e) => setArtContent(e.target.value)} rows={4}
              className="resize-none font-mono text-sm bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors" />
            <Button data-testid="create-artifact-btn" type="submit" className="rounded-full ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity"><Plus className="w-4 h-4 me-2" /> Save artifact</Button>
          </form>
        )}
        {artifacts.length === 0 ? <p className="text-sm text-[#64748B]">No artifacts yet.</p> : (
          <div className="space-y-2">
            {artifacts.map((a) => (
              <div key={a.id} data-testid={`artifact-${a.id}`} className="px-4 py-3 rounded-xl bg-[#12121C] border border-[rgba(255,255,255,0.06)]">
                <p className="text-sm text-white mb-1">{a.name} <span className="text-xs text-[#64748B]">· {a.type}</span></p>
                {a.content && <pre className="text-xs text-[#94A3B8] whitespace-pre-wrap line-clamp-4 font-mono">{a.content}</pre>}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
