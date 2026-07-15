import React, { useState, useEffect } from "react";
import { 
  BarChart2, 
  Play, 
  RefreshCw, 
  HelpCircle, 
  CheckCircle2, 
  AlertTriangle,
  Layers,
  Search,
  DollarSign,
  Clock
} from "lucide-react";

function EvaluationSuite() {
  const [runs, setRuns] = useState([]);
  const [comparisonData, setComparisonData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [runningEval, setRunningEval] = useState(false);

  const fetchEvalData = async () => {
    setLoading(true);
    try {
      const headers = {
        "Authorization": `Bearer ${localStorage.getItem("token")}`
      };
      
      // Fetch runs
      const runsResp = await fetch("/api/evaluations/runs", { headers });
      const runsData = await runsResp.json();
      if (runsResp.ok) setRuns(runsData);

      // Fetch retrieval comparison stats
      const compResp = await fetch("/api/evaluations/retrieval-comparison", { headers });
      const compData = await compResp.json();
      if (compResp.ok) setComparisonData(compData.metrics || []);
    } catch (err) {
      console.error("Error fetching evaluations data", err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchEvalData();
  }, []);

  const handleTriggerEval = async () => {
    setRunningEval(true);
    try {
      const response = await fetch("/api/evaluations/run?dataset_id=1", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${localStorage.getItem("token")}`
        }
      });
      const data = await response.json();
      if (response.ok) {
        alert("Batch evaluation triggered successfully!");
        fetchEvalData(); // Refresh list to show pending
      } else {
        alert(data.detail || "Failed to trigger evaluation");
      }
    } catch (err) {
      alert("Error contacting API");
    }
    setRunningEval(false);
  };

  return (
    <div>
      {/* 1. Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 700, letterSpacing: '-0.5px' }}>Evaluation Engine</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Run offline batch evaluations against 100+ synthetic cases to audit model performance changes.</p>
        </div>
        <div style={{ display: 'flex', gap: '0.8rem' }}>
          <button class="btn btn-secondary" onClick={fetchEvalData}>
            <RefreshCw size={16} />
            Sync Logs
          </button>
          <button class="btn" onClick={handleTriggerEval} disabled={runningEval}>
            <Play size={16} />
            {runningEval ? "Triggering..." : "Run Batch Evaluation (100 Cases)"}
          </button>
        </div>
      </div>

      {/* 2. RAG Retrieval Performance Benchmark Comparison (pgvector) */}
      <div class="glass-card" style={{ padding: '2rem', marginBottom: '2.5rem' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Layers size={20} color="var(--primary)" />
          pgvector Hybrid Retrieval & Reranker Benchmarks
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
          Compare vector similarity search versus Reciprocal Rank Fusion (RRF) and Cross-Encoder model reranking. Metrics are measured dynamically using actual execution tests.
        </p>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>
                <th style={{ padding: '0.8rem' }}>Retrieval Strategy</th>
                <th style={{ padding: '0.8rem' }}>Recall@5</th>
                <th style={{ padding: '0.8rem' }}>Mean Reciprocal Rank (MRR)</th>
                <th style={{ padding: '0.8rem', textAlign: 'right' }}>Search Latency (ms)</th>
              </tr>
            </thead>
            <tbody>
              {comparisonData.map((row, idx) => (
                <tr 
                  key={idx} 
                  style={{ 
                    borderBottom: '1px solid var(--border-color)',
                    background: idx === 2 ? 'rgba(99, 102, 241, 0.05)' : 'transparent',
                    fontWeight: idx === 2 ? 'bold' : 'normal'
                  }}
                >
                  <td style={{ padding: '1rem 0.8rem' }}>
                    {idx === 2 ? "⭐ " : ""}{row.method}
                  </td>
                  <td style={{ padding: '1rem 0.8rem', color: row.recall_at_5 > 0.9 ? 'var(--success)' : 'inherit' }}>
                    {(row.recall_at_5 * 100).toFixed(0)}%
                  </td>
                  <td style={{ padding: '1rem 0.8rem' }}>
                    {row.mrr.toFixed(2)}
                  </td>
                  <td style={{ padding: '1rem 0.8rem', textAlign: 'right', color: row.latency_ms > 30 ? 'var(--warning)' : 'inherit' }}>
                    {row.latency_ms.toFixed(1)} ms
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 3. Offline Evaluation Runs */}
      <div class="glass-card" style={{ padding: '2rem' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1.5rem' }}>Evaluation History Logs</h2>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>Loading history logs...</div>
        ) : runs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
            No evaluation runs completed yet. Click "Run Batch Evaluation" above to trigger a test run.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {runs.map((run) => (
              <div 
                key={run.id} 
                style={{
                  border: '1px solid var(--border-color)',
                  borderRadius: '10px',
                  padding: '1.5rem',
                  background: 'rgba(255, 255, 255, 0.01)'
                }}
              >
                {/* Header of Run Card */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem', marginBottom: '1rem' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                      <span style={{ fontSize: '1.1rem', fontWeight: 600 }}>Run ID: #{run.id}</span>
                      <span class={`badge ${run.completed_at ? 'badge-resolved' : 'badge-pending'}`}>
                        {run.completed_at ? "Completed" : "Running"}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.3rem' }}>
                      Model under test: <strong>{run.model_name}</strong> | Started at: {new Date(run.started_at).toLocaleString()}
                    </div>
                  </div>
                  {run.completed_at && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textAlign: 'right' }}>
                      Duration: {((new Date(run.completed_at) - new Date(run.started_at)) / 1000).toFixed(1)}s
                    </div>
                  )}
                </div>

                {/* Metrics detail */}
                {run.summary_metrics ? (
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                    gap: '1.25rem'
                  }}>
                    {/* Intent Accuracy */}
                    <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.03)' }}>
                      <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', fontWeight: 500 }}>Intent Accuracy</div>
                      <div style={{ fontSize: '1.4rem', fontWeight: 700, margin: '2px 0', color: 'var(--success)' }}>
                        {(run.summary_metrics.intent_accuracy * 100).toFixed(1)}%
                      </div>
                    </div>

                    {/* Tool Selection */}
                    <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.03)' }}>
                      <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', fontWeight: 500 }}>Tool Selection Match</div>
                      <div style={{ fontSize: '1.4rem', fontWeight: 700, margin: '2px 0', color: 'var(--primary)' }}>
                        {(run.summary_metrics.tool_selection_accuracy * 100).toFixed(1)}%
                      </div>
                    </div>

                    {/* Policy Citation */}
                    <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.03)' }}>
                      <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', fontWeight: 500 }}>Policy Citation Match</div>
                      <div style={{ fontSize: '1.4rem', fontWeight: 700, margin: '2px 0', color: '#38BDF8' }}>
                        {(run.summary_metrics.policy_citation_accuracy * 100).toFixed(1)}%
                      </div>
                    </div>

                    {/* Escalation Precision / Recall */}
                    <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.03)' }}>
                      <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', fontWeight: 500 }}>Escalation Precision/Recall</div>
                      <div style={{ fontSize: '1.1rem', fontWeight: 700, margin: '5px 0' }}>
                        P: {(run.summary_metrics.escalation_precision * 100).toFixed(0)}% | R: {(run.summary_metrics.escalation_recall * 100).toFixed(0)}%
                      </div>
                    </div>

                    {/* Avg Latency & Cost */}
                    <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.03)' }}>
                      <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', fontWeight: 500 }}>Avg Latency & Cost</div>
                      <div style={{ fontSize: '1.1rem', fontWeight: 700, margin: '5px 0' }}>
                        {(run.summary_metrics.average_latency_ms / 1000).toFixed(2)}s | ${run.summary_metrics.average_cost.toFixed(4)}
                      </div>
                    </div>

                  </div>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--warning)', fontSize: '0.85rem' }}>
                    <AlertTriangle size={16} />
                    Evaluation is executing. Summary metrics will show up upon completion...
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  );
}

export default EvaluationSuite;
