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

const NAV_ITEMS = [
  { to: "/dashboard", icon: Home, label: "Home" },
  { to: "/opportunities", icon: Radio, label: "Signaux" },
  { to: "/portfolio", icon: Wallet, label: "Portfolio" },
  { to: "/agents", icon: Bot, label: "AI Agents" },
  { to: "/workspace", icon: MessageSquare, label: "Workspace" },
  { to: "/markets", icon: BarChart3, label: "Marches" },
  { to: "/performance", icon: TrendingUp, label: "Performance" },
  { to: "/briefs", icon: FileText, label: "Briefs" },
  { to: "/track-record", icon: Trophy, label: "Track Record" },
  { to: "/pricing", icon: CreditCard, label: "Tarifs" },
  { to: "/settings", icon: Settings, label: "Reglages" },
]

export function Sidebar() {
  const { user, logout } = useAuth()
  const nav = useNavigate()

  const handleLogout = () => {
    logout()
    nav("/")
  }

  return (
    <aside
      className="w-[220px] h-screen fixed top-0 left-0 bg-surface-card flex flex-col py-6 px-4 z-50"
      style={{ borderRight: "1px solid rgba(255,255,255,0.08)" }}
    >
      <NavLink to="/" className="flex items-center gap-2.5 px-2 pb-6 no-underline">
        <Triangle size={20} strokeWidth={1.75} className="text-accent fill-accent/20" />
        <span className="text-lg font-bold tracking-tight text-txt-primary">Foresight</span>
      </NavLink>

      <nav className="flex flex-col gap-1 flex-1">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-all duration-150 no-underline",
                isActive
                  ? "text-accent bg-accent-muted"
                  : "text-txt-muted hover:text-txt-secondary hover:bg-surface-raised",
              )
            }
          >
            <Icon size={18} strokeWidth={1.8} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="flex flex-col gap-3 pt-4 px-2" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-success shadow-[0_0_6px_rgba(16,185,129,0.5)] animate-pulse-live" />
          <span className="text-xs text-txt-muted">Pipeline active</span>
        </div>
        {user && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-txt-muted truncate max-w-[140px]">{user.email}</span>
            <button
              onClick={handleLogout}
              className="p-1.5 rounded-md text-txt-muted hover:text-danger hover:bg-danger/10 transition-colors bg-transparent border-none cursor-pointer"
              title="Se deconnecter"
            >
              <LogOut size={14} />
            </button>
          </div>
        )}
      </div>
    </aside>
  )
}
