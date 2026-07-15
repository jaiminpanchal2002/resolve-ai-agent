import React, { useState, useEffect } from "react";
import { 
  ArrowLeft, 
  Cpu, 
  Wrench, 
  ShieldAlert, 
  FileCheck, 
  MessageSquare, 
  DollarSign, 
  Clock, 
  Check, 
  X, 
  Edit3,
  ExternalLink,
  ChevronDown,
  ChevronUp
} from "lucide-react";

function TicketDetail({ ticketId, goBack }) {
  const [ticket, setTicket] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // Human Review form states
  const [reviewStatus, setReviewStatus] = useState("APPROVED"); // APPROVED, REJECTED, EDITED
  const [reviewFeedback, setReviewFeedback] = useState("");
  const [editedResolution, setEditedResolution] = useState("RESOLVED");
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [reviewSuccess, setReviewSuccess] = useState(false);

  // Tool Accordion states
  const [openTools, setOpenTools] = useState({});

  const fetchTicketDetails = async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api/tickets/${ticketId}`, {
        headers: {
          "Authorization": `Bearer ${localStorage.getItem("token")}`
        }
      });
      const data = await response.json();
      if (response.ok) {
        setTicket(data);
        // Default edited status to whatever the ticket currently has
        if (data.status) setEditedResolution(data.status);
      }
    } catch (err) {
      console.error("Error fetching ticket details", err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchTicketDetails();
  }, [ticketId]);

  const toggleTool = (toolId) => {
    setOpenTools(prev => ({
      ...prev,
      [toolId]: !prev[toolId]
    }));
  };

  const handleReviewSubmit = async (e) => {
    e.preventDefault();
    setReviewSubmitting(true);
    setReviewSuccess(false);

    try {
      const response = await fetch(`/api/tickets/${ticketId}/review`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${localStorage.getItem("token")}`
        },
        body: JSON.stringify({
          status: reviewStatus,
          feedback: reviewFeedback,
          edited_resolution: reviewStatus === "EDITED" ? editedResolution : null
        })
      });

      if (response.ok) {
        setReviewSuccess(true);
        fetchTicketDetails(); // Reload data
      } else {
        alert("Review submission failed");
      }
    } catch (err) {
      alert("Error contacting API");
    }
    setReviewSubmitting(false);
  };

  if (loading) {
    return <div style={{ textAlign: 'center', padding: '5rem', color: 'var(--text-secondary)' }}>Loading audit trace...</div>;
  }

  if (!ticket) {
    return <div style={{ textAlign: 'center', padding: '5rem', color: 'var(--danger)' }}>Ticket not found.</div>;
  }

  const latestRun = ticket.runs && ticket.runs[0];

  return (
    <div>
      {/* 1. Back button */}
      <button class="nav-btn" onClick={goBack} style={{ marginBottom: '1.5rem', paddingLeft: 0 }}>
        <ArrowLeft size={16} />
        Back to control queue
      </button>

      {/* 2. Top Info Bar */}
      <div class="glass-card" style={{ padding: '1.5rem', marginBottom: '2rem', display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>CASE AUDIT</span>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 700 }}>Ticket ID: {ticket.id}</h2>
          <div style={{ display: 'flex', gap: '0.8rem', marginTop: '0.5rem', alignItems: 'center' }}>
            <span class={`badge badge-${ticket.status.toLowerCase()}`}>{ticket.status}</span>
            {ticket.category && <span style={{ color: 'var(--primary)', fontWeight: 600, fontSize: '0.85rem' }}>{ticket.category}</span>}
            {ticket.severity && (
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Severity: <strong style={{ color: ticket.severity === 'HIGH' || ticket.severity === 'CRITICAL' ? 'var(--danger)' : 'inherit' }}>{ticket.severity}</strong>
              </span>
            )}
          </div>
        </div>

        {latestRun && (
          <div style={{ display: 'flex', gap: '1.5rem', borderLeft: '1px solid var(--border-color)', paddingLeft: '1.5rem' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
                <Clock size={12} /> LATENCY
              </div>
              <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>{(latestRun.latency_ms / 1000).toFixed(2)}s</div>
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
                <DollarSign size={12} /> RUN COST
              </div>
              <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--success)' }}>${latestRun.estimated_cost.toFixed(5)}</div>
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
                <Cpu size={12} /> MODEL
              </div>
              <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>{latestRun.model_name}</div>
            </div>
          </div>
        )}
      </div>

      {/* 3. Grid: Left Column (Chat + Review), Right Column (LangGraph execution flow) */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '2rem', alignItems: 'start' }}>
        
        {/* LEFT COLUMN: Customer inquiry & Review Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* Chat Messages */}
          <div class="glass-card" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <MessageSquare size={18} color="var(--primary)" />
              Customer Inquiry history
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {ticket.messages.map((m, idx) => (
                <div 
                  key={idx} 
                  style={{
                    alignSelf: m.sender === 'customer' ? 'flex-start' : 'flex-end',
                    background: m.sender === 'customer' ? 'rgba(99, 102, 241, 0.1)' : 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid',
                    borderColor: m.sender === 'customer' ? 'rgba(99, 102, 241, 0.15)' : 'var(--border-color)',
                    padding: '0.9rem 1.2rem',
                    borderRadius: '12px',
                    maxWidth: '85%',
                    fontSize: '0.9rem',
                    lineHeight: '1.4'
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: '0.75rem', color: m.sender === 'customer' ? 'var(--primary)' : 'var(--text-secondary)', marginBottom: '0.3rem', textTransform: 'uppercase' }}>
                    {m.sender}
                  </div>
                  {m.body}
                  <div style={{ textAlign: 'right', fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.4rem' }}>
                    {new Date(m.created_at).toLocaleTimeString()}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Human-in-the-Loop Review Panel */}
          <div class="glass-card" style={{ padding: '1.5rem', borderLeft: '3px solid var(--primary)' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              🛡️ Auditor Review Panel
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', marginBottom: '1.25rem' }}>
              Provide human feedback to validate, reject, or adjust the AI's autonomous decisions.
            </p>

            {ticket.human_review ? (
              <div style={{
                background: 'rgba(255, 255, 255, 0.03)',
                padding: '1rem',
                borderRadius: '8px',
                border: '1px solid var(--border-color)',
                fontSize: '0.85rem'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <strong>Review Status:</strong>
                  <span style={{
                    fontWeight: 'bold',
                    color: ticket.human_review.status === 'APPROVED' ? 'var(--success)' : 
                           ticket.human_review.status === 'REJECTED' ? 'var(--danger)' : 'var(--warning)'
                  }}>{ticket.human_review.status}</span>
                </div>
                {ticket.human_review.feedback && (
                  <div style={{ marginBottom: '0.5rem' }}>
                    <strong>Feedback:</strong> {ticket.human_review.feedback}
                  </div>
                )}
                <div>
                  <strong>Reviewed At:</strong> {new Date(ticket.human_review.reviewed_at).toLocaleString()}
                </div>
              </div>
            ) : (
              <form onSubmit={handleReviewSubmit}>
                {reviewSuccess && (
                  <div style={{ background: 'rgba(16, 185, 129, 0.1)', color: 'var(--success)', padding: '0.6rem', borderRadius: '6px', fontSize: '0.85rem', marginBottom: '1rem' }}>
                    Review submitted successfully!
                  </div>
                )}

                {/* Review Choice */}
                <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
                  <button 
                    type="button" 
                    class={`nav-btn ${reviewStatus === "APPROVED" ? "active" : ""}`} 
                    style={{ flex: 1, justifyContent: 'center', padding: '0.5rem' }}
                    onClick={() => setReviewStatus("APPROVED")}
                  >
                    <Check size={16} color="var(--success)" /> Approve
                  </button>
                  <button 
                    type="button" 
                    class={`nav-btn ${reviewStatus === "REJECTED" ? "active" : ""}`} 
                    style={{ flex: 1, justifyContent: 'center', padding: '0.5rem' }}
                    onClick={() => setReviewStatus("REJECTED")}
                  >
                    <X size={16} color="var(--danger)" /> Reject
                  </button>
                  <button 
                    type="button" 
                    class={`nav-btn ${reviewStatus === "EDITED" ? "active" : ""}`} 
                    style={{ flex: 1, justifyContent: 'center', padding: '0.5rem' }}
                    onClick={() => setReviewStatus("EDITED")}
                  >
                    <Edit3 size={16} color="var(--warning)" /> Edit
                  </button>
                </div>

                {/* Edit Controls */}
                {reviewStatus === "EDITED" && (
                  <div style={{ marginBottom: '1rem', background: 'rgba(0,0,0,0.1)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                    <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                      Correct Resolution Status
                    </label>
                    <select 
                      class="form-input" 
                      value={editedResolution} 
                      onChange={(e) => setEditedResolution(e.target.value)}
                    >
                      <option value="RESOLVED">RESOLVED (Apply Fixes / Refund)</option>
                      <option value="ESCALATED">ESCALATED (Route to Human Agent)</option>
                      <option value="OPEN">OPEN (Keep Active)</option>
                    </select>
                  </div>
                )}

                <div style={{ marginBottom: '1.25rem' }}>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                    Auditor Notes & Feedback
                  </label>
                  <textarea
                    class="form-input"
                    rows={3}
                    placeholder="Enter compliance reasons or details for rejection..."
                    value={reviewFeedback}
                    onChange={(e) => setReviewFeedback(e.target.value)}
                  />
                </div>

                <button type="submit" class="btn" style={{ width: '100%', justifyContent: 'center' }} disabled={reviewSubmitting}>
                  Submit Review Decision
                </button>
              </form>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: LangGraph execution trace */}
        <div class="glass-card" style={{ padding: '2rem' }}>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Cpu size={20} color="var(--primary)" />
            AI Execution Trace (LangGraph Node Sequence)
          </h3>

          {!latestRun ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
              No execution trace available for this ticket yet.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', position: 'relative' }}>
              
              {/* Vertical line connecting nodes */}
              <div style={{
                position: 'absolute',
                left: '20px',
                top: '15px',
                bottom: '15px',
                width: '2px',
                background: 'rgba(99, 102, 241, 0.15)',
                zIndex: 1
              }}></div>

              {/* NODE 1: Classify */}
              <div style={{ display: 'flex', gap: '1.25rem', zIndex: 2 }}>
                <div style={{ width: '42px', height: '42px', borderRadius: '50%', background: '#6366F1', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#FFF', fontWeight: 'bold' }}>
                  1
                </div>
                <div style={{ flex: 1, background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <strong style={{ fontSize: '0.95rem' }}>Intent Classification Node</strong>
                    <span class="badge badge-resolved" style={{ fontSize: '0.7rem' }}>COMPLETED</span>
                  </div>
                  {latestRun.decision ? (
                    <div style={{ fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.25rem', color: 'var(--text-secondary)' }}>
                      <div><strong>Category:</strong> <span style={{ color: 'var(--text-main)' }}>{ticket.category}</span></div>
                      <div><strong>Intent:</strong> <span style={{ color: 'var(--text-main)' }}>{ticket.intent}</span></div>
                      <div><strong>Severity:</strong> <span style={{ color: 'var(--danger)' }}>{ticket.severity}</span></div>
                    </div>
                  ) : (
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Classification metadata parsed.</span>
                  )}
                </div>
              </div>

              {/* NODE 2: Plan */}
              <div style={{ display: 'flex', gap: '1.25rem', zIndex: 2 }}>
                <div style={{ width: '42px', height: '42px', borderRadius: '50%', background: '#8B5CF6', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#FFF', fontWeight: 'bold' }}>
                  2
                </div>
                <div style={{ flex: 1, background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <strong style={{ fontSize: '0.95rem' }}>Planner Node</strong>
                    <span class="badge badge-resolved" style={{ fontSize: '0.7rem' }}>COMPLETED</span>
                  </div>
                  
                  {/* Step list */}
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                    <div style={{ fontWeight: 600, color: 'var(--text-main)', marginBottom: '0.4rem' }}>Formulated Resolution Plan:</div>
                    <ol style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                      <li>Determine customer verification status</li>
                      <li>Fetch associated order records</li>
                      <li>Verify shipment delivery proof & signature</li>
                      <li>Validate transaction logs for double charges</li>
                      <li>Enforce policies & generate compliant outcome</li>
                    </ol>
                  </div>
                </div>
              </div>

              {/* NODE 3: Tool Execution */}
              <div style={{ display: 'flex', gap: '1.25rem', zIndex: 2 }}>
                <div style={{ width: '42px', height: '42px', borderRadius: '50%', background: '#EC4899', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#FFF', fontWeight: 'bold' }}>
                  3
                </div>
                <div style={{ flex: 1, background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.8rem' }}>
                    <strong style={{ fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <Wrench size={16} />
                      Tool Executor Node
                    </strong>
                    <span class="badge badge-resolved" style={{ fontSize: '0.7rem' }}>COMPLETED</span>
                  </div>

                  {latestRun.tool_calls.length === 0 ? (
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>No tools called during execution.</div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                      {latestRun.tool_calls.map((tc) => (
                        <div key={tc.id} style={{ border: '1px solid rgba(255,255,255,0.05)', borderRadius: '6px', overflow: 'hidden' }}>
                          <button 
                            type="button"
                            onClick={() => toggleTool(tc.id)}
                            style={{
                              width: '100%',
                              background: 'rgba(255,255,255,0.02)',
                              border: 'none',
                              color: 'var(--text-main)',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              padding: '0.6rem 0.8rem',
                              fontFamily: 'inherit',
                              fontSize: '0.8rem',
                              fontWeight: 600,
                              cursor: 'pointer'
                            }}
                          >
                            <span style={{ color: 'var(--secondary)' }}>
                              {tc.tool_name}({Object.keys(tc.input).join(", ")})
                            </span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{tc.latency_ms}ms</span>
                              {openTools[tc.id] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            </div>
                          </button>
                          
                          {openTools[tc.id] && (
                            <div style={{ padding: '0.8rem', background: '#070A13', borderTop: '1px solid rgba(255,255,255,0.05)', fontSize: '0.75rem', fontFamily: 'monospace', overflowX: 'auto' }}>
                              <div style={{ color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>// Input Arguments:</div>
                              <pre style={{ color: '#818CF8', marginBottom: '0.6rem' }}>{JSON.stringify(tc.input, null, 2)}</pre>
                              <div style={{ color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>// Returned Payload:</div>
                              <pre style={{ color: '#10B981' }}>{JSON.stringify(tc.output, null, 2)}</pre>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* NODE 4: Guardrails */}
              <div style={{ display: 'flex', gap: '1.25rem', zIndex: 2 }}>
                <div style={{ width: '42px', height: '42px', borderRadius: '50%', background: '#F59E0B', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#FFF', fontWeight: 'bold' }}>
                  4
                </div>
                <div style={{ flex: 1, background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <strong style={{ fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <ShieldAlert size={16} />
                      Guardrails & Compliance Node
                    </strong>
                    <span class="badge badge-resolved" style={{ fontSize: '0.7rem' }}>COMPLETED</span>
                  </div>
                  
                  {/* Violations or Clean */}
                  {latestRun.decision && latestRun.decision.evidence.some(e => e.includes("exceeds") || e.includes("POL-") || e.includes("missing")) ? (
                    <div style={{
                      background: 'rgba(239, 68, 68, 0.08)',
                      border: '1px solid rgba(239, 68, 68, 0.2)',
                      color: '#FCA5A5',
                      padding: '0.8rem',
                      borderRadius: '6px',
                      fontSize: '0.8rem'
                    }}>
                      <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Guardrail Intercept Action:</div>
                      {latestRun.decision.evidence.filter(e => e.includes("exceeds") || e.includes("POL-") || e.includes("missing")).map((e, idx) => (
                        <div key={idx} style={{ marginTop: '0.2rem' }}>⚠️ {e}</div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ color: 'var(--success)', fontSize: '0.8rem' }}>
                      ✓ All deterministic business rules validated. No policy violations.
                    </div>
                  )}
                </div>
              </div>

              {/* NODE 5: Final Response */}
              <div style={{ display: 'flex', gap: '1.25rem', zIndex: 2 }}>
                <div style={{ width: '42px', height: '42px', borderRadius: '50%', background: '#10B981', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#FFF', fontWeight: 'bold' }}>
                  5
                </div>
                <div style={{ flex: 1, background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem' }}>
                  <div style={{ display: 'flex', justifySelf: 'stretch', justifyContent: 'space-between', marginBottom: '0.5rem', width: '100%' }}>
                    <strong style={{ fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <FileCheck size={16} />
                      Response Generator Node
                    </strong>
                    <span class="badge badge-resolved" style={{ fontSize: '0.7rem' }}>COMPLETED</span>
                  </div>

                  {latestRun.decision ? (
                    <div style={{ fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                      <div>
                        <strong>Autonomous Resolution:</strong>{" "}
                        <span class={`badge ${latestRun.decision.resolution === 'RESOLVED' ? 'badge-resolved' : 'badge-escalated'}`}>
                          {latestRun.decision.resolution}
                        </span>
                      </div>
                      
                      <div>
                        <strong>Reasoning:</strong>
                        <div style={{ color: 'var(--text-secondary)', marginTop: '0.2rem', lineHeight: '1.4' }}>
                          {latestRun.decision.reason}
                        </div>
                      </div>

                      {latestRun.decision.evidence.length > 0 && (
                        <div>
                          <strong>Extracted Evidence:</strong>
                          <ul style={{ paddingLeft: '1.2rem', color: 'var(--text-secondary)', marginTop: '0.2rem', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                            {latestRun.decision.evidence.map((ev, idx) => (
                              <li key={idx}>{ev}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {latestRun.decision.actions_taken.length > 0 && (
                        <div>
                          <strong>Executed Actions:</strong>
                          <ul style={{ paddingLeft: '1.2rem', color: 'var(--text-secondary)', marginTop: '0.2rem', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                            {latestRun.decision.actions_taken.map((act, idx) => (
                              <li key={idx} style={{ color: '#A7F3D0' }}>✓ {act}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ) : (
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Failed to compile final response.</span>
                  )}
                </div>
              </div>

            </div>
          )}
        </div>

      </div>
    </div>
  );
}

export default TicketDetail;
