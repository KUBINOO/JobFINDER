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
import { Compass, RefreshCw } from "lucide-react"

const API_BASE = "http://localhost:8000/api"

const LOADING_MESSAGES = [
  "Přemýšlím, kde začít...",
  "Otvírám pracovní portály...",
  "Scrapuji inzeráty z jobs.cz...",
  "Analyzuji nalezené pozice...",
  "Prozkoumávám další možnosti...",
  "Filtruji nejlepší shody...",
  "Porovnávám platové ohodnocení...",
  "Dokončuji finální výběr..."
]

export function ExploreModal({ children }: { children?: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  const [count, setCount] = useState<number | "">(10)
  const [query, setQuery] = useState("")
  const [loadingMessageIndex, setLoadingMessageIndex] = useState(0)
  const queryClient = useQueryClient()

  const exploreMutation = useMutation({
    mutationFn: async (data: { jobCount: number, searchQuery: string }) => {
      // Reálné volání backendu
      const res = await axios.post(`${API_BASE}/applications/explore`, { count: data.jobCount, query: data.searchQuery })
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

  // Cycle through loading messages when pending
  useEffect(() => {
    let interval: ReturnType<typeof setInterval>
    if (exploreMutation.isPending) {
      interval = setInterval(() => {
        setLoadingMessageIndex((prev) => (prev + 1) % LOADING_MESSAGES.length)
      }, 3500) // Change message every 3.5 seconds
    } else {
      setLoadingMessageIndex(0)
    }
    return () => clearInterval(interval)
  }, [exploreMutation.isPending])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const parsedCount = Number(count)
    if (parsedCount > 0 && parsedCount <= 20) {
      exploreMutation.mutate({ jobCount: parsedCount, searchQuery: query })
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
            Skript projde dostupné portály a vybere pro vás ty nejlepší pozice podle zadaných kritérií.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-4">
          <div className="space-y-2">
            <label htmlFor="query-input" className="text-sm font-medium">Hledaná pozice (klíčové slovo)</label>
            <Input 
              id="query-input"
              type="text"
              placeholder="např. React Developer, Projektový manažer..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full h-12"
              autoFocus
              disabled={exploreMutation.isPending}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="count-input" className="text-sm font-medium">Počet inzerátů ke stažení (max 20)</label>
            <Input 
              id="count-input"
              type="number"
              min={1}
              max={20}
              placeholder="Zadejte počet (např. 10)"
              value={count}
              onChange={(e) => setCount(e.target.value === "" ? "" : Number(e.target.value))}
              className="w-full h-12"
              disabled={exploreMutation.isPending}
            />
          </div>
          <div className="flex justify-end pt-2">
            <Button 
              type="submit" 
              disabled={count === "" || Number(count) < 1 || Number(count) > 20 || exploreMutation.isPending}
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
