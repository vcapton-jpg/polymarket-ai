import { useState, useEffect } from "react"
import { Send, Key } from "lucide-react"
import "./Settings.css"

function Settings() {
  const [telegramChatId, setTelegramChatId] = useState("")
  const [minScoreThreshold, setMinScoreThreshold] = useState(60)
  const [apiKey, setApiKey] = useState("")
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    fetch("/api/settings")
      .then((r) => r.json())
      .then((data) => {
        if (data.telegram_chat_id) setTelegramChatId(data.telegram_chat_id)
        if (data.min_score_threshold) setMinScoreThreshold(data.min_score_threshold)
      })
      .catch(() => {})
  }, [])

  const handleSave = async () => {
    await fetch("/api/settings/telegram", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        telegram_chat_id: telegramChatId,
        min_score_threshold: minScoreThreshold,
      }),
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="settings">
      <h1>Settings</h1>

      <div className="settings-section">
        <h2><Send /> Telegram Bot</h2>
        <p>Connect Telegram to receive real-time signal notifications.</p>

        <div className="form-group">
          <label>Chat ID</label>
          <input
            type="text"
            value={telegramChatId}
            onChange={(e) => setTelegramChatId(e.target.value)}
            placeholder="Enter your Telegram chat ID"
          />
        </div>

        <div className="form-group">
          <label>Minimum Score Threshold</label>
          <input
            type="range"
            min="0"
            max="100"
            value={minScoreThreshold}
            onChange={(e) => setMinScoreThreshold(Number(e.target.value))}
          />
          <span>{minScoreThreshold}</span>
        </div>

        <button onClick={handleSave} className="save-button">
          {saved ? "Saved!" : "Save"}
        </button>
      </div>

      <div className="settings-section">
        <h2><Key /> API Keys</h2>
        <p>Manage your API keys for external integrations.</p>

        <div className="form-group">
          <label>OpenAI API Key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-..."
          />
        </div>

        <button className="save-button">Update Key</button>
      </div>
    </div>
  )
}

export default Settings