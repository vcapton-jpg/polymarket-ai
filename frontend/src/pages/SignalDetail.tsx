import { useParams, Link } from "react-router-dom"
import { useState, useEffect } from "react"


function SignalDetail() {
  const { id } = useParams()
  const [signal, setSignal] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`/api/signals/${id}`)
      .then((res) => res.json())
      .then(setSignal)
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="loading">Loading...</div>

  return (
    <div className="signal-detail">
      <Link to="/dashboard" className="back-link">← Back to Dashboard</Link>

      <div className="detail-header">
        <span className={`direction-badge ${signal?.direction === "YES" ? "buy-yes" : "buy-no"}`}>
          {signal?.direction === "YES" ? "🟢 BUY YES" : "🔴 BUY NO"}
        </span>
        <h1>{signal?.score}/100</h1>
      </div>

      <div className="detail-card">
        <h2>{signal?.question}</h2>

        <div className="detail-grid">
          <div className="detail-item">
            <label>Confidence</label>
            <span>{signal?.confidence_label}</span>
          </div>
          <div className="detail-item">
            <label>Urgency</label>
            <span>{signal?.urgency_label}</span>
          </div>
          <div className="detail-item">
            <label>Tradability</label>
            <span>{signal?.tradability_label}</span>
          </div>
          <div className="detail-item">
            <label>Price at Signal</label>
            <span>${signal?.market_price_at_signal}</span>
          </div>
        </div>

        {signal?.llm_analysis && (
          <div className="llm-analysis">
            <h3>LLM Analysis</h3>
            <p>{signal.llm_analysis.llm_summary}</p>
            <p>Reasoning: {signal.llm_analysis.llm_reasoning}</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default SignalDetail