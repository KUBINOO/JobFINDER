import { Job, JobStatus, JobCard } from "./JobCard"
import { ScrollArea } from "../ui/scroll-area"
import { motion, AnimatePresence } from "framer-motion"

interface PipelineBoardProps {
  jobs: Job[];
  onJobClick: (job: Job) => void;
  onDeleteJob?: (jobId: string) => void;
  onStatusChange?: (jobId: string, newStatus: JobStatus) => void;
}

const KANBAN_COLUMNS: { id: JobStatus; title: string; badgeVariant: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" }[] = [
  { id: "Generated", title: "Připraveno", badgeVariant: "secondary" },
  { id: "Sent", title: "Odesláno", badgeVariant: "success" },
  { id: "Interview", title: "Pohovor", badgeVariant: "warning" },
  { id: "Offer", title: "Nabídka", badgeVariant: "success" },
  { id: "Rejected", title: "Zamítnuto", badgeVariant: "destructive" },
]

export function PipelineBoard({ jobs, onJobClick, onDeleteJob, onStatusChange }: PipelineBoardProps) {
  return (
    <div className="flex-1 flex gap-6 p-6 h-full overflow-x-auto bg-transparent">
      {KANBAN_COLUMNS.map((col) => {
        // Zahrneme do "Generated" i pozice s vygenerovaným tělem
        const columnJobs = jobs.filter((j) => {
          if (col.id === "Generated") {
            return j.status === "Generated" || (j.status === "Completed" && Boolean(j.generated_body))
          }
          return j.status === col.id
        })

        return (
          <div key={col.id} className="flex flex-col w-80 shrink-0">
            <div className="flex items-center justify-between mb-4 px-2">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-lg">{col.title}</h3>
              </div>
              <span className="text-xs font-medium px-2 py-1 bg-white/40 dark:bg-black/40 rounded-full border border-white/20">
                {columnJobs.length}
              </span>
            </div>
            
            <ScrollArea className="flex-1 h-[calc(100vh-140px)]">
              <div className="flex flex-col gap-3 pb-20 pr-3">
                <AnimatePresence>
                  {columnJobs.map((job) => (
                    <motion.div
                      key={job.id}
                      layoutId={job.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.9 }}
                      transition={{ type: "spring", stiffness: 300, damping: 25 }}
                      className="flex flex-col"
                    >
                      <JobCard 
                        job={job} 
                        onClick={() => onJobClick(job)}
                        onDelete={onDeleteJob ? () => onDeleteJob(job.id) : undefined}
                      />
                      {onStatusChange && (
                        <div 
                          className="-mt-2 mb-3 p-2 bg-white/40 dark:bg-black/30 border border-t-0 border-white/20 dark:border-white/10 rounded-b-xl flex items-center justify-between text-xs"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <span className="text-muted-foreground font-medium">Stav:</span>
                          <select
                            value={job.status}
                            onChange={(e) => onStatusChange(job.id, e.target.value as JobStatus)}
                            className="bg-white/80 dark:bg-black/80 rounded-md px-2 py-1 text-xs font-medium border border-border focus:ring-1 focus:ring-primary cursor-pointer text-foreground"
                          >
                            <option value="Generated">Připraveno</option>
                            <option value="Sent">Odesláno</option>
                            <option value="Interview">Pohovor</option>
                            <option value="Offer">Nabídka</option>
                            <option value="Rejected">Zamítnuto</option>
                          </select>
                        </div>
                      )}
                    </motion.div>
                  ))}
                </AnimatePresence>
                
                {columnJobs.length === 0 && (
                  <div className="text-center p-6 border border-dashed border-white/20 rounded-2xl text-muted-foreground text-sm">
                    Žádné žádosti v tomto stavu
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>
        )
      })}
    </div>
  )
}
