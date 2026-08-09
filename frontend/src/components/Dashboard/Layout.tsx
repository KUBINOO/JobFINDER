import React, { useState } from "react"
import { JobCard, Job, JobStatus } from "./JobCard"
import { ScrollArea } from "../ui/scroll-area"
import { Button } from "../ui/button"
import { Search, History, Settings, Send, RefreshCw, Briefcase, LayoutDashboard, ListTodo, Sun, Moon } from "lucide-react"
import { cn } from "../../lib/utils"
import { DetailPanel } from "./DetailPanel"
import { PipelineBoard } from "./PipelineBoard"
import { AddJobModal } from "./AddJobModal"
import { ExploreModal } from "./ExploreModal"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import axios from "axios"
import { SettingsLayout } from "../Settings/SettingsLayout"
import { useTheme } from "../ThemeProvider"

const API_BASE = "http://localhost:8000/api"

export function DashboardLayout() {
  const [activeTab, setActiveTab] = useState<"search" | "history" | "settings">("search")
  const [viewMode, setViewMode] = useState<"master-detail" | "pipeline">("master-detail")
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  
  const { theme, setTheme } = useTheme()
  const queryClient = useQueryClient()

  // Fetch jobs
  const { data: jobs = [], isLoading } = useQuery<Job[]>({
    queryKey: ["jobs"],
    queryFn: async () => {
      const res = await axios.get(`${API_BASE}/applications`)
      return res.data
    },
    refetchInterval: 3000, // Poll every 3 seconds for live updates
  })

  // Set selected job on initial load if none selected
  React.useEffect(() => {
    if (!selectedJobId && jobs.length > 0) {
      setSelectedJobId(jobs[0].id)
    }
  }, [jobs, selectedJobId])

  const selectedJob = jobs.find((j) => j.id === selectedJobId) || null


  // Update status (for pipeline board clicks or DetailPanel)
  const updateStatusMutation = useMutation({
    mutationFn: async ({ id, status }: { id: string, status: JobStatus }) => {
      const res = await axios.patch(`${API_BASE}/applications/${id}`, { status: status.toUpperCase() })
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] })
    }
  })

  const handleStatusChange = (jobId: string, newStatus: JobStatus) => {
    updateStatusMutation.mutate({ id: jobId, status: newStatus })
  }

  const deleteJobMutation = useMutation({
    mutationFn: async (id: string) => {
      await axios.delete(`${API_BASE}/applications/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] })
      if (selectedJobId) {
        setSelectedJobId(null)
      }
    }
  })

  const handleDeleteJob = (jobId: string) => {
    if (window.confirm("Opravdu chcete smazat tuto žádost?")) {
      deleteJobMutation.mutate(jobId)
    }
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-transparent">
      {/* LEVÝ PANEL (Sidebar) */}
      <div className="w-16 flex-shrink-0 flex flex-col items-center py-6 border-r border-white/20 dark:border-white/10 bg-white/40 dark:bg-black/40 backdrop-blur-2xl z-20">
        <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center text-primary-foreground mb-8 shadow-lg">
          <Briefcase className="w-5 h-5" />
        </div>
        
        <div className="flex flex-col gap-4 flex-1 mt-4">
          <SidebarIcon icon={<Search />} active={activeTab === "search"} onClick={() => setActiveTab("search")} tooltip="Hledat" />
          <SidebarIcon icon={<History />} active={activeTab === "history"} onClick={() => setActiveTab("history")} tooltip="Historie" />
        </div>

        <div className="flex flex-col gap-4 mb-4">
          <SidebarIcon 
            icon={theme === "dark" ? <Sun /> : <Moon />} 
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")} 
            tooltip="Přepnout motiv" 
          />
          <SidebarIcon icon={<Settings />} active={activeTab === "settings"} onClick={() => setActiveTab("settings")} tooltip="Nastavení" />
        </div>
      </div>

      {/* ZBYTEK OBRAZOVKY S PŘEPÍNAČEM */}
      <div className="flex-1 flex flex-col">
        {activeTab === "settings" ? (
          <SettingsLayout />
        ) : (
          <>
            {/* Top-level Navigation / Tabs */}
            <div className="h-16 flex items-center px-6 border-b border-white/20 dark:border-white/10 bg-white/30 dark:bg-black/20 backdrop-blur-xl z-20 shrink-0 gap-4">
          <div className="flex p-1 bg-black/5 dark:bg-white/10 rounded-xl">
            <button
              onClick={() => setViewMode("master-detail")}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all",
                viewMode === "master-detail" ? "bg-white dark:bg-black/50 text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              )}
            >
              <ListTodo className="w-4 h-4" />
              Nové žádosti
            </button>
            <button
              onClick={() => setViewMode("pipeline")}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all",
                viewMode === "pipeline" ? "bg-white dark:bg-black/50 text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              )}
            >
              <LayoutDashboard className="w-4 h-4" />
              Můj Pipeline
            </button>
          </div>
        </div>

        {/* Dynamic Content based on View Mode */}
        <div className="flex-1 flex overflow-hidden">
          {viewMode === "master-detail" ? (
            <>
              {/* STŘEDNÍ PANEL (Master) */}
              <div className="w-[380px] flex-shrink-0 flex flex-col border-r border-white/20 dark:border-white/10 bg-white/30 dark:bg-black/20 backdrop-blur-xl relative z-10">
                <div className="p-4 pt-6 z-20">
                  <div className="flex items-center justify-between mb-4 px-2">
                    <h2 className="text-xl font-semibold tracking-tight">Aktivní pozice</h2>
                    <Badge count={jobs.length} />
                  </div>
                  
                  <div className="mb-4 space-y-3">
                    <ExploreModal />
                    <AddJobModal />
                  </div>
                </div>

                <ScrollArea className="flex-1 px-4">
                  <div className="pb-6">
                    {isLoading && jobs.length === 0 ? (
                      <div className="text-center py-10 text-muted-foreground">Načítání...</div>
                    ) : jobs.length === 0 ? (
                      <div className="text-center py-10 text-muted-foreground">Zatím nemáte žádné pozice</div>
                    ) : (
                      jobs.map((job) => (
                        <JobCard
                          key={job.id}
                          job={job}
                          isSelected={job.id === selectedJobId}
                          onClick={() => setSelectedJobId(job.id)}
                          onDelete={() => handleDeleteJob(job.id)}
                        />
                      ))
                    )}
                  </div>
                </ScrollArea>
              </div>

              {/* PRAVÝ PANEL (Detail) */}
              <div className="flex-1 flex flex-col bg-white/10 dark:bg-black/10 relative">
                <DetailPanel job={selectedJob} onStatusChange={handleStatusChange} />
              </div>
            </>
          ) : (
            <PipelineBoard jobs={jobs} onJobClick={(job) => {
              setSelectedJobId(job.id)
              setViewMode("master-detail")
            }} onDeleteJob={handleDeleteJob} />
          )}
        </div>
          </>
        )}
      </div>
    </div>
  )
}

function SidebarIcon({ icon, active, onClick, tooltip }: { icon: React.ReactNode; active?: boolean; onClick?: () => void; tooltip?: string }) {
  return (
    <button
      onClick={onClick}
      title={tooltip}
      className={cn(
        "w-12 h-12 flex items-center justify-center rounded-xl transition-all duration-200",
        active 
          ? "bg-black/5 dark:bg-white/10 text-foreground shadow-sm" 
          : "text-muted-foreground hover:bg-black/5 dark:hover:bg-white/5 hover:text-foreground"
      )}
    >
      {React.cloneElement(icon as React.ReactElement, { className: "w-5 h-5" })}
    </button>
  )
}

function Badge({ count }: { count: number }) {
  if (count === 0) return null
  return (
    <span className="flex items-center justify-center min-w-[20px] h-5 px-1.5 text-[11px] font-bold bg-primary text-primary-foreground rounded-full">
      {count}
    </span>
  )
}
