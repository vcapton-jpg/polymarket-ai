import React from "react"
import ReactDOM from "react-dom/client"
import App from "./App"
import "./styles/globals.css"
import "./lib/i18n"
import { UserPreferencesProvider } from "./lib/userPreferences"
import { ToastProvider } from "./lib/useToasts"

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <UserPreferencesProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </UserPreferencesProvider>
  </React.StrictMode>,
)
