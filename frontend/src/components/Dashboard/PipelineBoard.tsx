import { Job, JobStatus, JobCard } from "./JobCard"
import { ScrollArea } from "../ui/scroll-area"
import { motion, AnimatePresence } from "framer-motion"

interface PipelineBoardProps {
  jobs: Job[];
  onJobClick: (job: Job) => void;
  onDeleteJob?: (jobId: string) => void;
}

const KANBAN_COLUMNS: { id: JobStatus; title: string }[] = [
  { id: "Sent", title: "Posláno" },
  { id: "Interview", title: "Pohovor" },
  { id: "Rejected", title: "Zamítnuto" },
  { id: "Offer", title: "Nabídka" },
]

export function PipelineBoard({ jobs, onJobClick, onDeleteJob }: PipelineBoardProps) {
  return (
    <div className="flex-1 flex gap-6 p-6 h-full overflow-x-auto bg-transparent">
      {KANBAN_COLUMNS.map((col) => {
        const columnJobs = jobs.filter((j) => j.status === col.id)

        return (
          <div key={col.id} className="flex flex-col w-80 shrink-0">
            <div className="flex items-center justify-between mb-4 px-2">
              <h3 className="font-semibold text-lg">{col.title}</h3>
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
                    >
                      <JobCard 
                        job={job} 
                        onClick={() => onJobClick(job)}
                        onDelete={onDeleteJob ? () => onDeleteJob(job.id) : undefined}
                      />
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
