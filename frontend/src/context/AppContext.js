import { createContext, useContext, useState, useEffect, useCallback } from "react";
import axios from "axios";
import { translations } from "@/i18n";

axios.defaults.withCredentials = true;
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, withCredentials: true });

const savedToken = localStorage.getItem("token");
if (savedToken) api.defaults.headers.common["Authorization"] = `Bearer ${savedToken}`;

function setAuthToken(token) {
  if (token) {
    localStorage.setItem("token", token);
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    localStorage.removeItem("token");
    delete api.defaults.headers.common["Authorization"];
  }
}

const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export function AppProvider({ children }) {
  const [user, setUser] = useState(null); // null=checking, false=guest, obj=auth
  const [lang, setLang] = useState(() => localStorage.getItem("lang") || "ar");

  const t = translations[lang];

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = translations[lang].dir;
    localStorage.setItem("lang", lang);
  }, [lang]);

  const toggleLang = () => setLang((l) => (l === "ar" ? "en" : "ar"));

  const refreshUser = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
      return data;
    } catch {
      setUser(false);
      return null;
    }
  }, []);

  useEffect(() => { refreshUser(); }, [refreshUser]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    setAuthToken(data.token);
    setUser(data.user);
    return data.user;
  };
  const register = async (name, email, password) => {
    const { data } = await api.post("/auth/register", { name, email, password });
    setAuthToken(data.token);
    setUser(data.user);
    return data.user;
  };
  const logout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    setAuthToken(null);
    setUser(false);
  };
  const updateCredits = (credits) => setUser((u) => (u ? { ...u, credits } : u));

  return (
    <AppContext.Provider value={{ user, setUser, lang, setLang, toggleLang, t, refreshUser, login, register, logout, updateCredits }}>
      {children}
    </AppContext.Provider>
  );
}
