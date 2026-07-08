import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/lib/auth";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import AuditView from "@/pages/AuditView";
import Ledger from "@/pages/Ledger";
import AuthCallback from "@/pages/AuthCallback";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen bg-black text-[#808080] mono text-xs p-8 ae-cursor">CHECKING SESSION</div>;
  if (!user) return <Navigate to="/" replace />;
  return children;
}

function RouterShell() {
  const location = useLocation();
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <Routes>
      <Route path="/" element={<Login />} />
      <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
      <Route path="/ledger" element={<Protected><Ledger /></Protected>} />
      <Route path="/audits/:id" element={<Protected><AuditView /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <RouterShell />
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}
