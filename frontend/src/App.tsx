import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { useState, useEffect } from "react"
import Landing from "./pages/Landing"
import Dashboard from "./pages/Dashboard"
import SignalDetail from "./pages/SignalDetail"
import Analytics from "./pages/Analytics"
import Settings from "./pages/Settings"


function App() {
  const [darkMode, setDarkMode] = useState(true)

  useEffect(() => {
    const saved = localStorage.getItem("darkMode")
    if (saved !== null) {
      setDarkMode(saved === "true")
    }
  }, [])

  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode)
    localStorage.setItem("darkMode", String(darkMode))
  }, [darkMode])

  return (
    <BrowserRouter>
      <div className="app">
        <nav className="nav">
          <div className="nav-content">
            <a href="/" className="logo">Signal</a>
            <div className="nav-links">
              <a href="/dashboard">Dashboard</a>
              <a href="/analytics">Analytics</a>
              <a href="/settings">Settings</a>
              <button onClick={() => setDarkMode(!darkMode)} className="theme-toggle">
                {darkMode ? "☀️" : "🌙"}
              </button>
            </div>
          </div>
        </nav>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/signal/:id" element={<SignalDetail />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App