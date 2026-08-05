import { createContext, useContext, useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
export const api = axios.create({ baseURL: API, withCredentials: true });

const saved = localStorage.getItem("token");
if (saved) api.defaults.headers.common["Authorization"] = `Bearer ${saved}`;

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem("token", token);
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    localStorage.removeItem("token");
    delete api.defaults.headers.common["Authorization"];
  }
}

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null=checking, false=guest, obj=auth

  const refreshUser = useCallback(async () => {
    if (window.location.hash?.includes("session_id=")) { return; }
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
  const oauthExchange = async (sessionId) => {
    const { data } = await api.post("/auth/oauth/emergent", { session_id: sessionId });
    setAuthToken(data.token);
    setUser(data.user);
    return data.user;
  };
  const logout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    setAuthToken(null);
    setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, setUser, login, register, oauthExchange, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}
