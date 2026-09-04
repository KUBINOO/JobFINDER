import React, { useState } from "react"
import { JobCard, Job, JobStatus } from "./JobCard"
import { ScrollArea } from "../ui/scroll-area"
import { Search, History, Settings, LayoutDashboard, ListTodo, Sun, Moon, Sparkles, Loader2, Heart } from "lucide-react"
import { Button } from "../ui/button"
import { cn } from "../../lib/utils"
import { DetailPanel } from "./DetailPanel"
import { PipelineBoard } from "./PipelineBoard"
import { AddJobModal } from "./AddJobModal"
import { ExploreModal } from "./ExploreModal"
import { HistoryView } from "./HistoryView"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import axios from "axios"
import { SettingsLayout } from "../Settings/SettingsLayout"
import { useTheme } from "../ThemeProvider"

const API_BASE = "http://localhost:8000/api"

export function DashboardLayout() {
  const [activeTab, setActiveTab] = useState<"search" | "history" | "settings">("search")
  const [settingsTab, setSettingsTab] = useState<string>("profile")
  const [viewMode, setViewMode] = useState<"master-detail" | "pipeline">("master-detail")
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  
  const { theme, setTheme } = useTheme()
  const queryClient = useQueryClient()

  const handleOpenSettings = (tab: string = "profile") => {
    setSettingsTab(tab)
    setActiveTab("settings")
  }

  // Fetch jobs with smart polling (only polls when a background job is in progress)
  const { data: jobs = [], isLoading } = useQuery<Job[]>({
    queryKey: ["jobs"],
    queryFn: async () => {
      const res = await axios.get(`${API_BASE}/applications`)
      return res.data
    },
    refetchInterval: (query) => {
      const data = query.state.data as Job[] | undefined
      const hasActiveJobs = data?.some((j) => 
        ["Pending", "Scraping", "Generating", "Sending"].includes(j.status) ||
        (j.status === "Completed" && (j.match_score === undefined || j.match_score === null))
      )
      return hasActiveJobs ? 2000 : false
    },
  })

  // Set selected job on initial load if none selected
  React.useEffect(() => {
    if (!selectedJobId && jobs.length > 0) {
      setSelectedJobId(jobs[0].id)
    }
  }, [jobs.length, selectedJobId])

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

  const matchAllMutation = useMutation({
    mutationFn: async () => {
      const res = await axios.post(`${API_BASE}/applications/match-all`)
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] })
      // Opakované dotazy pro zachycení výsledků background tasků
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["jobs"] }), 3000)
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["jobs"] }), 6000)
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["jobs"] }), 10000)
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      alert("Chyba při spuštění hromadné AI analýzy: " + (detail || err.message))
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
      <div className="w-16 flex-shrink-0 flex flex-col items-center py-5 border-r border-white/20 dark:border-white/10 bg-white/40 dark:bg-black/40 backdrop-blur-2xl z-20">
        <div className="flex flex-col gap-3 flex-1">
          <SidebarIcon 
            icon={<Search />} 
            active={activeTab === "search"} 
            onClick={() => { setActiveTab("search"); setViewMode("master-detail"); }} 
            tooltip="Hledat a žádosti" 
          />
          <SidebarIcon 
            icon={<History />} 
            active={activeTab === "history"} 
            onClick={() => setActiveTab("history")} 
            tooltip="Historie žádostí" 
          />
        </div>

        <div className="flex flex-col gap-3 mb-2">
          <SidebarIcon 
            icon={theme === "dark" ? <Sun /> : <Moon />} 
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")} 
            tooltip="Přepnout motiv" 
          />
          <SidebarIcon 
            icon={<Settings />} 
            active={activeTab === "settings"} 
            onClick={() => setActiveTab("settings")} 
            tooltip="Nastavení" 
          />
        </div>
      </div>

      {/* ZBYTEK OBRAZOVKY S PŘEPÍNAČEM */}
      <div className="flex-1 flex flex-col min-w-0">
        {activeTab === "settings" ? (
          <SettingsLayout initialTab={settingsTab} onBack={() => setActiveTab("search")} />
        ) : activeTab === "history" ? (
          <HistoryView
            jobs={jobs}
            isLoading={isLoading}
            onStatusChange={handleStatusChange}
            onDeleteJob={handleDeleteJob}
            onSelectJobForDetail={(jobId) => {
              setSelectedJobId(jobId)
              setActiveTab("search")
              setViewMode("master-detail")
            }}
          />
        ) : (
          <>
            {/* Top-level Navigation / Tabs */}
            <div className="h-16 flex items-center justify-between px-6 border-b border-white/20 dark:border-white/10 bg-white/30 dark:bg-black/20 backdrop-blur-xl z-20 shrink-0 gap-4">
              <div className="flex items-center gap-6">
                {/* Modern Brand Logo linking to GitHub */}
                <a
                  href="https://github.com/KUBINOO/JobFINDER"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center group cursor-pointer focus:outline-none transition-all duration-200 hover:opacity-80 active:scale-95"
                  title="Otevřít JobFinder na GitHubu (KUBINOO)"
                >
                  <span className="text-2xl font-black tracking-tight font-heading flex items-center gap-1">
                    <span className="text-foreground">Job</span>
                    <span className="bg-gradient-to-r from-blue-600 via-indigo-600 to-violet-600 bg-clip-text text-transparent">Finder</span>
                    <span className="ml-1.5 text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">AI</span>
                  </span>
                </a>

                <div className="h-5 w-[1px] bg-black/10 dark:bg-white/10" />

                {/* View Switcher Tabs */}
                <div className="flex p-1 bg-black/5 dark:bg-white/10 rounded-xl">
                  <button
                    onClick={() => setViewMode("master-detail")}
                    className={cn(
                      "flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-all",
                      viewMode === "master-detail" ? "bg-white dark:bg-black/50 text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <ListTodo className="w-4 h-4" />
                    Nové žádosti
                  </button>
                  <button
                    onClick={() => setViewMode("pipeline")}
                    className={cn(
                      "flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-all",
                      viewMode === "pipeline" ? "bg-white dark:bg-black/50 text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <LayoutDashboard className="w-4 h-4" />
                    Můj Pipeline
                  </button>
                </div>
              </div>

              {/* Right Corner Credit Badge */}
              <a
                href="https://github.com/KUBINOO"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/50 dark:bg-black/30 border border-black/5 dark:border-white/10 text-xs text-muted-foreground hover:text-foreground hover:bg-white/80 dark:hover:bg-black/60 transition-all shadow-sm group cursor-pointer"
                title="Vytvořil KUBINOO na GitHubu"
              >
                <span className="text-[11px] font-medium flex items-center gap-1">
                  made with <Heart className="w-3.5 h-3.5 text-rose-500 fill-rose-500 animate-pulse" />
                </span>
                <span className="text-[11px] font-bold text-foreground group-hover:text-primary transition-colors">
                  by KUBINOO
                </span>
              </a>
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

                    {/* STICKY TLAČÍTKO PRO HROMADNÝ MATCHING */}
                    {jobs.length > 0 && (
                      <div className="p-3 border-t border-white/20 dark:border-white/10 bg-white/40 dark:bg-black/40 backdrop-blur-xl z-20 shrink-0">
                        <Button
                          onClick={() => matchAllMutation.mutate()}
                          disabled={matchAllMutation.isPending || isLoading}
                          className="w-full h-11 rounded-xl font-semibold gap-2 shadow-md bg-gradient-to-r from-primary to-primary/80 hover:from-primary/90 hover:to-primary text-primary-foreground hover:shadow-primary/20 hover:scale-[1.01] transition-all text-xs"
                        >
                          {matchAllMutation.isPending ? (
                            <>
                              <Loader2 className="w-4 h-4 animate-spin" />
                              <span>Vyhodnocuji všechny pozice...</span>
                            </>
                          ) : (
                            <>
                              <Sparkles className="w-4 h-4" />
                              <span>Spočítat AI shodu pro všechny ({jobs.length})</span>
                            </>
                          )}
                        </Button>
                      </div>
                    )}
                  </div>

                  {/* PRAVÝ PANEL (Detail) */}
                  <div className="flex-1 flex flex-col bg-white/10 dark:bg-black/10 relative">
                    <DetailPanel 
                      job={selectedJob} 
                      onStatusChange={handleStatusChange} 
                      onOpenSettings={handleOpenSettings}
                    />
                  </div>
                </>
              ) : (
                <PipelineBoard 
                  jobs={jobs} 
                  onJobClick={(job) => {
                    setSelectedJobId(job.id)
                    setViewMode("master-detail")
                  }} 
                  onDeleteJob={handleDeleteJob} 
                  onStatusChange={handleStatusChange}
                />
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
