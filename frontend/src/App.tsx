import { BrowserRouter, Routes, Route, useLocation, useNavigate } from "react-router-dom"
import { lazy, Suspense, useEffect, type ReactNode } from "react"
import { AnimatePresence, LayoutGroup, motion, useReducedMotion } from "framer-motion"
import { RequireAuth } from "./components/auth/RequireAuth"
import { ErrorBoundary } from "./components/ErrorBoundary"
import { readAuth } from "./lib/trial"
import { STORAGE_KEYS } from "./lib/storageKeys"
import { DURATIONS, EASE_PREMIUM } from "./lib/motion"

const Homepage = lazy(() => import("./pages/Homepage"))
const Signals = lazy(() => import("./pages/Signals"))
const SignalDetail = lazy(() => import("./pages/SignalDetail"))
const SignalOutcome = lazy(() => import("./pages/SignalOutcome"))
const Portfolio = lazy(() => import("./pages/Portfolio"))
const Performance = lazy(() => import("./pages/Performance"))
const Apprendre = lazy(() => import("./pages/Apprendre"))
const LearnSection = lazy(() => import("./pages/LearnSection"))
const Welcome = lazy(() => import("./pages/Welcome"))
const Settings = lazy(() => import("./pages/Settings"))
const Pricing = lazy(() => import("./pages/Pricing"))
const Faq = lazy(() => import("./pages/Faq"))
const Login = lazy(() => import("./pages/Login"))
const Signup = lazy(() => import("./pages/Signup"))
const SignalVariants = lazy(() => import("./pages/SignalVariants"))
const Cgu = lazy(() => import("./pages/Cgu"))
const Risques = lazy(() => import("./pages/Risques"))
const MentionsLegales = lazy(() => import("./pages/MentionsLegales"))

/**
 * Paths that never require onboarding completion (public marketing pages
 * + Welcome itself + auth entry points). The L&T trading-test gates
 * (`/welcome/tutorial`, `/welcome/quiz`, `/welcome/budget`) were removed
 * — the only remaining onboarding step is the Welcome profile quiz,
 * which routes the user into Apprendre on completion. Apprendre and the
 * app routes are therefore freely accessible once the user has either
 * completed or explicitly skipped Welcome.
 */
const ONBOARDING_EXEMPT_PATHS = new Set([
  "/",
  "/welcome",
  "/login",
  "/signup",
  "/pricing",
  "/signal-variants",
  "/cgu",
  "/risques",
  "/mentions-legales",
])

/**
 * App-level guard: if the user is authenticated but hasn't entered
 * Welcome (and hasn't explicitly skipped), push them there. Single
 * local-first gate now — the server-authoritative trading-test gates
 * (tutorial/quiz/budget) were removed in favour of Apprendre as the
 * educational on-ramp. Apprendre is *recommended* via the Welcome
 * post-recap transition but never blocks navigation.
 */
function RequireOnboarding() {
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    if (ONBOARDING_EXEMPT_PATHS.has(location.pathname)) return
    if (!readAuth()) return

    const onboarding = localStorage.getItem(STORAGE_KEYS.onboarding)
    if (onboarding !== "done" && onboarding !== "skipped") {
      navigate("/welcome", { replace: true })
    }
  }, [location.pathname, navigate])

  return null
}

/**
 * Per-route error boundary wrapper.
 *
 * Mounted around every `Route element` so a thrown render in one page
 * (Signals chart blowing up, Portfolio mock parse failing, etc.) shows a
 * scoped fallback inside the otherwise intact shell, instead of taking
 * the whole app down. The root <ErrorBoundary> in `main.tsx` is the
 * last-resort net behind these.
 *
 * `scope` is mostly for the in-DOM error-text label and console output —
 * keep it short and human-readable.
 */
function RouteBoundary({ scope, children }: { scope: string; children: ReactNode }) {
  return <ErrorBoundary scope={scope}>{children}</ErrorBoundary>
}

/**
 * Per-route fade/translate wrapper.
 *
 * Wraps each Route element so AnimatePresence can run an entry + exit
 * animation on path change. The motion is intentionally subtle — a
 * 12 px lift over `DURATIONS.default` — so it adds polish without
 * stretching perceived navigation latency. Snaps under
 * `prefers-reduced-motion`.
 *
 * **AnimatePresence mode is `popLayout`**, not `wait`. The Welcome →
 * Apprendre transition uses a shared `layoutId` for the profile
 * pellet, which requires both pages to be mounted in the same commit
 * so Framer can measure source + destination. `wait` would unmount
 * Welcome before mounting Apprendre and break that handoff;
 * `popLayout` keeps the exiting page in the DOM (positioned
 * absolutely) while the new one mounts on top, preserving layoutId
 * continuity.
 */
