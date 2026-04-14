import { NavLink } from "react-router-dom"
import {
  Home,
  Radio,
  Wallet,
  Bot,
  Settings,
} from "lucide-react"
import { cn } from "../../lib/utils"

const TAB_ITEMS = [
  { to: "/dashboard", icon: Home, label: "Home" },
  { to: "/opportunities", icon: Radio, label: "Signals" },
  { to: "/portfolio", icon: Wallet, label: "Portfolio" },
  { to: "/agents", icon: Bot, label: "Agents" },
  { to: "/settings", icon: Settings, label: "More" },
]

export function MobileNav() {
  return (
    <nav
      className="fixed bottom-0 left-0 right-0 flex justify-around items-center h-[calc(60px+env(safe-area-inset-bottom,0px))] pb-[env(safe-area-inset-bottom,0px)] bg-surface-card/95 backdrop-blur-xl z-50"
      style={{ borderTop: "1px solid rgba(255,255,255,0.10)" }}
    >
      {TAB_ITEMS.map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            cn(
              "flex flex-col items-center justify-center gap-0.5 flex-1 py-2 no-underline transition-colors",
              isActive ? "text-accent" : "text-txt-muted",
            )
          }
          style={{ WebkitTapHighlightColor: "transparent" }}
        >
          <Icon size={20} strokeWidth={1.8} />
          <span className="text-[10px] font-medium">{label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
