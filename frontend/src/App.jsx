import React, { useState, useEffect } from "react";
import Dashboard from "./components/Dashboard.jsx";
import TicketDetail from "./components/TicketDetail.jsx";
import EvaluationSuite from "./components/EvaluationSuite.jsx";
import Auth from "./components/Auth.jsx";
import { ShieldCheck, LayoutDashboard, BarChart3, LogOut, Ticket } from "lucide-react";

function App() {
  const [token, setToken] = useState(localStorage.getItem("token") || "");
  const [role, setRole] = useState(localStorage.getItem("role") || "");
  const [view, setView] = useState("dashboard"); // dashboard, ticket, evaluations
  const [selectedTicketId, setSelectedTicketId] = useState(null);

  useEffect(() => {
    if (token) {
      localStorage.setItem("token", token);
      localStorage.setItem("role", role);
    } else {
      localStorage.removeItem("token");
      localStorage.removeItem("role");
    }
  }, [token, role]);

  const handleLogout = () => {
    setToken("");
    setRole("");
    setView("dashboard");
    setSelectedTicketId(null);
  };

  const navigateToTicket = (ticketId) => {
    setSelectedTicketId(ticketId);
    setView("ticket");
  };

  if (!token) {
    return <Auth setToken={setToken} setRole={setRole} />;
  }

  return (
    <div class="app-container">
      <header>
        <div class="logo-container">
          <span class="logo-icon">🛡️</span>
          <span class="logo-text">ResolveAI Control Center</span>
          <span style={{
            fontSize: '0.75rem',
            background: 'rgba(99, 102, 241, 0.2)',
            color: '#818CF8',
            padding: '2px 8px',
            borderRadius: '12px',
            textTransform: 'uppercase',
            fontWeight: 'bold',
            marginLeft: '5px'
          }}>{role}</span>
        </div>
        <div class="nav-links">
          <button 
            class={`nav-btn ${view === "dashboard" ? "active" : ""}`}
            onClick={() => { setView("dashboard"); setSelectedTicketId(null); }}
          >
            <LayoutDashboard size={18} />
            Queue & Metrics
          </button>
          <button 
            class={`nav-btn ${view === "evaluations" ? "active" : ""}`}
            onClick={() => { setView("evaluations"); setSelectedTicketId(null); }}
          >
            <BarChart3 size={18} />
            Evaluation Suite
          </button>
          {selectedTicketId && (
            <button class="nav-btn active">
              <Ticket size={18} />
              Ticket: {selectedTicketId}
            </button>
          )}
          <button class="nav-btn" onClick={handleLogout} style={{ color: '#F87171' }}>
            <LogOut size={18} />
            Sign Out
          </button>
        </div>
      </header>

      <main>
        {view === "dashboard" && <Dashboard navigateToTicket={navigateToTicket} />}
        {view === "ticket" && (
          <TicketDetail 
            ticketId={selectedTicketId} 
            goBack={() => setView("dashboard")} 
          />
        )}
        {view === "evaluations" && <EvaluationSuite />}
      </main>
    </div>
  );
}

export default App;
