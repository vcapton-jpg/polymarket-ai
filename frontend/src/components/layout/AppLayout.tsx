import { Outlet, useLocation } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import { Sidebar } from "./Sidebar"
import { MobileNav } from "./MobileNav"
import { useIsMobile } from "../../hooks/useIsMobile"

const pageVariants = {
  initial: { opacity: 0, y: 8, filter: "blur(4px)" },
  animate: { opacity: 1, y: 0, filter: "blur(0px)" },
  exit: { opacity: 0, y: -4, filter: "blur(2px)" },
}

export function AppLayout() {
  const isMobile = useIsMobile()
  const location = useLocation()

  return (
    <div className="flex min-h-screen bg-surface-0">
      {!isMobile && <Sidebar />}
      <main
        className={
          isMobile
            ? "flex-1 px-4 pt-[env(safe-area-inset-top,16px)] pb-[calc(80px+env(safe-area-inset-bottom,0px))] max-w-[100vw] overflow-x-hidden"
            : "ml-[220px] flex-1 py-8 px-6 lg:px-10 max-w-[1200px]"
        }
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            variants={pageVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>
      {isMobile && <MobileNav />}
    </div>
  )
}
