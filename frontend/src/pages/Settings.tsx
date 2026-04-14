import { useState } from "react"
import { motion } from "framer-motion"
import { Settings as SettingsIcon, Bell, Sliders, Info, ExternalLink, Save, Smartphone } from "lucide-react"
import { Card } from "../components/ui/Card"
import { Button } from "../components/ui/Button"
import { BUCKETS, SCORE_TIERS } from "../lib/constants"
import { cn } from "../lib/utils"
import { usePushNotifications } from "../hooks/usePushNotifications"

interface Prefs {
  telegramChatId: string
  minScoreNotif: number
  notifDirections: "both" | "yes" | "no"
  defaultBucket: string
  defaultMinScore: number
  showLowConviction: boolean
}

export default function Settings() {
  const [prefs, setPrefs] = useState<Prefs>(() => {
    try {
      const stored = localStorage.getItem("signal-prefs")
      if (stored) return { ...{
        telegramChatId: "",
        minScoreNotif: 60,
        notifDirections: "both",
        defaultBucket: "",
        defaultMinScore: 0,
        showLowConviction: true,
      }, ...JSON.parse(stored) }
    } catch {}
    return {
      telegramChatId: "",
      minScoreNotif: 60,
      notifDirections: "both",
      defaultBucket: "",
      defaultMinScore: 0,
      showLowConviction: true,
    }
  })
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    localStorage.setItem("signal-prefs", JSON.stringify(prefs))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="max-w-[700px]">
      {/* Header */}
      <div className="flex items-center gap-3 mb-1">
        <SettingsIcon size={20} className="text-accent" />
        <h1 className="text-xl md:text-2xl font-bold text-txt-primary tracking-tight">Settings</h1>
      </div>
      <p className="text-sm text-txt-muted mb-6">Configure your preferences and notifications</p>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col gap-5"
      >
        {/* Telegram Notifications */}
        <Card className="p-5">
          <div className="flex items-center gap-3 mb-5">
            <Bell size={18} className="text-accent" />
            <h3 className="text-sm font-semibold text-txt-primary">Telegram Notifications</h3>
          </div>

          <div className="mb-5">
            <label className="block text-[11px] font-semibold text-txt-muted uppercase tracking-wider mb-2">
              Chat ID
            </label>
            <input
              type="text"
              value={prefs.telegramChatId}
              onChange={(e) => setPrefs({ ...prefs, telegramChatId: e.target.value })}
              placeholder="Enter your Telegram Chat ID"
              className="w-full"
            />
            <p className="text-[11px] text-txt-muted mt-1">
              Message @SignalPMBot on Telegram to get your Chat ID
            </p>
          </div>

          <div className="mb-5">
            <label className="block text-[11px] font-semibold text-txt-muted uppercase tracking-wider mb-2">
              Min score threshold
            </label>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min={50}
                max={90}
                step={5}
                value={prefs.minScoreNotif}
                onChange={(e) => setPrefs({ ...prefs, minScoreNotif: Number(e.target.value) })}
                className="flex-1 accent-accent h-1.5"
              />
              <span className="font-mono text-sm font-semibold text-accent w-8 text-right font-tabular">
                {prefs.minScoreNotif}+
              </span>
            </div>
          </div>

          <div className="mb-5">
            <label className="block text-[11px] font-semibold text-txt-muted uppercase tracking-wider mb-2">
              Notification types
            </label>
            <div className="flex gap-2">
              {[
                { value: "both" as const, label: "Both" },
                { value: "yes" as const, label: "BUY YES" },
                { value: "no" as const, label: "BUY NO" },
              ].map((d) => (
                <button
                  key={d.value}
                  onClick={() => setPrefs({ ...prefs, notifDirections: d.value })}
                  className={cn(
                    "px-4 py-2 rounded-md text-xs font-semibold transition-all border",
                    prefs.notifDirections === d.value
                      ? "bg-accent/15 border-accent/40 text-accent"
                      : "bg-surface-card text-txt-muted shadow-card hover:text-txt-secondary",
                  )}
                  style={{ border: prefs.notifDirections === d.value ? "1px solid rgba(245,158,11,0.35)" : "1px solid rgba(255,255,255,0.08)" }}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>

          <Button variant="secondary" size="sm" disabled>
            Send test signal
          </Button>
          <p className="text-[11px] text-txt-muted mt-2">Coming soon</p>
        </Card>

        {/* Push Notifications */}
        <PushNotificationCard />

        {/* Signal Preferences */}
        <Card className="p-5">
          <div className="flex items-center gap-3 mb-5">
            <Sliders size={18} className="text-accent" />
            <h3 className="text-sm font-semibold text-txt-primary">Signal Preferences</h3>
          </div>

          <div className="mb-5">
            <label className="block text-[11px] font-semibold text-txt-muted uppercase tracking-wider mb-2">
              Default category filter
            </label>
            <div className="flex gap-2 flex-wrap">
              {[{ value: "", label: "All" }, ...BUCKETS].map((b) => (
                <button
                  key={b.value}
                  onClick={() => setPrefs({ ...prefs, defaultBucket: b.value })}
                  className={cn(
                    "px-3 py-1.5 rounded-full text-xs font-semibold transition-all border",
                    prefs.defaultBucket === b.value
                      ? "bg-accent/15 border-accent/40 text-accent"
                      : "bg-surface-card text-txt-muted shadow-card hover:text-txt-secondary",
                  )}
                  style={{ border: prefs.defaultBucket === b.value ? "1px solid rgba(245,158,11,0.35)" : "1px solid rgba(255,255,255,0.08)" }}
                >
                  {"emoji" in b && b.emoji ? `${b.emoji} ` : ""}{b.label}
                </button>
              ))}
            </div>
          </div>

          <div className="mb-5">
            <label className="block text-[11px] font-semibold text-txt-muted uppercase tracking-wider mb-2">
              Default min score
            </label>
            <select
              value={prefs.defaultMinScore}
              onChange={(e) => setPrefs({ ...prefs, defaultMinScore: Number(e.target.value) })}
              className="w-full"
            >
              <option value={0}>Show all signals</option>
              <option value={60}>60+ (Actionable)</option>
              <option value={75}>75+ (High conviction)</option>
              <option value={90}>90+ (Exceptional)</option>
            </select>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-txt-primary font-medium">Show low conviction signals</p>
              <p className="text-[11px] text-txt-muted">Signals scoring below 60</p>
            </div>
            <button
              onClick={() => setPrefs({ ...prefs, showLowConviction: !prefs.showLowConviction })}
              className={cn(
                "w-11 h-6 rounded-full relative transition-colors cursor-pointer border-none",
                prefs.showLowConviction ? "bg-accent" : "bg-surface-raised",
              )}
            >
              <div
                className="w-4.5 h-4.5 rounded-full bg-white absolute top-[3px] transition-all"
                style={{ left: prefs.showLowConviction ? 23 : 3, width: 18, height: 18 }}
              />
            </button>
          </div>
        </Card>

        {/* About */}
        <Card className="p-5">
          <div className="flex items-center gap-3 mb-5">
            <Info size={18} className="text-accent" />
            <h3 className="text-sm font-semibold text-txt-primary">About Signal</h3>
          </div>

          <div className="space-y-4 text-sm">
            <div className="flex justify-between items-center py-2" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
              <span className="text-txt-muted">Version</span>
              <span className="font-mono text-txt-secondary text-xs">0.1.0</span>
            </div>

            <div>
              <p className="text-txt-muted mb-2 text-xs font-semibold uppercase tracking-wider">How scores work</p>
              <div className="bg-surface-raised rounded-md p-3 text-xs text-txt-secondary leading-relaxed space-y-2">
                <p>Signals combine multiple factors: semantic relevance between news and market, LLM impact analysis, market liquidity, spread, and price positioning.</p>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  {Object.values(SCORE_TIERS).map((tier) => (
                    <div key={tier.label} className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full" style={{ background: tier.color }} />
                      <span className="text-[11px]">{tier.min}+: {tier.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div>
              <p className="text-txt-muted mb-2 text-xs font-semibold uppercase tracking-wider">Data sources</p>
              <p className="text-xs text-txt-secondary">RSS feeds, World News API, X/Twitter monitoring -- covering global press agencies, financial media, and social signals.</p>
            </div>

            <a
              href="https://polymarket.com"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-accent text-xs font-medium hover:underline"
            >
              <ExternalLink size={12} />
              Open Polymarket
            </a>
          </div>
        </Card>
      </motion.div>

      {/* Save */}
      <div className="flex items-center gap-4 mt-8 pt-6" style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}>
        <Button onClick={handleSave} icon={<Save size={16} />}>
          {saved ? "Saved!" : "Save Preferences"}
        </Button>
        {saved && (
          <motion.span
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            className="text-success text-sm"
          >
            Preferences saved successfully.
          </motion.span>
        )}
      </div>
    </div>
  )
}

function PushNotificationCard() {
  const { supported, subscribed, subscribe, unsubscribe, permission } = usePushNotifications()

  if (!supported) return null

  return (
    <Card className="p-5">
      <div className="flex items-center gap-3 mb-5">
        <Smartphone size={18} className="text-accent" />
        <h3 className="text-sm font-semibold text-txt-primary">Push Notifications</h3>
      </div>

      <p className="text-xs text-txt-secondary mb-4">
        Receive native push notifications on your device when high-conviction signals are detected.
      </p>

      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-txt-primary font-medium">
            {subscribed ? "Notifications enabled" : "Enable push notifications"}
          </p>
          <p className="text-[11px] text-txt-muted">
            {permission === "denied" ? "Blocked by browser — allow in site settings" : "Signals scoring 60+ will trigger a notification"}
          </p>
        </div>
        <button
          onClick={() => subscribed ? unsubscribe() : subscribe()}
          disabled={permission === "denied"}
          className={cn(
            "w-11 h-6 rounded-full relative transition-colors cursor-pointer border-none",
            subscribed ? "bg-accent" : "bg-surface-raised",
            permission === "denied" && "opacity-50 cursor-not-allowed",
          )}
        >
          <div
            className="rounded-full bg-white absolute top-[3px] transition-all"
            style={{ left: subscribed ? 23 : 3, width: 18, height: 18 }}
          />
        </button>
      </div>
    </Card>
  )
}
