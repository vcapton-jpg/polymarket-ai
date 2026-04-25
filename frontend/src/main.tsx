import React from "react"
import ReactDOM from "react-dom/client"
import App from "./App"
import "./styles/globals.css"
import "./lib/i18n"
import { UserPreferencesProvider } from "./lib/userPreferences"
import { ToastProvider } from "./lib/useToasts"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ErrorBoundary } from "./components/ErrorBoundary"

/**
 * Global TanStack Query defaults.
 *
 * - `staleTime: 60s` — most of the data we render (positions, performance,
 *   profile-derived limits) is healthy for at least a minute. Without
 *   this every navigation between pages flashes a loading state because
 *   the default staleTime is 0 (every mount refetches).
 * - `retry: 1` — one automatic retry on a transient failure, then surface
 *   the error to the UI. The default of 3 makes diagnostic UX confusing
 *   on real outages.
 * - `refetchOnWindowFocus: false` — global default off; pages that genuinely
 *   need it (live signals, balances) opt back in per-query. Avoids
 *   gratuitous spinners when alt-tabbing.
 *
 * Per-query overrides remain available — `useUserLimits` and
 * `usePaperPortfolio` already declare their own staleTime; those win.
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {/* Root error boundary — last resort. Catches anything that escapes
        per-route boundaries inside <App/>. */}
    <ErrorBoundary scope="Application">
      <QueryClientProvider client={queryClient}>
        <UserPreferencesProvider>
          <ToastProvider>
            {/* Wagmi + viem are NOT mounted at the root. The two wallet-
                using surfaces (OrderForm in SignalDetail, Settings wallet
                section) wrap themselves in <WalletScope> locally so
                wagmi tree-splits into those lazy chunks rather than the
                eager `index` bundle. See lib/WalletScope.tsx. */}
            <App />
          </ToastProvider>
        </UserPreferencesProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>,
)
