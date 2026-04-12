import { ArrowRight, TrendingUp, Zap, Shield } from "lucide-react"


function Landing() {
  return (
    <div className="landing">
      <section className="hero">
        <div className="hero-content">
          <h1>Know before the market does</h1>
          <p className="subtitle">
            Real-time signals on prediction markets — politics, science, geopolitics, sports
          </p>
          <a href="/dashboard" className="cta-button">
            Get early access <ArrowRight size={20} />
          </a>
        </div>
        <div className="hero-preview">
          <div className="signal-card-preview">
            <div className="signal-header">
              <span className="direction-badge buy-yes">🟢 BUY YES</span>
              <span className="score">78/100</span>
            </div>
            <p className="signal-question">Will Russia and Ukraine reach a peace agreement by June 2025?</p>
            <div className="signal-meta">
              <span>Confidence: High</span>
              <span>Window: ~8 min</span>
            </div>
          </div>
        </div>
      </section>

      <section className="how-it-works">
        <h2>How it works</h2>
        <div className="steps">
          <div className="step">
            <div className="step-icon"><Zap /></div>
            <h3>1. Monitor</h3>
            <p>We track RSS feeds, X, and news APIs in real-time</p>
          </div>
          <div className="step">
            <div className="step-icon"><TrendingUp /></div>
            <h3>2. Analyze</h3>
            <p>AI detects events and matches them to prediction markets</p>
          </div>
          <div className="step">
            <div className="step-icon"><Shield /></div>
            <h3>3. Signal</h3>
            <p>Get actionable signals before the market corrects</p>
          </div>
        </div>
      </section>

      <section className="pricing">
        <h2>Pricing</h2>
        <div className="pricing-cards">
          <div className="pricing-card">
            <h3>Free</h3>
            <p className="price">$0</p>
            <ul>
              <li>5 signals/day</li>
              <li>Delayed by 5 min</li>
            </ul>
            <button>Get started</button>
          </div>
          <div className="pricing-card featured">
            <h3>Pro</h3>
            <p className="price">$29/mo</p>
            <ul>
              <li>Unlimited signals</li>
              <li>Real-time alerts</li>
              <li>Telegram integration</li>
            </ul>
            <button>Get started</button>
          </div>
        </div>
      </section>

      <footer className="footer">
        <p>© 2025 Signal. Built for prediction market traders.</p>
      </footer>
    </div>
  )
}

export default Landing