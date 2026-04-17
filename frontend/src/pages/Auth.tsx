import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import { GoogleLogin, type CredentialResponse } from "@react-oauth/google"
import { Triangle, ArrowRight, Mail, Lock, AlertCircle, Loader2 } from "lucide-react"
import { useAuth } from "../lib/auth"

const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID

const formStagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06, delayChildren: 0.05 } },
}

const formFadeUp = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] as const },
  },
}

export default function Auth() {
  const nav = useNavigate()
  const { login, register, loginWithGoogle } = useAuth()
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

  const handleGoogleSuccess = async (cred: CredentialResponse) => {
    if (!cred.credential) return
    setError("")
    setLoading(true)
    try {
      await loginWithGoogle(cred.credential)
      nav("/dashboard", { replace: true })
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError("Google sign-in failed")
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface-0 flex items-center justify-center px-4">
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-[radial-gradient(circle,rgba(245,158,11,0.06)_0%,transparent_65%)] shadow-glow" />
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
            <span className="text-2xl font-bold tracking-display font-display text-txt-primary">Foresight</span>
          </button>
          <h1 className="text-xl font-bold text-txt-primary mb-2 font-display tracking-display">
            {mode === "register" ? "Create your account" : "Welcome back"}
          </h1>
          <p className="text-sm text-txt-muted">
            {mode === "register"
              ? "Deep analysis and conviction scores for prediction markets"
              : "Sign in to access your signals"
            }
          </p>
        </div>

        <div className="gradient-border rounded-xl shadow-card">
          <div className="glass-card rounded-xl border border-edge-subtle p-7 shadow-glass">
            {googleClientId ? (
              <>
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                  className="flex justify-center w-full mb-2 [&>div]:!w-full [&_iframe]:!w-full"
                >
                  <GoogleLogin
                    onSuccess={handleGoogleSuccess}
                    onError={() => setError("Google sign-in was cancelled or failed")}
                    theme="filled_black"
                    size="large"
                    width="340"
                    text="continue_with"
                    shape="rectangular"
                  />
                </motion.div>
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: 0.05, ease: [0.22, 1, 0.36, 1] }}
                  className="flex items-center gap-3 my-6"
                >
                  <div className="flex-1 h-px bg-edge-subtle" />
                  <span className="text-[11px] text-txt-muted font-mono">or</span>
                  <div className="flex-1 h-px bg-edge-subtle" />
                </motion.div>
              </>
            ) : null}

            <motion.form
              variants={formStagger}
              initial="hidden"
              animate="visible"
              onSubmit={handleSubmit}
              className="flex flex-col gap-4"
            >
              <motion.div variants={formFadeUp}>
                <label className="block text-[11px] font-semibold text-txt-muted uppercase tracking-wider mb-2 font-display">
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
                    className="w-full pl-10 rounded-lg"
                  />
                </div>
              </motion.div>

              <motion.div variants={formFadeUp}>
                <label className="block text-[11px] font-semibold text-txt-muted uppercase tracking-wider mb-2 font-display">
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
                    className="w-full pl-10 rounded-lg"
                  />
                </div>
              </motion.div>

              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-2 p-3 rounded-lg bg-danger/10 text-danger text-sm border border-edge-subtle"
                >
                  <AlertCircle size={15} className="shrink-0" />
                  {error}
                </motion.div>
              )}

              <motion.button
                variants={formFadeUp}
                type="submit"
                disabled={loading}
                className="w-full py-3 rounded-lg bg-gradient-to-r from-accent to-accent-bright text-surface-0 text-sm font-bold hover:brightness-110 transition-all cursor-pointer border-none flex items-center justify-center gap-2 mt-2 disabled:opacity-50 disabled:cursor-not-allowed shadow-glow hover:shadow-glow-lg"
              >
                {loading ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <>
                    {mode === "register" ? "Create account" : "Sign in"}
                    <ArrowRight size={16} />
                  </>
                )}
              </motion.button>
            </motion.form>

            <motion.p
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
              className="text-center text-sm text-txt-muted mt-6"
            >
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
            </motion.p>
          </div>
        </div>

        <p className="text-center text-[11px] text-txt-muted mt-6 leading-relaxed">
          By continuing you agree to our terms and privacy policy.
        </p>
      </motion.div>
    </div>
  )
}
