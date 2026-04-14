import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import { Triangle, ArrowRight, Mail, Lock, AlertCircle, Loader2 } from "lucide-react"
import { useAuth } from "../lib/auth"

export default function Auth() {
  const nav = useNavigate()
  const { login, register } = useAuth()
  const [mode, setMode] = useState<"login" | "register">("register")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setLoading(true)

    try {
      if (mode === "register") {
        await register(email.trim(), password)
      } else {
        await login(email.trim(), password)
      }
      nav("/dashboard", { replace: true })
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError("Unable to connect")
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface-0 flex items-center justify-center px-4">
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-[radial-gradient(circle,rgba(245,158,11,0.06)_0%,transparent_65%)]" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="relative w-full max-w-[420px]"
      >
        <div className="text-center mb-10">
          <button
            type="button"
            onClick={() => nav("/")}
            className="inline-flex items-center gap-2.5 bg-transparent border-none cursor-pointer mb-6"
          >
            <Triangle size={28} strokeWidth={1.8} className="text-accent fill-accent/20" />
            <span className="text-2xl font-bold tracking-tight text-txt-primary">Foresight</span>
          </button>
          <h1 className="text-xl font-bold text-txt-primary mb-2">
            {mode === "register" ? "Create your account" : "Welcome back"}
          </h1>
          <p className="text-sm text-txt-muted">
            {mode === "register"
              ? "Deep analysis and conviction scores for prediction markets"
              : "Sign in to access your signals"
            }
          </p>
        </div>

        <div
          className="bg-surface-card rounded-2xl p-7 shadow-[0_4px_40px_rgba(0,0,0,0.3)]"
          style={{ border: "1px solid rgba(255,255,255,0.06)" }}
        >
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="block text-[11px] font-semibold text-txt-muted uppercase tracking-wider mb-2">
                Email
              </label>
              <div className="relative">
                <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-txt-muted" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  autoComplete="email"
                  className="w-full pl-10"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-txt-muted uppercase tracking-wider mb-2">
                Password
              </label>
              <div className="relative">
                <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-txt-muted" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === "register" ? "At least 8 characters" : "Your password"}
                  required
                  minLength={mode === "register" ? 8 : 1}
                  autoComplete={mode === "register" ? "new-password" : "current-password"}
                  className="w-full pl-10"
                />
              </div>
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center gap-2 p-3 rounded-lg bg-danger/10 text-danger text-sm"
              >
                <AlertCircle size={15} className="shrink-0" />
                {error}
              </motion.div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-xl bg-accent text-surface-0 text-sm font-bold hover:brightness-110 transition-all cursor-pointer border-none flex items-center justify-center gap-2 mt-2 disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_20px_rgba(245,158,11,0.12)]"
            >
              {loading ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <>
                  {mode === "register" ? "Create account" : "Sign in"}
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>

          <div className="flex items-center gap-3 my-6">
            <div className="flex-1 h-px bg-edge" />
            <span className="text-[11px] text-txt-muted">or</span>
            <div className="flex-1 h-px bg-edge" />
          </div>

          <p className="text-center text-sm text-txt-muted">
            {mode === "register" ? (
              <>
                Already have an account?{" "}
                <button
                  type="button"
                  onClick={() => { setMode("login"); setError("") }}
                  className="text-accent font-semibold hover:underline bg-transparent border-none cursor-pointer"
                >
                  Sign in
                </button>
              </>
            ) : (
              <>
                No account yet?{" "}
                <button
                  type="button"
                  onClick={() => { setMode("register"); setError("") }}
                  className="text-accent font-semibold hover:underline bg-transparent border-none cursor-pointer"
                >
                  Create account
                </button>
              </>
            )}
          </p>
        </div>

        <p className="text-center text-[11px] text-txt-muted mt-6 leading-relaxed">
          By continuing you agree to our terms and privacy policy.
        </p>
      </motion.div>
    </div>
  )
}