function RouteTransition({ children }: { children: ReactNode }) {
  const reduced = useReducedMotion()
  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={reduced ? undefined : { opacity: 0, y: -8 }}
      transition={{ duration: reduced ? 0 : DURATIONS.default, ease: EASE_PREMIUM }}
    >
      {children}
    </motion.div>
  )
}

/**
 * Routes split into its own component so we can call `useLocation()`
 * here — `<Routes>` needs the explicit `location` prop to stay stable
 * across an AnimatePresence exit, and `key={location.pathname}` is what
 * triggers the per-path remount that AnimatePresence keys off.
 */
function AnimatedRoutes() {
  const location = useLocation()
  return (
    <AnimatePresence mode="popLayout" initial={false}>
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<RouteBoundary scope="Homepage"><RouteTransition><Homepage /></RouteTransition></RouteBoundary>} />
        <Route path="/pricing" element={<RouteBoundary scope="Pricing"><RouteTransition><Pricing /></RouteTransition></RouteBoundary>} />
        <Route path="/faq" element={<RouteBoundary scope="FAQ"><RouteTransition><Faq /></RouteTransition></RouteBoundary>} />
        <Route path="/signal-variants" element={<RouteBoundary scope="Signal variants"><RouteTransition><SignalVariants /></RouteTransition></RouteBoundary>} />
        <Route path="/cgu" element={<RouteBoundary scope="CGU"><RouteTransition><Cgu /></RouteTransition></RouteBoundary>} />
        <Route path="/risques" element={<RouteBoundary scope="Risques"><RouteTransition><Risques /></RouteTransition></RouteBoundary>} />
        <Route path="/mentions-legales" element={<RouteBoundary scope="Mentions légales"><RouteTransition><MentionsLegales /></RouteTransition></RouteBoundary>} />
        <Route path="/login" element={<RouteBoundary scope="Login"><RouteTransition><Login /></RouteTransition></RouteBoundary>} />
        <Route path="/signup" element={<RouteBoundary scope="Signup"><RouteTransition><Signup /></RouteTransition></RouteBoundary>} />
        <Route path="/signals" element={<RouteBoundary scope="Signaux"><RequireAuth><RouteTransition><Signals /></RouteTransition></RequireAuth></RouteBoundary>} />
        <Route path="/signals/:id" element={<RouteBoundary scope="Signal · détail"><RequireAuth><RouteTransition><SignalDetail /></RouteTransition></RequireAuth></RouteBoundary>} />
        <Route path="/signals/:id/outcome" element={<RouteBoundary scope="Signal · résultat"><RequireAuth><RouteTransition><SignalOutcome /></RouteTransition></RequireAuth></RouteBoundary>} />
        <Route path="/portfolio" element={<RouteBoundary scope="Portefeuille"><RequireAuth><RouteTransition><Portfolio /></RouteTransition></RequireAuth></RouteBoundary>} />
        <Route path="/performance" element={<RouteBoundary scope="Performance"><RequireAuth><RouteTransition><Performance /></RouteTransition></RequireAuth></RouteBoundary>} />
        <Route path="/apprendre" element={<RouteBoundary scope="Apprendre"><RequireAuth><RouteTransition><Apprendre /></RouteTransition></RequireAuth></RouteBoundary>} />
        <Route path="/apprendre/:slug" element={<RouteBoundary scope="Apprendre · section"><RequireAuth><RouteTransition><LearnSection /></RouteTransition></RequireAuth></RouteBoundary>} />
        <Route path="/welcome" element={<RouteBoundary scope="Welcome"><RequireAuth><RouteTransition><Welcome /></RouteTransition></RequireAuth></RouteBoundary>} />
        <Route path="/settings" element={<RouteBoundary scope="Réglages"><RequireAuth><RouteTransition><Settings /></RouteTransition></RequireAuth></RouteBoundary>} />
      </Routes>
    </AnimatePresence>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-obsidian-900 text-ink grain">
        <RequireOnboarding />
        <Suspense fallback={<div className="container-page py-20 text-ink-muted">Chargement…</div>}>
          <LayoutGroup>
            <AnimatedRoutes />
          </LayoutGroup>
        </Suspense>
      </div>
    </BrowserRouter>
  )
}
