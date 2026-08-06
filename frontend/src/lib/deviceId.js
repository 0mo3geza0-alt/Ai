// Lightweight, dependency-free device fingerprint used to limit multiple
// account creation from the same browser/device. Not bullet-proof, but a
// good free deterrent combined with email + IP checks.

function hashString(str) {
  let h1 = 0xdeadbeef ^ str.length;
  let h2 = 0x41c6ce57 ^ str.length;
  for (let i = 0; i < str.length; i++) {
    const ch = str.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(16);
}

function canvasSignature() {
  try {
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    if (!ctx) return "nocanvas";
    ctx.textBaseline = "top";
    ctx.font = "14px 'Arial'";
    ctx.fillStyle = "#f60";
    ctx.fillRect(125, 1, 62, 20);
    ctx.fillStyle = "#069";
    ctx.fillText("VibeVerse-fp", 2, 15);
    ctx.fillStyle = "rgba(102,204,0,0.7)";
    ctx.fillText("VibeVerse-fp", 4, 17);
    return canvas.toDataURL();
  } catch {
    return "canvaserr";
  }
}

export function getDeviceFingerprint() {
  const KEY = "vv_device_id";
  const cached = localStorage.getItem(KEY);
  if (cached) return cached;

  const nav = window.navigator || {};
  const scr = window.screen || {};
  const parts = [
    nav.userAgent,
    nav.language,
    (nav.languages || []).join(","),
    nav.platform,
    nav.hardwareConcurrency,
    nav.deviceMemory,
    scr.width + "x" + scr.height + "x" + scr.colorDepth,
    new Date().getTimezoneOffset(),
    Intl.DateTimeFormat().resolvedOptions().timeZone,
    canvasSignature(),
  ].join("||");

  const fp = hashString(parts);
  try { localStorage.setItem(KEY, fp); } catch {}
  return fp;
}
