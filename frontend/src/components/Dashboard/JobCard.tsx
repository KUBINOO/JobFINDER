import { Badge } from "../ui/badge"
import { cn } from "../../lib/utils"
import { Trash2 } from "lucide-react"

// Status definovaný backendem
export type JobStatus = "Pending" | "Scraping" | "Generating" | "Generated" | "Sending" | "Sent" | "Completed" | "Failed" | "Interview" | "Rejected" | "Offer"

export interface Job {
  id: string
  title: string
  company: string
  status: JobStatus
  dateAdded: string
  match_score?: number
  match_reason?: string
  pros?: string[]
  cons?: string[]
  missing_skills?: string[]
  part_time_viability?: string
  source_portal?: string
  employment_type?: string
  timezone_region?: string
  description?: string
  generated_subject?: string
  generated_body?: string
  error_logs?: string
  url?: string
  source_url?: string
}

interface JobCardProps {
  job: Job
  isSelected?: boolean
  onClick?: () => void
  onDelete?: (e: React.MouseEvent) => void
}

// Mapování anglických stavů na české pro UI
const statusLabelMap: Record<JobStatus, string> = {
  Pending: "Čeká",
  Scraping: "Stahuji data",
  Generating: "Analyzuji",
  Generated: "Připraveno",
  Sending: "Odesílám",
  Sent: "Posláno",
  Completed: "Dokončeno",
  Failed: "Selhalo",
  Interview: "Pohovor",
  Rejected: "Zamítnuto",
  Offer: "Nabídka",
}

// Mapování barev stavů
const statusColorMap: Record<JobStatus, "default" | "secondary" | "destructive" | "outline" | "success" | "warning"> = {
  Pending: "outline",
  Scraping: "warning",
  Generating: "warning",
  Generated: "success",
  Sending: "warning",
  Sent: "success",
  Completed: "success",
  Failed: "destructive",
  Interview: "default",
  Rejected: "destructive",
  Offer: "success",
}

export function JobCard({ job, isSelected, onClick, onDelete }: JobCardProps) {
  const hasScore = typeof job.match_score === "number" && job.match_score !== null

  const getScoreColor = (score?: number | null) => {
    if (score === undefined || score === null) return "text-muted-foreground border-transparent bg-muted/20"
    if (score >= 80) return "text-green-600 dark:text-green-400 border-green-500/30 bg-green-500/10"
    if (score >= 50) return "text-yellow-600 dark:text-yellow-400 border-yellow-500/30 bg-yellow-500/10"
    return "text-red-600 dark:text-red-400 border-red-500/30 bg-red-500/10"
  }

  return (
    <div
      onClick={onClick}
      title={job.match_reason || undefined}
      className={cn(
        "group relative flex flex-col p-4 mb-3 rounded-2xl border transition-all cursor-pointer select-none",
        isSelected
          ? "bg-primary text-primary-foreground border-primary shadow-md"
          : "bg-white/60 dark:bg-black/40 border-white/40 dark:border-white/10 hover:bg-white/80 dark:hover:bg-black/60 shadow-sm hover:shadow"
      )}
    >
      {onDelete && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (onDelete) onDelete(e);
          }}
          className={cn(
            "absolute top-2 right-2 p-1.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity z-10",
            isSelected ? "hover:bg-primary-foreground/20" : "hover:bg-black/10 dark:hover:bg-white/10"
          )}
          title="Smazat pozici"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      )}

      <div className="flex items-start justify-between mb-2">
        <h3 className={cn("font-medium text-base line-clamp-1 flex-1 pr-6", isSelected && "text-primary-foreground")}>
          {job.title}
        </h3>
        {hasScore ? (
          <div className={cn(
            "flex items-center justify-center min-w-9 h-9 px-1.5 shrink-0 rounded-full border text-xs font-bold shadow-xs", 
            isSelected ? "text-primary-foreground border-primary-foreground/50 bg-primary-foreground/20" : getScoreColor(job.match_score)
          )}>
            {job.match_score}%
          </div>
        ) : job.status === "Generating" ? (
          <div className="flex items-center justify-center w-9 h-9 shrink-0 rounded-full bg-primary/10 text-primary animate-pulse text-[10px] font-bold">
            AI...
          </div>
        ) : null}
      </div>

      {/* Štítky zdroje a úvazku */}
      {(job.source_portal || (job.employment_type && job.employment_type !== "UNKNOWN")) && (
        <div className="flex items-center gap-1.5 flex-wrap mb-2.5">
          {job.source_portal && (
            <span className={cn(
              "text-[10px] font-semibold px-1.5 py-0.5 rounded-md",
              isSelected ? "bg-white/20 text-white" : "bg-primary/10 text-primary"
            )}>
              {job.source_portal}
            </span>
          )}
          {job.employment_type && job.employment_type !== "UNKNOWN" && (
            <span className={cn(
              "text-[10px] font-medium px-1.5 py-0.5 rounded-md",
              isSelected ? "bg-white/20 text-white" : "bg-muted text-muted-foreground"
            )}>
              {job.employment_type === "PART_TIME" ? "Part-time" : job.employment_type === "CONTRACTOR_B2B" ? "B2B" : job.employment_type}
            </span>
          )}
          {job.timezone_region && job.timezone_region !== "UNKNOWN" && (
            <span className={cn(
              "text-[10px] font-medium px-1.5 py-0.5 rounded-md",
              isSelected ? "bg-white/20 text-white" : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
            )}>
              {job.timezone_region}
            </span>
          )}
        </div>
      )}

      <div className="flex items-center justify-between mt-auto">
        <span className={cn("text-sm font-medium", isSelected ? "text-primary-foreground/80" : "text-muted-foreground")}>
          {job.company}
        </span>
        <Badge 
          variant={statusColorMap[job.status]} 
          className={cn("ml-2 shrink-0 scale-90", isSelected && 'border-primary-foreground/50 text-primary-foreground')}
        >
          {statusLabelMap[job.status]}
        </Badge>
      </div>
    </div>
  )
}
