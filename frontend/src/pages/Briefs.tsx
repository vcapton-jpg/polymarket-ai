import { useQuery } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { FileText, Calendar, TrendingUp, Award } from "lucide-react"
import { PageHeader } from "../components/layout/PageHeader"
import { Card } from "../components/ui/Card"
import { Skeleton } from "../components/ui/Skeleton"
import { EmptyState } from "../components/ui/EmptyState"
import { api, queryKeys } from "../lib/api"
import { cn, timeAgo } from "../lib/utils"

export default function Briefs() {
  const { data, isLoading } = useQuery({
    queryKey: queryKeys.agentActivity("reporter"),
    queryFn: () => api.agentActivity("reporter"),
  })

  const briefs = data?.activities?.filter(a => a.action === "daily_brief") || []

  if (isLoading) {
    return (
      <div className="py-8 flex flex-col gap-4">
        <Skeleton height={32} width="40%" />
        <Skeleton height={150} />
        <Skeleton height={150} />
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title="Intelligence Briefs"
        subtitle="Daily and weekly reports from the Reporter Agent"
      />

      {briefs.length === 0 ? (
        <EmptyState
          icon={<FileText size={40} className="text-txt-muted" />}
          title="No briefs yet"
          message="The Reporter Agent generates daily intelligence briefs automatically. Check back soon!"
        />
      ) : (
        <div className="flex flex-col gap-4">
          {briefs.map((brief, i) => {
            const details = brief.details || {}
            const signalsCount = (details.signals_count as number) || 0
            const wins = (details.wins as number) || 0
            const losses = (details.losses as number) || 0
            const winRate = (details.win_rate as number | null)

            return (
              <motion.div
                key={brief.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Card className="p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-cyan-500/15 text-cyan-500 flex items-center justify-center">
                        <FileText size={16} />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-txt-primary">
                          Daily Intelligence Brief
                        </h3>
                        <span className="text-[11px] text-txt-muted flex items-center gap-1">
                          <Calendar size={10} />
                          {timeAgo(brief.at)} ago
                        </span>
                      </div>
                    </div>
                  </div>

                  <p className="text-sm text-txt-secondary mb-3">{brief.summary}</p>

                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-surface-raised rounded-md p-3 text-center">
                      <TrendingUp size={14} className="text-accent mx-auto mb-1" />
                      <span className="text-lg font-bold text-txt-primary block">{signalsCount}</span>
                      <span className="text-[10px] text-txt-muted">Signals</span>
                    </div>
                    <div className="bg-surface-raised rounded-md p-3 text-center">
                      <Award size={14} className="text-success mx-auto mb-1" />
                      <span className="text-lg font-bold text-success block">{wins}</span>
                      <span className="text-[10px] text-txt-muted">Wins</span>
                    </div>
                    <div className="bg-surface-raised rounded-md p-3 text-center">
                      <span className="text-lg font-bold text-txt-primary block">
                        {winRate != null ? `${winRate}%` : "—"}
                      </span>
                      <span className="text-[10px] text-txt-muted">Win Rate</span>
                    </div>
                  </div>
                </Card>
              </motion.div>
            )
          })}
        </div>
      )}
    </div>
  )
}
