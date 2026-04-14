import type { ReactNode } from "react"
import { Card } from "./Card"

interface Props {
  label: string
  value: string | number
  icon: ReactNode
  sub?: string
  trend?: { value: string; positive: boolean } | null
  mono?: boolean
}

export function StatCard({ label, value, icon, sub, trend, mono }: Props) {
  return (
    <Card style={{ padding: "20px 22px" }}>
      <div style={styles.top}>
        <span style={styles.label}>{label}</span>
        <div style={styles.icon}>{icon}</div>
      </div>
      <div
        style={{
          ...styles.value,
          fontFamily: mono ? "var(--font-mono)" : "var(--font-sans)",
        }}
      >
        {value}
      </div>
      {sub && <span style={styles.sub}>{sub}</span>}
      {trend && (
        <span
          style={{
            fontSize: "0.75rem",
            fontWeight: 500,
            color: trend.positive ? "var(--color-success)" : "var(--color-danger)",
          }}
        >
          {trend.value}
        </span>
      )}
    </Card>
  )
}

const styles: Record<string, React.CSSProperties> = {
  top: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "12px",
  },
  label: {
    fontSize: "0.68rem",
    fontWeight: 600,
    color: "var(--text-muted)",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  },
  icon: {
    width: 34,
    height: 34,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: "var(--radius-sm)",
    background: "var(--color-accent-muted)",
    color: "var(--color-accent)",
  },
  value: {
    fontSize: "1.625rem",
    fontWeight: 700,
    color: "var(--text-primary)",
    lineHeight: 1.2,
    marginBottom: "6px",
    letterSpacing: "-0.02em",
  },
  sub: {
    fontSize: "0.75rem",
    color: "var(--text-muted)",
    lineHeight: 1.45,
    display: "block",
  },
}
