import { useState, useEffect, useCallback } from "react"
import { Link } from "react-router-dom"
import { formatDistanceToNow } from "date-fns"
import { Filter, SortAsc, TrendingUp, TrendingDown } from "lucide-react"
import "./Dashboard.css"

interface Signal {
  id: number
  direction: "YES" | "NO"
  question: string
  score: number
  confidence_label: string
  urgency_label: string
  tradability_label: string
  market_price_at_signal: number
  signal_date: string
  bucket: string
}

function Dashboard() {
  const [signals, setSignals] = useState<Signal[]>([])
  const [filters, setFilters] = useState({
    bucket: "",
    minScore: 0,
    direction: "",
  })
  const [sort, setSort] = useState("newest")
  const [loading, setLoading] = useState(true)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    // Fetch signals
    fetchSignals()

    // WebSocket connection
    const ws = new WebSocket("ws://localhost:8000/ws/signals")

    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onmessage = (event) => {
      const signal = JSON.parse(event.data)
      setSignals((prev) => [signal, ...prev])
    }

    return () => ws.close()
  }, [])

  const fetchSignals = async () => {
    try {
      const response = await fetch("/api/signals?limit=20")
      const data = await response.json()
      setSignals(data.signals || [])
    } catch (error) {
      console.error("Failed to fetch signals:", error)
    } finally {
      setLoading(false)
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return "#10B981"
    if (score >= 60) return "#3B82F6"
    return "#F59E0B"
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Signal Feed</h1>
        <div className={`connection-status ${connected ? "connected" : ""}`}>
          {connected ? "Live" : "Connecting..."}
        </div>
      </div>

      <div className="filters">
        <select
          value={filters.bucket}
          onChange={(e) => setFilters({ ...filters, bucket: e.target.value })}
          className="filter-select"
        >
          <option value="">All buckets</option>
          <option value="politics">Politics</option>
          <option value="geopolitics">Geopolitics</option>
          <option value="economics">Economics</option>
          <option value="crypto">Crypto</option>
          <option value="sports">Sports</option>
          <option value="science">Science</option>
        </select>

        <select
          value={filters.minScore}
          onChange={(e) => setFilters({ ...filters, minScore: Number(e.target.value) })}
          className="filter-select"
        >
          <option value={0}>All scores</option>
          <option value={60}>Score 60+</option>
          <option value={80}>Score 80+</option>
        </select>

        <select
          value={filters.direction}
          onChange={(e) => setFilters({ ...filters, direction: e.target.value })}
          className="filter-select"
        >
          <option value="">All directions</option>
          <option value="YES">Buy YES</option>
          <option value="NO">Buy NO</option>
        </select>

        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          className="filter-select"
        >
          <option value="newest">Newest first</option>
          <option value="score">Highest score</option>
          <option value="resolution">Fastest resolution</option>
        </select>
      </div>

      <div className="signals-list">
        {loading ? (
          <div className="loading">Loading signals...</div>
        ) : signals.length === 0 ? (
          <div className="empty">No signals yet. New signals will appear here.</div>
        ) : (
          signals.map((signal) => (
            <Link to={`/signal/${signal.id}`} key={signal.id} className="signal-card">
              <div className="signal-card-header">
                <span className={`direction-badge ${signal.direction === "YES" ? "buy-yes" : "buy-no"}`}>
                  {signal.direction === "YES" ? "🟢 BUY YES" : "🔴 BUY NO"}
                </span>
                <span className="score" style={{ color: getScoreColor(signal.score) }}>
                  {signal.score}/100
                </span>
              </div>
              <p className="signal-question">{signal.question}</p>
              <div className="signal-meta">
                <span className="bucket">{signal.bucket}</span>
                <span>Confidence: {signal.confidence_label}</span>
                <span>Urgency: {signal.urgency_label}</span>
                <span>Tradability: {signal.tradability_label}</span>
              </div>
              <div className="signal-footer">
                <span>Price: ${signal.market_price_at_signal?.toFixed(2)}</span>
                <span>{formatDistanceToNow(new Date(signal.signal_date), { addSuffix: true })}</span>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  )
}

export default Dashboard