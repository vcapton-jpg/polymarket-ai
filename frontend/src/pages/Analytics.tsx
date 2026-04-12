import { useState, useEffect } from "react"
import { LineChart, BarChart, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Line, Bar } from "recharts"
import "./Analytics.css"

function Analytics() {
  const [accuracyData, setAccuracyData] = useState<any[]>([])
  const [bucketData, setBucketData] = useState<any[]>([])
  const [costData, setCostData] = useState({ daily_cost: 0, total_tokens: 0 })

  useEffect(() => {
    fetch("/api/analytics/accuracy").then((r) => r.json()).then(setAccuracyData)
    fetch("/api/analytics/costs").then((r) => r.json()).then(setCostData)
  }, [])

  return (
    <div className="analytics">
      <h1>Analytics</h1>

      <div className="stats-grid">
        <div className="stat-card">
          <h3>Signal Accuracy</h3>
          <p className="stat-value">--</p>
        </div>
        <div className="stat-card">
          <h3>LLM Daily Cost</h3>
          <p className="stat-value">${costData.daily_cost.toFixed(2)}</p>
        </div>
        <div className="stat-card">
          <h3>Total Signals</h3>
          <p className="stat-value">--</p>
        </div>
      </div>

      <div className="chart-card">
        <h3>Accuracy Over Time</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={accuracyData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="accuracy" stroke="#3B82F6" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h3>Performance by Bucket</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={bucketData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="bucket" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="accuracy" fill="#3B82F6" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default Analytics