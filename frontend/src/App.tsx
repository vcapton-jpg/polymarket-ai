import { BrowserRouter, Routes, Route, useLocation, useNavigate } from "react-router-dom"
import { lazy, Suspense, useEffect } from "react"
import { LayoutGroup } from "framer-motion"
import { RequireAuth } from "./components/auth/RequireAuth"
import { readAuth } from "./lib/trial"
import { STORAGE_KEYS } from "./lib/storageKeys"

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
const Tutorial = lazy(() => import("./pages/onboarding/Tutorial"))
const Quiz = lazy(() => import("./pages/onboarding/Quiz"))
const BudgetSetup = lazy(() => import("./pages/onboarding/BudgetSetup"))

/**
 * Paths that never require onboarding completion (public marketing pages
 * + the onboarding flow itself + auth entry points).
 */
const ONBOARDING_EXEMPT_PATHS = new Set([
  "/",
  "/welcome",
  "/welcome/tutorial",
  "/welcome/quiz",
  "/welcome/budget",
  "/login",
  "/signup",
  "/pricing",
  "/signal-variants",
])

/**
 * App-level guard: if the user is authenticated but hasn't finished (or
 * skipped) onboarding, force-redirect to /welcome. Runs on every route
 * transition; no-op on public/auth/onboarding routes.
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

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-obsidian-900 text-ink grain">
        <RequireOnboarding />
        <Suspense fallback={<div className="container-page py-20 text-ink-muted">Chargement…</div>}>
          <LayoutGroup>
            <Routes>
              <Route path="/" element={<Homepage />} />
              <Route path="/pricing" element={<Pricing />} />
              <Route path="/faq" element={<Faq />} />
              <Route path="/signal-variants" element={<SignalVariants />} />
              <Route path="/login" element={<Login />} />
              <Route path="/signup" element={<Signup />} />
              <Route path="/signals" element={<RequireAuth><Signals /></RequireAuth>} />
              <Route path="/signals/:id" element={<RequireAuth><SignalDetail /></RequireAuth>} />
              <Route path="/signals/:id/outcome" element={<RequireAuth><SignalOutcome /></RequireAuth>} />
              <Route path="/portfolio" element={<RequireAuth><Portfolio /></RequireAuth>} />
              <Route path="/performance" element={<RequireAuth><Performance /></RequireAuth>} />
              <Route path="/apprendre" element={<RequireAuth><Apprendre /></RequireAuth>} />
              <Route path="/apprendre/:slug" element={<RequireAuth><LearnSection /></RequireAuth>} />
              <Route path="/welcome" element={<RequireAuth><Welcome /></RequireAuth>} />
              <Route path="/welcome/tutorial" element={<RequireAuth><Tutorial /></RequireAuth>} />
              <Route path="/welcome/quiz" element={<RequireAuth><Quiz /></RequireAuth>} />
              <Route path="/welcome/budget" element={<RequireAuth><BudgetSetup /></RequireAuth>} />
              <Route path="/settings" element={<RequireAuth><Settings /></RequireAuth>} />
            </Routes>
          </LayoutGroup>
        </Suspense>
      </div>
    </BrowserRouter>
  )
}
