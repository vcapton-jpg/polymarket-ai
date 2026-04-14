import { Outlet } from "react-router-dom"
import { Sidebar } from "./Sidebar"
import { MobileNav } from "./MobileNav"
import { useIsMobile } from "../../hooks/useIsMobile"

export function AppLayout() {
  const isMobile = useIsMobile()

  return (
    <div className="flex min-h-screen">
      {!isMobile && <Sidebar />}
      <main
        className={
          isMobile
            ? "flex-1 px-4 pt-[env(safe-area-inset-top,16px)] pb-[calc(76px+env(safe-area-inset-bottom,0px))] max-w-[100vw] overflow-x-hidden"
            : "ml-[220px] flex-1 py-8 px-6 lg:px-10 max-w-[1200px]"
        }
      >
        <Outlet />
      </main>
      {isMobile && <MobileNav />}
    </div>
  )
}
