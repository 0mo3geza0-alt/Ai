import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AppProvider, useApp } from "@/context/AppContext";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import DashboardLayout from "@/pages/DashboardLayout";
import DashboardHome from "@/pages/DashboardHome";
import Chat from "@/pages/Chat";
import TextStudio from "@/pages/TextStudio";
import ImageStudio from "@/pages/ImageStudio";
import History from "@/pages/History";
import Settings from "@/pages/Settings";

function Loader() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#05050A]">
      <div className="flex gap-2"><span className="dot" /><span className="dot" /><span className="dot" /></div>
    </div>
  );
}

function Protected({ children }) {
  const { user } = useApp();
  if (user === null) return <Loader />;
  if (user === false) return <Navigate to="/login" replace />;
  return children;
}

function Guest({ children }) {
  const { user } = useApp();
  if (user === null) return <Loader />;
  if (user) return <Navigate to="/app" replace />;
  return children;
}

function App() {
  return (
    <div className="App grain">
      <AppProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Guest><Login /></Guest>} />
            <Route path="/register" element={<Guest><Register /></Guest>} />
            <Route path="/app" element={<Protected><DashboardLayout /></Protected>}>
              <Route index element={<DashboardHome />} />
              <Route path="chat" element={<Chat />} />
              <Route path="text" element={<TextStudio />} />
              <Route path="image" element={<ImageStudio />} />
              <Route path="history" element={<History />} />
              <Route path="settings" element={<Settings />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster position="top-center" theme="dark" richColors />
      </AppProvider>
    </div>
  );
}

export default App;
