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
    <nav className="fixed bottom-0 left-0 right-0 flex justify-around items-center h-[calc(64px+env(safe-area-inset-bottom,0px))] pb-[env(safe-area-inset-bottom,0px)] glass-card z-50 border-t border-edge-subtle">
      {TAB_ITEMS.map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            cn(
              "flex flex-col items-center justify-center gap-1 flex-1 py-2 no-underline transition-all duration-200",
              isActive ? "text-accent" : "text-txt-muted",
            )
          }
          style={{ WebkitTapHighlightColor: "transparent" }}
        >
          {({ isActive }) => (
            <>
              <div className="relative">
                <Icon size={20} strokeWidth={isActive ? 2 : 1.8} />
                {isActive && (
                  <span className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-accent shadow-[0_0_6px_rgba(212,160,23,0.5)]" />
                )}
              </div>
              <span className={cn("text-[10px]", isActive ? "font-semibold" : "font-medium")}>
                {label}
              </span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}
