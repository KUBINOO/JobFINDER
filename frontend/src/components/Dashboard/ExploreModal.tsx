import React, { useState, useEffect } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
} from "../ui/dialog"
import { Button } from "../ui/button"
import { Input } from "../ui/input"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import axios from "axios"
import { Compass, RefreshCw, Check } from "lucide-react"
import { cn } from "../../lib/utils"

const API_BASE = "http://localhost:8000/api"

const AVAILABLE_PORTALS = [
  { id: "jobs.cz", label: "Jobs.cz" },
  { id: "prace.cz", label: "Prace.cz" },
  { id: "startupjobs.cz", label: "StartupJobs.cz" },
  { id: "profesia.cz", label: "Profesia.cz" },
  { id: "volnamista.cz", label: "VolnaMista.cz" },
]

const LOADING_MESSAGES = [
  "Přemýšlím, kde začít...",
  "Otvírám vybrané pracovní portály...",
  "Scrapuji inzeráty z Jobs.cz a dalších zdrojů...",
  "Analyzuji a filtruji nalezené pozice...",
  "Rovnoměrně rozděluji kvótu mezi vybrané weby...",
  "Porovnávám relevanci a texty inzerátů...",
  "Dokončuji finální výběr a zařazuji do pipeline..."
]

export function ExploreModal({ children }: { children?: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  const [count, setCount] = useState<number | "">(10)
  const [query, setQuery] = useState("")
  const [selectedSources, setSelectedSources] = useState<string[]>([
    "jobs.cz",
    "startupjobs.cz",
    "prace.cz"
  ])
  const [loadingMessageIndex, setLoadingMessageIndex] = useState(0)
  const queryClient = useQueryClient()

  const toggleSource = (sourceId: string) => {
    if (selectedSources.includes(sourceId)) {
      if (selectedSources.length === 1) {
        alert("Musí zůstat vybraný alespoň jeden portál.")
        return
      }
      setSelectedSources(selectedSources.filter((id) => id !== sourceId))
    } else {
      setSelectedSources([...selectedSources, sourceId])
    }
  }

  const exploreMutation = useMutation({
    mutationFn: async (data: { jobCount: number, searchQuery: string, sources: string[] }) => {
      const res = await axios.post(`${API_BASE}/applications/explore`, { 
        count: data.jobCount, 
        query: data.searchQuery,
        sources: data.sources
      })
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] })
      setOpen(false)
      setCount(10)
      setQuery("")
      alert("Prozkoumávání dokončeno. Nové pozice byly přidány ke zpracování.")
    },
    onError: (err: any) => {
      alert(`Chyba při hromadném prohledávání: ${err.response?.data?.detail || err.message}`)
      setOpen(false)
    }
  })

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>
    if (exploreMutation.isPending) {
      interval = setInterval(() => {
        setLoadingMessageIndex((prev) => (prev + 1) % LOADING_MESSAGES.length)
      }, 3500)
    } else {
      setLoadingMessageIndex(0)
    }
    return () => clearInterval(interval)
  }, [exploreMutation.isPending])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const parsedCount = Number(count)
    if (selectedSources.length === 0) {
      alert("Vyberte alespoň jeden pracovní portál.")
      return
    }
    if (parsedCount > 0 && parsedCount <= 20) {
      exploreMutation.mutate({ 
        jobCount: parsedCount, 
        searchQuery: query,
        sources: selectedSources 
      })
    } else {
      alert("Prosím zadejte platný počet (1 - 20).")
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {children || (
          <Button className="w-full h-12 rounded-xl shadow-lg hover:shadow-xl transition-all flex items-center justify-center gap-2 bg-primary text-primary-foreground">
            <Compass className="w-5 h-5" />
            <span className="font-semibold text-lg">Prozkoumat pozice</span>
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Prozkoumat pracovní portály</DialogTitle>
          <DialogDescription>
            Skript projde vybrané portály a rozdělí mezi ně požadovaný počet inzerátů.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-3">
          <div className="space-y-2">
            <label htmlFor="query-input" className="text-sm font-medium">Hledaná pozice (klíčové slovo)</label>
            <Input 
              id="query-input"
              type="text"
              placeholder="např. React Developer, Projektový manažer..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full h-11"
              autoFocus
              disabled={exploreMutation.isPending}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">
              Zdroje pro vyhledávání ({selectedSources.length}/{AVAILABLE_PORTALS.length})
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {AVAILABLE_PORTALS.map((portal) => {
                const isSelected = selectedSources.includes(portal.id)
                return (
                  <button
                    key={portal.id}
                    type="button"
                    onClick={() => toggleSource(portal.id)}
                    disabled={exploreMutation.isPending}
                    className={cn(
                      "flex items-center justify-between px-3 py-2 rounded-xl border text-xs font-medium transition-all text-left",
                      isSelected
                        ? "bg-primary text-primary-foreground border-primary shadow-sm"
                        : "bg-black/5 dark:bg-white/5 border-border/50 text-muted-foreground hover:bg-black/10 dark:hover:bg-white/10"
                    )}
                  >
                    <span>{portal.label}</span>
                    {isSelected && <Check className="w-3.5 h-3.5 ml-1.5 shrink-0" />}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="space-y-2">
            <label htmlFor="count-input" className="text-sm font-medium">Počet inzerátů ke stažení (max 20)</label>
            <Input 
              id="count-input"
              type="number"
              min={1}
              max={20}
              placeholder="Zadejte počet (např. 7)"
              value={count}
              onChange={(e) => setCount(e.target.value === "" ? "" : Number(e.target.value))}
              className="w-full h-11"
              disabled={exploreMutation.isPending}
            />
          </div>

          <div className="flex justify-end pt-2">
            <Button 
              type="submit" 
              disabled={
                count === "" || 
                Number(count) < 1 || 
                Number(count) > 20 || 
                selectedSources.length === 0 || 
                exploreMutation.isPending
              }
              className="w-full sm:w-auto h-11 transition-all duration-500 min-w-[200px]"
            >
              {exploreMutation.isPending ? (
                <div className="flex items-center w-full justify-center">
                  <RefreshCw className="w-4 h-4 mr-3 animate-spin flex-shrink-0" />
                  <span className="animate-pulse">{LOADING_MESSAGES[loadingMessageIndex]}</span>
                </div>
              ) : (
                "Spustit prozkoumávání"
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
