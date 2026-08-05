import { useState } from "react";
import { motion } from "framer-motion";
import { Image as ImageIcon, Download, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useApp, api, formatApiErrorDetail } from "@/context/AppContext";
import { Dots } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export default function ImageStudio() {
  const { t, updateCredits } = useApp();
  const [prompt, setPrompt] = useState("");
  const [image, setImage] = useState("");
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    if (!prompt.trim()) return;
    setLoading(true); setImage("");
    try {
      const { data } = await api.post("/image/generate", { prompt });
      setImage(data.image);
      updateCredits(data.credits);
    } catch (err) {
      toast.error(err.response?.status === 402 ? t.common.noCredits : formatApiErrorDetail(err.response?.data?.detail) || t.common.error);
    } finally { setLoading(false); }
  };

  const download = () => {
    const a = document.createElement("a");
    a.href = image; a.download = "neuraforge-image.png"; a.click();
  };

  return (
    <div className="px-5 lg:px-8 py-8 max-w-5xl">
      <h1 className="font-display text-2xl md:text-3xl font-bold mb-1">{t.image.title}</h1>
      <p className="text-[#94A3B8] mb-8">{t.image.sub}</p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <Textarea data-testid="image-prompt-input" value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={6}
            placeholder={t.image.placeholder}
            className="resize-none bg-[#12121C] border-[rgba(255,255,255,0.1)] text-white focus:border-[#4F46E5] transition-colors rounded-xl" />
          <Button data-testid="image-generate-btn" onClick={generate} disabled={loading || !prompt.trim()}
            className="rounded-full h-11 px-8 ai-gradient-bg text-white border-0 hover:opacity-90 transition-opacity">
            <Sparkles className="w-4 h-4 me-2" /> {loading ? <Dots /> : t.image.generate}
          </Button>
        </div>

        <div className="rounded-2xl bg-[#0C0C14] border border-[rgba(255,255,255,0.06)] p-5 aspect-square flex items-center justify-center relative overflow-hidden">
          {loading ? (
            <div className="flex flex-col items-center gap-4"><Dots /><p className="text-sm text-[#64748B]">{t.common.loading}</p></div>
          ) : image ? (
            <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} className="w-full h-full relative group">
              <img data-testid="generated-image" src={image} alt="generated" className="w-full h-full object-contain rounded-xl" />
              <button onClick={download} data-testid="image-download-btn"
                className="absolute bottom-3 end-3 flex items-center gap-2 px-3 py-2 rounded-full glass text-white text-sm opacity-0 group-hover:opacity-100 transition-opacity border border-[rgba(255,255,255,0.15)]">
                <Download className="w-4 h-4" /> {t.image.download}
              </button>
            </motion.div>
          ) : (
            <div className="flex flex-col items-center text-center text-[#64748B]">
              <ImageIcon className="w-10 h-10 mb-3 opacity-40" /><p className="text-sm max-w-xs">{t.image.empty}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
