import { NavLink, useNavigate } from "react-router-dom"
import {
  Home,
  Radio,
  BarChart3,
  TrendingUp,
  Trophy,
  Settings,
  Triangle,
  Wallet,
  Bot,
  FileText,
  CreditCard,
  MessageSquare,
  LogOut,
} from "lucide-react"
import { cn } from "../../lib/utils"
import { useAuth } from "../../lib/auth"

const NAV_GROUPS = [
  {
    label: "Trading",
    items: [
      { to: "/dashboard", icon: Home, label: "Home" },
      { to: "/opportunities", icon: Radio, label: "Signals" },
      { to: "/portfolio", icon: Wallet, label: "Portfolio" },
    ],
  },
  {
    label: "Analysis",
    items: [
      { to: "/markets", icon: BarChart3, label: "Markets" },
      { to: "/performance", icon: TrendingUp, label: "Performance" },
      { to: "/track-record", icon: Trophy, label: "Track Record" },
    ],
  },
  {
    label: "AI",
    items: [
      { to: "/agents", icon: Bot, label: "Agents" },
      { to: "/workspace", icon: MessageSquare, label: "Workspace" },
      { to: "/briefs", icon: FileText, label: "Briefs" },
    ],
  },
  {
    label: "Account",
    items: [
      { to: "/pricing", icon: CreditCard, label: "Pricing" },
      { to: "/settings", icon: Settings, label: "Settings" },
    ],
  },
]

export function Sidebar() {
  const { user, logout } = useAuth()
  const nav = useNavigate()

  const handleLogout = () => {
    logout()
    nav("/")
  }

  return (
    <aside className="w-[220px] h-screen fixed top-0 left-0 glass-card flex flex-col py-5 px-3 z-50 border-r border-edge-subtle">
      <NavLink to="/" className="flex items-center gap-2.5 px-3 pb-5 no-underline group">
        <div className="w-8 h-8 rounded-lg bg-accent-muted flex items-center justify-center group-hover:bg-accent/20 transition-colors">
          <Triangle size={16} strokeWidth={1.75} className="text-accent fill-accent/20" />
        </div>
        <span className="text-lg font-display font-bold tracking-display text-txt-primary">
          Foresight
        </span>
      </NavLink>

      <nav className="flex flex-col gap-5 flex-1 overflow-y-auto">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <span className="text-[10px] font-semibold text-txt-muted uppercase tracking-[0.12em] px-3 mb-1.5 block">
              {group.label}
            </span>
            <div className="flex flex-col gap-0.5">
              {group.items.map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) =>
                    cn(
                      "relative flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium transition-all duration-200 no-underline",
                      isActive
                        ? "text-accent bg-accent-muted"
                        : "text-txt-muted hover:text-txt-secondary hover:bg-surface-glass",
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 rounded-r-full bg-accent" />
                      )}
                      <Icon size={17} strokeWidth={1.8} />
                      <span>{label}</span>
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="flex flex-col gap-3 pt-4 px-2 border-t border-edge-subtle">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-success shadow-[0_0_8px_rgba(16,185,129,0.5)] animate-pulse-live" />
          <span className="text-[11px] text-txt-muted font-mono">Pipeline active</span>
        </div>
        {user && (
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-6 h-6 rounded-full bg-accent-muted flex items-center justify-center shrink-0">
                <span className="text-[10px] font-bold text-accent">
                  {user.email?.charAt(0).toUpperCase()}
                </span>
              </div>
              <span className="text-[11px] text-txt-muted truncate">{user.email}</span>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 rounded-lg text-txt-muted hover:text-danger hover:bg-danger/10 transition-colors bg-transparent border-none cursor-pointer"
              title="Sign out"
            >
              <LogOut size={14} />
            </button>
          </div>
        )}
      </div>
    </aside>
  )
}
