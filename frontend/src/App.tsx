import { Routes, Route, Navigate } from "react-router-dom"
import { AppLayout } from "./components/layout/AppLayout"
import { lazy, Suspense, type ReactNode } from "react"
import { Skeleton } from "./components/ui/Skeleton"
import { AuthProvider, useAuth } from "./lib/auth"

const Landing = lazy(() => import("./pages/Landing"))
const Auth = lazy(() => import("./pages/Auth"))
const Dashboard = lazy(() => import("./pages/Dashboard"))
const Opportunities = lazy(() => import("./pages/Opportunities"))
const OpportunityDetail = lazy(() => import("./pages/OpportunityDetail"))
const Markets = lazy(() => import("./pages/Markets"))
const Performance = lazy(() => import("./pages/Performance"))
const Learn = lazy(() => import("./pages/Learn"))
const TrackRecord = lazy(() => import("./pages/TrackRecord"))
const Settings = lazy(() => import("./pages/Settings"))
const Portfolio = lazy(() => import("./pages/Portfolio"))
const Agents = lazy(() => import("./pages/Agents"))
const Pricing = lazy(() => import("./pages/Pricing"))
const Briefs = lazy(() => import("./pages/Briefs"))
const AgentWorkspace = lazy(() => import("./pages/AgentWorkspace"))

function PageLoader() {
  return (
    <div className="py-8 flex flex-col gap-4">
      <Skeleton height={32} width="40%" />
      <Skeleton height={200} />
      <Skeleton height={120} />
    </div>
  )
}

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth()
  if (isLoading) return <PageLoader />
  if (!user) return <Navigate to="/auth" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <AuthProvider>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/auth" element={<Auth />} />
          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/opportunities" element={<Opportunities />} />
            <Route path="/opportunity/:id" element={<OpportunityDetail />} />
            <Route path="/markets" element={<Markets />} />
            <Route path="/performance" element={<Performance />} />
            <Route path="/learn" element={<Learn />} />
            <Route path="/track-record" element={<TrackRecord />} />
            <Route path="/portfolio" element={<Portfolio />} />
            <Route path="/agents" element={<Agents />} />
            <Route path="/pricing" element={<Pricing />} />
            <Route path="/briefs" element={<Briefs />} />
            <Route path="/workspace" element={<AgentWorkspace />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </Suspense>
    </AuthProvider>
  )
}
