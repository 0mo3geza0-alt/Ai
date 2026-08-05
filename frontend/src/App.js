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
import Chat from "@/pages/Chat";
import Creations from "@/pages/Creations";
import Agents from "@/pages/Agents";
import Memory from "@/pages/Memory";
import Security from "@/pages/Security";
import Admin from "@/pages/Admin";
import Organization from "@/pages/Organization";
import ApiKeys from "@/pages/ApiKeys";
import Projects from "@/pages/Projects";
import ProjectDetail from "@/pages/ProjectDetail";
import Settings from "@/pages/Settings";
import SharePage from "@/pages/SharePage";
import Gallery from "@/pages/Gallery";
import Backoffice from "@/pages/Backoffice";
import Billing from "@/pages/Billing";
import PaymentSuccess from "@/pages/PaymentSuccess";
import PaymentCancel from "@/pages/PaymentCancel";

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
      <Route path="/gallery" element={<Gallery />} />
      <Route path="/backoffice" element={<Backoffice />} />
      <Route path="/share/:token" element={<SharePage />} />
      <Route path="/payment/success" element={<Protected><PaymentSuccess /></Protected>} />
      <Route path="/payment/cancel" element={<Protected><PaymentCancel /></Protected>} />
      <Route path="/login" element={<Guest><Login /></Guest>} />
      <Route path="/register" element={<Guest><Register /></Guest>} />
      <Route path="/app" element={<Protected><DashboardLayout /></Protected>}>
        <Route index element={<Overview />} />
        <Route path="chat" element={<Chat />} />
        <Route path="create" element={<Navigate to="/app/chat" replace />} />
        <Route path="creations" element={<Creations />} />
        <Route path="agents" element={<Agents />} />
        <Route path="memory" element={<Memory />} />
        <Route path="security" element={<Security />} />
        <Route path="admin" element={<Admin />} />
        <Route path="organization" element={<Organization />} />
        <Route path="api-keys" element={<ApiKeys />} />
        <Route path="projects" element={<Projects />} />
        <Route path="projects/:pid" element={<ProjectDetail />} />
        <Route path="settings" element={<Settings />} />
        <Route path="billing" element={<Billing />} />
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
