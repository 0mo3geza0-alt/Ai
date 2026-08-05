import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Foundation from "@/pages/Foundation";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import AuthCallback from "@/pages/AuthCallback";
import DashboardLayout from "@/pages/DashboardLayout";
import Overview from "@/pages/Overview";
import Organization from "@/pages/Organization";
import ApiKeys from "@/pages/ApiKeys";
import Projects from "@/pages/Projects";
import ProjectDetail from "@/pages/ProjectDetail";
import Settings from "@/pages/Settings";

function Boot() {
  return <div className="min-h-screen flex items-center justify-center bg-[#05050A]"><span className="flex gap-2"><span className="dot" /><span className="dot" /><span className="dot" /></span></div>;
}

function Protected({ children }) {
  const { user } = useAuth();
  if (user === null) return <Boot />;
  if (user === false) return <Navigate to="/login" replace />;
  return children;
}

function Guest({ children }) {
  const { user } = useAuth();
  if (user === null) return <Boot />;
  if (user) return <Navigate to="/app" replace />;
  return children;
}

function AppRouter() {
  const location = useLocation();
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <Routes>
      <Route path="/" element={<Foundation />} />
      <Route path="/login" element={<Guest><Login /></Guest>} />
      <Route path="/register" element={<Guest><Register /></Guest>} />
      <Route path="/app" element={<Protected><DashboardLayout /></Protected>}>
        <Route index element={<Overview />} />
        <Route path="organization" element={<Organization />} />
        <Route path="api-keys" element={<ApiKeys />} />
        <Route path="projects" element={<Projects />} />
        <Route path="projects/:pid" element={<ProjectDetail />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <div className="App grain">
      <AuthProvider>
        <BrowserRouter>
          <AppRouter />
        </BrowserRouter>
        <Toaster position="top-center" theme="dark" richColors />
      </AuthProvider>
    </div>
  );
}

export default App;
