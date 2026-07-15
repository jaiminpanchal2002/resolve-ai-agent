import React, { useState, useEffect } from "react";
import { 
  Play, 
  RefreshCw, 
  Search, 
  TrendingUp, 
  AlertTriangle, 
  CheckCircle, 
  DollarSign, 
  Clock, 
  PlusCircle,
  HelpCircle,
  FileText
} from "lucide-react";

function Dashboard({ navigateToTicket }) {
  const [metrics, setMetrics] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  
  // Ticket Ingestion Simulator state
  const [simCustomerId, setSimCustomerId] = useState("CUS-10001");
  const [simCustomerName, setSimCustomerName] = useState("Jane Doe");
  const [simMessage, setSimMessage] = useState("My laptop shows delivered but I haven't received it. It was ₹82,000.");
  const [asyncRun, setAsyncRun] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [simResult, setSimResult] = useState(null);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const headers = {
        "Authorization": `Bearer ${localStorage.getItem("token")}`
      };
      
      // Fetch metrics
      const mResp = await fetch("/api/dashboard/metrics", { headers });
      const mData = await mResp.json();
      if (mResp.ok) setMetrics(mData);

      // Fetch tickets
      const url = statusFilter ? `/api/tickets?status_filter=${statusFilter}` : "/api/tickets";
      const tResp = await fetch(url, { headers });
      const tData = await tResp.json();
      if (tResp.ok) setTickets(tData);
    } catch (err) {
      console.error("Error fetching dashboard data", err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchDashboardData();
  }, [statusFilter]);

  const handleSimulate = async (e) => {
    e.preventDefault();
    setSimulating(true);
    setSimResult(null);

    try {
      const response = await fetch(`/api/tickets?async_run=${asyncRun}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${localStorage.getItem("token")}`
        },
        body: JSON.stringify({
          customer_id: simCustomerId,
          customer_name: simCustomerName,
          messages: [
            {
              sender: "customer",
              body: simMessage
            }
          ]
        })
      });

      const data = await response.json();
      if (response.ok) {
        setSimResult(data);
        fetchDashboardData(); // Refresh list
      } else {
        alert(data.detail || "Simulation failed");
      }
    } catch (err) {
      alert("Error contacting API");
    }
    setSimulating(false);
  };

  const getSeverityStyle = (sev) => {
    if (!sev) return "";
    switch(sev.toUpperCase()) {
      case "CRITICAL":
      case "HIGH":
        return "severity-high";
      case "MEDIUM":
        return "severity-medium";
      default:
        return "severity-low";
    }
  };

  return (
    <div>
      {/* 1. Header and Refresh */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 700, letterSpacing: '-0.5px' }}>Operations Control</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Real-time agent performance tracking and human audit queue.</p>
        </div>
        <button class="btn btn-secondary" onClick={fetchDashboardData}>
          <RefreshCw size={16} />
          Refresh Stats
        </button>
      </div>

      {/* 2. Metrics Grid */}
      {metrics && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '1.25rem',
          marginBottom: '2.5rem'
        }}>
          {/* Resolution Rate Card */}
          <div class="glass-card" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ background: 'rgba(16, 185, 129, 0.15)', padding: '0.8rem', borderRadius: '10px', color: 'var(--success)' }}>
              <CheckCircle size={24} />
            </div>
            <div>
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 500 }}>Auto-Resolution Rate</div>
              <div style={{ fontSize: '1.6rem', fontWeight: 700, margin: '2px 0' }}>
                {(metrics.resolution_rate * 100).toFixed(1)}%
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Direct client self-solve</div>
            </div>
          </div>

          {/* Escalation Rate Card */}
          <div class="glass-card" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ background: 'rgba(239, 68, 68, 0.15)', padding: '0.8rem', borderRadius: '10px', color: 'var(--danger)' }}>
              <AlertTriangle size={24} />
            </div>
            <div>
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 500 }}>Escalation Rate</div>
              <div style={{ fontSize: '1.6rem', fontWeight: 700, margin: '2px 0' }}>
                {(metrics.escalation_rate * 100).toFixed(1)}%
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Routed to expert review</div>
            </div>
          </div>

          {/* Human Approval Card */}
          <div class="glass-card" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ background: 'rgba(99, 102, 241, 0.15)', padding: '0.8rem', borderRadius: '10px', color: 'var(--primary)' }}>
              <TrendingUp size={24} />
            </div>
            <div>
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 500 }}>Human Approval Rate</div>
              <div style={{ fontSize: '1.6rem', fontWeight: 700, margin: '2px 0' }}>
                {(metrics.human_approval_rate * 100).toFixed(1)}%
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Auditor compliance agreement</div>
            </div>
          </div>

          {/* Average Cost Card */}
          <div class="glass-card" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ background: 'rgba(168, 85, 247, 0.15)', padding: '0.8rem', borderRadius: '10px', color: 'var(--secondary)' }}>
              <DollarSign size={24} />
            </div>
            <div>
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 500 }}>Avg Cost / Ticket</div>
              <div style={{ fontSize: '1.6rem', fontWeight: 700, margin: '2px 0' }}>
                ₹{(metrics.average_cost_per_ticket * 83.5).toFixed(3)}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                ${metrics.average_cost_per_ticket.toFixed(4)}
              </div>
            </div>
          </div>

          {/* P95 Latency Card */}
          <div class="glass-card" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ background: 'rgba(245, 158, 11, 0.15)', padding: '0.8rem', borderRadius: '10px', color: 'var(--warning)' }}>
              <Clock size={24} />
            </div>
            <div>
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 500 }}>P95 Resolution Time</div>
              <div style={{ fontSize: '1.6rem', fontWeight: 700, margin: '2px 0' }}>
                {(metrics.p95_latency_ms / 1000).toFixed(2)}s
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                {metrics.p95_latency_ms.toFixed(0)} ms total
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 3. Columns: Left side simulator, Right side queue */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '2rem', alignItems: 'start' }}>
        
        {/* Left Column: Simulator */}
        <div class="glass-card" style={{ padding: '2rem' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <PlusCircle size={20} color="var(--primary)" />
            Ticket Simulator
          </h2>
          
          <form onSubmit={handleSimulate}>
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                Customer ID
              </label>
              <select 
                class="form-input" 
                value={simCustomerId} 
                onChange={(e) => setSimCustomerId(e.target.value)}
              >
                <option value="CUS-10001">CUS-10001 (High Value order ORD-20001 available)</option>
                <option value="CUS-10002">CUS-10002 (Duplicate charge ORD-20002 available)</option>
                <option value="CUS-10003">CUS-10003 (Standard order ORD-20003 available)</option>
                <option value="CUS-NEW">CUS-NEW (Create fresh profile)</option>
              </select>
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                Customer Name
              </label>
              <input
                type="text"
                class="form-input"
                value={simCustomerName}
                onChange={(e) => setSimCustomerName(e.target.value)}
              />
            </div>

            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                Customer Inquiry
              </label>
              <textarea
                class="form-input"
                rows={4}
                style={{ resize: 'vertical' }}
                value={simMessage}
                onChange={(e) => setSimMessage(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.5rem' }}>
              <input
                type="checkbox"
                id="async_checkbox"
                checked={asyncRun}
                onChange={(e) => setAsyncRun(e.target.checked)}
                style={{ width: '16px', height: '16px', cursor: 'pointer' }}
              />
              <label htmlFor="async_checkbox" style={{ fontSize: '0.85rem', cursor: 'pointer', userSelect: 'none' }}>
                Run asynchronously in background (Celery)
              </label>
            </div>

            <button type="submit" class="btn" style={{ width: '100%', justifyContent: 'center' }} disabled={simulating}>
              <Play size={16} />
              {simulating ? "Executing Agent Graph..." : "Inject Support Ticket"}
            </button>
          </form>

          {/* Simulation outcome indicator */}
          {simResult && (
            <div style={{
              marginTop: '1.5rem',
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              padding: '1rem',
              fontSize: '0.85rem'
            }}>
              <div style={{ fontWeight: 600, color: 'var(--primary)', marginBottom: '0.5rem' }}>
                Simulation Results
              </div>
              <div style={{ marginBottom: '0.4rem' }}>
                <strong>Ticket ID:</strong> {simResult.ticket_id}
              </div>
              <div>
                <strong>Status:</strong>{" "}
                <span class={`badge ${simResult.status === 'COMPLETED' ? 'badge-resolved' : 'badge-pending'}`}>
                  {simResult.status}
                </span>
              </div>
              {simResult.agent_run && (
                <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                  <div><strong>Resolution:</strong> {simResult.agent_run.resolution}</div>
                  <div><strong>Reason:</strong> {simResult.agent_run.reason}</div>
                  <button 
                    class="btn btn-secondary" 
                    onClick={() => navigateToTicket(simResult.ticket_id)}
                    style={{ padding: '0.4rem 0.8rem', fontSize: '0.75rem', marginTop: '0.5rem', width: '100%', justifyContent: 'center' }}
                  >
                    <FileText size={12} />
                    View Detailed Audit Trace
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column: Ticket Queue */}
        <div class="glass-card" style={{ padding: '2rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Active Audit Queue</h2>
            
            {/* Status Filter */}
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button 
                class={`nav-btn ${statusFilter === "" ? "active" : ""}`} 
                onClick={() => setStatusFilter("")}
                style={{ fontSize: '0.8rem', padding: '0.3rem 0.6rem' }}
              >
                All
              </button>
              <button 
                class={`nav-btn ${statusFilter === "OPEN" ? "active" : ""}`} 
                onClick={() => setStatusFilter("OPEN")}
                style={{ fontSize: '0.8rem', padding: '0.3rem 0.6rem' }}
              >
                Open
              </button>
              <button 
                class={`nav-btn ${statusFilter === "RESOLVED" ? "active" : ""}`} 
                onClick={() => setStatusFilter("RESOLVED")}
                style={{ fontSize: '0.8rem', padding: '0.3rem 0.6rem' }}
              >
                Resolved
              </button>
              <button 
                class={`nav-btn ${statusFilter === "ESCALATED" ? "active" : ""}`} 
                onClick={() => setStatusFilter("ESCALATED")}
                style={{ fontSize: '0.8rem', padding: '0.3rem 0.6rem' }}
              >
                Escalated
              </button>
            </div>
          </div>

          {loading ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
              Loading audit queue...
            </div>
          ) : tickets.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
              No tickets found matching the criteria.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>
                    <th style={{ padding: '0.8rem' }}>Ticket ID</th>
                    <th style={{ padding: '0.8rem' }}>Customer ID</th>
                    <th style={{ padding: '0.8rem' }}>Category</th>
                    <th style={{ padding: '0.8rem' }}>Intent</th>
                    <th style={{ padding: '0.8rem' }}>Severity</th>
                    <th style={{ padding: '0.8rem' }}>Resolution</th>
                    <th style={{ padding: '0.8rem', textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {tickets.map((ticket) => (
                    <tr 
                      key={ticket.id} 
                      style={{ 
                        borderBottom: '1px solid var(--border-color)',
                        background: ticket.human_review_status ? 'rgba(255, 255, 255, 0.01)' : 'transparent',
                        transition: 'background 0.2s'
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)'}
                      onMouseLeave={(e) => e.currentTarget.style.background = ticket.human_review_status ? 'rgba(255, 255, 255, 0.01)' : 'transparent'}
                    >
                      <td style={{ padding: '1rem 0.8rem', fontWeight: 600 }}>{ticket.id}</td>
                      <td style={{ padding: '1rem 0.8rem', color: 'var(--text-secondary)' }}>{ticket.customer_id}</td>
                      <td style={{ padding: '1rem 0.8rem' }}>
                        {ticket.category ? (
                          <span style={{ fontSize: '0.8rem', color: '#818CF8', fontWeight: 500 }}>
                            {ticket.category}
                          </span>
                        ) : "-"}
                      </td>
                      <td style={{ padding: '1rem 0.8rem', fontSize: '0.85rem' }}>{ticket.intent || "-"}</td>
                      <td style={{ padding: '1rem 0.8rem' }}>
                        {ticket.severity ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <span class={`severity-dot ${getSeverityStyle(ticket.severity)}`}></span>
                            <span style={{ fontSize: '0.8rem' }}>{ticket.severity}</span>
                          </div>
                        ) : "-"}
                      </td>
                      <td style={{ padding: '1rem 0.8rem' }}>
                        <span class={`badge badge-${ticket.status.toLowerCase()}`}>
                          {ticket.status}
                        </span>
                      </td>
                      <td style={{ padding: '1rem 0.8rem', textAlign: 'right' }}>
                        <button 
                          class="btn btn-secondary" 
                          style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                          onClick={() => navigateToTicket(ticket.id)}
                        >
                          Audit Trace
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
