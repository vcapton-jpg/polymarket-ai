import React from "react"
import ReactDOM from "react-dom/client"
import App from "./App"
import "./styles/globals.css"
import "./lib/i18n"
import { UserPreferencesProvider } from "./lib/userPreferences"
import { ToastProvider } from "./lib/useToasts"
import { WagmiProvider } from "wagmi"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { wagmiConfig } from "@/lib/wagmiConfig"

const queryClient = new QueryClient()

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <WagmiProvider config={wagmiConfig}>
      <QueryClientProvider client={queryClient}>
        <UserPreferencesProvider>
          <ToastProvider>
            <App />
          </ToastProvider>
        </UserPreferencesProvider>
      </QueryClientProvider>
    </WagmiProvider>
  </React.StrictMode>,
)
