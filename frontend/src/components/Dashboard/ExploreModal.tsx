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
import { 
  Compass, 
  RefreshCw, 
  Check, 
  MapPin, 
  Globe, 
  Search, 
  X,
  SlidersHorizontal,
  Building2,
  Sparkles
} from "lucide-react"
import { cn } from "../../lib/utils"
import { CZECH_REGIONS } from "../../constants/regions"

const API_BASE = "http://localhost:8000/api"

const AVAILABLE_PORTALS = [
  { id: "jobs.cz", label: "Jobs.cz", desc: "Největší CZ portál" },
  { id: "prace.cz", label: "Prace.cz", desc: "Široká nabídka pozic" },
  { id: "startupjobs.cz", label: "StartupJobs.cz", desc: "Startupy & inovace" },
  { id: "profesia.cz", label: "Profesia.cz", desc: "Specializované nabídky" },
  { id: "volnamista.cz", label: "VolnaMista.cz", desc: "Regionální pozice" },
]

const LOADING_MESSAGES = [
  "Přemýšlím, kde začít...",
  "Spouštím specializované agenty a API...",
  "Filtruji zadané parametry a úvazky...",
  "Stahuji nabídky z vybraných zdrojů...",
  "Analyzuji a deduplikuji nalezené pozice...",
  "Ověřuji časová pásma (CET / EMEA) a relevanci...",
  "AI počítá match score a shodu s tvým profilem...",
  "Dokončuji finální výběr a zařazuji do pipeline..."
]

export function ExploreModal({ children }: { children?: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  const [count, setCount] = useState<number | "">(10)
  const [query, setQuery] = useState("")
  const [market, setMarket] = useState<"cz" | "global" | "hybrid">("cz")
  const [employmentType, setEmploymentType] = useState<"ALL" | "PART_TIME" | "CONTRACTOR">("PART_TIME")
  const [timezone, setTimezone] = useState<"EMEA" | "WORLDWIDE">("EMEA")
  const [selectedSources, setSelectedSources] = useState<string[]>([
    "jobs.cz",
    "startupjobs.cz",
    "prace.cz"
  ])
  const [selectedRegions, setSelectedRegions] = useState<string[]>([])
  const [regionFilter, setRegionFilter] = useState("")
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

  const toggleRegion = (regionId: string) => {
    if (selectedRegions.includes(regionId)) {
      setSelectedRegions(selectedRegions.filter((id) => id !== regionId))
    } else {
      setSelectedRegions([...selectedRegions, regionId])
    }
  }

  const selectAllRegions = () => {
    setSelectedRegions(CZECH_REGIONS.map((r) => r.id))
  }

  const clearRegions = () => {
    setSelectedRegions([])
  }

  const selectPreset = (preset: "all" | "praha" | "praha_brno") => {
    if (preset === "all") {
      setSelectedRegions([])
    } else if (preset === "praha") {
      setSelectedRegions(["praha"])
    } else if (preset === "praha_brno") {
      setSelectedRegions(["praha", "jihomoravsky"])
    }
  }

  const filteredRegions = CZECH_REGIONS.filter((region) => {
    if (!regionFilter.trim()) return true
    const term = regionFilter.toLowerCase()
    return (
      region.name.toLowerCase().includes(term) ||
      region.city.toLowerCase().includes(term) ||
      (region.tag && region.tag.toLowerCase().includes(term))
    )
  })

  const exploreMutation = useMutation({
    mutationFn: async (data: { 
      jobCount: number
      searchQuery: string
      sources: string[]
      locations: string[] | null 
      market: "cz" | "global" | "hybrid"
      employmentType: "ALL" | "PART_TIME" | "CONTRACTOR"
      timezone: "EMEA" | "WORLDWIDE"
    }) => {
      const res = await axios.post(`${API_BASE}/applications/explore`, { 
        count: data.jobCount, 
        query: data.searchQuery,
        sources: data.sources,
        locations: data.locations && data.locations.length > 0 ? data.locations : null,
        market: data.market,
        employment_type: data.employmentType,
        timezone: data.timezone
      })
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] })
      setOpen(false)
      setCount(10)
      setQuery("")
      setSelectedRegions([])
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
    if (market === "cz" && selectedSources.length === 0) {
      alert("Vyberte alespoň jeden pracovní portál.")
      return
    }
    if (parsedCount > 0 && parsedCount <= 20) {
      exploreMutation.mutate({ 
        jobCount: parsedCount, 
        searchQuery: query,
        sources: selectedSources,
        locations: selectedRegions.length > 0 ? selectedRegions : null,
        market,
        employmentType,
        timezone
      })
    } else {
      alert("Prosím zadejte platný počet (1 - 20).")
    }
  }

  const isAllCzechSelected = selectedRegions.length === 0 || selectedRegions.length === CZECH_REGIONS.length

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
      <DialogContent className="sm:max-w-2xl max-h-[90vh] flex flex-col p-0 overflow-hidden bg-background/95 backdrop-blur-xl border border-white/20 dark:border-white/10 shadow-2xl">
        <DialogHeader className="p-6 pb-4 border-b border-border/40 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-primary/10 text-primary">
              <Compass className="w-5 h-5" />
            </div>
            <div>
              <DialogTitle className="text-xl font-bold">Prozkoumat pracovní portály</DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                Automaticky vyhledá inzeráty podle pozice, vybraných portálů a požadovaných krajů.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* 0. Volba cílového trhu */}
          <div className="space-y-2">
            <label className="text-sm font-semibold flex items-center gap-2">
              <Globe className="w-4 h-4 text-primary" />
              <span>Cílový pracovní trh</span>
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setMarket("cz")}
                disabled={exploreMutation.isPending}
                className={cn(
                  "flex flex-col items-center justify-center p-2.5 rounded-xl border text-xs font-semibold transition-all",
                  market === "cz"
                    ? "bg-primary text-primary-foreground border-primary shadow-sm ring-1 ring-primary/30"
                    : "bg-white/40 dark:bg-black/20 border-border/60 text-muted-foreground hover:bg-white/80 dark:hover:bg-white/5 hover:text-foreground"
                )}
              >
                <span className="text-lg mb-0.5">🇨🇿</span>
                <span>Český trh</span>
              </button>
              <button
                type="button"
                onClick={() => setMarket("global")}
                disabled={exploreMutation.isPending}
                className={cn(
                  "flex flex-col items-center justify-center p-2.5 rounded-xl border text-xs font-semibold transition-all",
                  market === "global"
                    ? "bg-primary text-primary-foreground border-primary shadow-sm ring-1 ring-primary/30"
                    : "bg-white/40 dark:bg-black/20 border-border/60 text-muted-foreground hover:bg-white/80 dark:hover:bg-white/5 hover:text-foreground"
                )}
              >
                <span className="text-lg mb-0.5">🌍</span>
                <span>Globální Remote</span>
              </button>
              <button
                type="button"
                onClick={() => setMarket("hybrid")}
                disabled={exploreMutation.isPending}
                className={cn(
                  "flex flex-col items-center justify-center p-2.5 rounded-xl border text-xs font-semibold transition-all",
                  market === "hybrid"
                    ? "bg-primary text-primary-foreground border-primary shadow-sm ring-1 ring-primary/30"
                    : "bg-white/40 dark:bg-black/20 border-border/60 text-muted-foreground hover:bg-white/80 dark:hover:bg-white/5 hover:text-foreground"
                )}
              >
                <span className="text-lg mb-0.5">🌐</span>
                <span>Kombinovaný</span>
              </button>
            </div>
          </div>

          {/* 1. Hledaná pozice */}
          <div className="space-y-2">
            <label htmlFor="query-input" className="text-sm font-semibold flex items-center gap-2">
              <Search className="w-4 h-4 text-primary" />
              <span>Hledaná pozice / klíčové slovo</span>
            </label>
            <Input 
              id="query-input"
              type="text"
              placeholder={market === "cz" ? "např. React Developer, Projektový manažer, Finanční analytik..." : "e.g. React Developer, Python, Full Stack, DevOps..."}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full h-11 text-base bg-white/50 dark:bg-black/30 border-border/60 focus-visible:ring-primary"
              autoFocus
              disabled={exploreMutation.isPending}
            />
          </div>

          {/* Globální Multi-Agentní panel */}
          {(market === "global" || market === "hybrid") && (
            <div className="p-4 rounded-xl bg-primary/5 border border-primary/20 space-y-3.5">
              <div className="flex items-center justify-between">
                <div className="text-xs font-bold text-primary flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4" />
                  Multi-agentní vyhledávání (RemoteOK, Remotive, WWR, Arbeitnow)
                </div>
                <span className="text-[11px] text-muted-foreground">Paralelní scraping</span>
              </div>

              {/* Úvazek */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground/90">Požadovaný typ úvazku / spolupráce:</label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setEmploymentType("PART_TIME")}
                    disabled={exploreMutation.isPending}
                    className={cn(
                      "py-2 px-2 rounded-lg text-xs font-semibold border transition-all text-center",
                      employmentType === "PART_TIME"
                        ? "bg-primary text-primary-foreground border-primary shadow-sm"
                        : "bg-white/40 dark:bg-black/20 border-border/60 text-muted-foreground hover:text-foreground"
                    )}
                  >
                    🎓 Part-time / Student
                  </button>
                  <button
                    type="button"
                    onClick={() => setEmploymentType("CONTRACTOR")}
                    disabled={exploreMutation.isPending}
                    className={cn(
                      "py-2 px-2 rounded-lg text-xs font-semibold border transition-all text-center",
                      employmentType === "CONTRACTOR"
                        ? "bg-primary text-primary-foreground border-primary shadow-sm"
                        : "bg-white/40 dark:bg-black/20 border-border/60 text-muted-foreground hover:text-foreground"
                    )}
                  >
                    💼 B2B / Kontrakt
                  </button>
                  <button
                    type="button"
                    onClick={() => setEmploymentType("ALL")}
                    disabled={exploreMutation.isPending}
                    className={cn(
                      "py-2 px-2 rounded-lg text-xs font-semibold border transition-all text-center",
                      employmentType === "ALL"
                        ? "bg-primary text-primary-foreground border-primary shadow-sm"
                        : "bg-white/40 dark:bg-black/20 border-border/60 text-muted-foreground hover:text-foreground"
                    )}
                  >
                    Všechny úvazky
                  </button>
                </div>
              </div>

              {/* Timezone */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground/90">Časové pásmo uchazeče:</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setTimezone("EMEA")}
                    disabled={exploreMutation.isPending}
                    className={cn(
                      "py-2 px-2.5 rounded-lg text-xs font-semibold border transition-all text-left flex items-center justify-between",
                      timezone === "EMEA"
                        ? "bg-emerald-600 text-white border-emerald-600 shadow-sm"
                        : "bg-white/40 dark:bg-black/20 border-border/60 text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <span>🇪🇺 CET / EMEA overlap</span>
                    {timezone === "EMEA" && <Check className="w-3.5 h-3.5 shrink-0 ml-1" />}
                  </button>
                  <button
                    type="button"
                    onClick={() => setTimezone("WORLDWIDE")}
                    disabled={exploreMutation.isPending}
                    className={cn(
                      "py-2 px-2.5 rounded-lg text-xs font-semibold border transition-all text-left flex items-center justify-between",
                      timezone === "WORLDWIDE"
                        ? "bg-primary text-primary-foreground border-primary shadow-sm"
                        : "bg-white/40 dark:bg-black/20 border-border/60 text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <span>🌐 Celý svět (Async / Worldwide)</span>
                    {timezone === "WORLDWIDE" && <Check className="w-3.5 h-3.5 shrink-0 ml-1" />}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* České portály a regiony (pouze pro CZ nebo Hybrid trh) */}
          {(market === "cz" || market === "hybrid") && (
            <>
              {/* 2. Zdroje pro vyhledávání (Portály) */}
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-semibold flex items-center gap-2">
                    <Building2 className="w-4 h-4 text-primary" />
                    <span>České pracovní portály ({selectedSources.length}/{AVAILABLE_PORTALS.length})</span>
                  </label>
                  <span className="text-xs text-muted-foreground">Vyberte zdroje</span>
                </div>
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
                          "flex items-center justify-between p-2.5 rounded-xl border text-xs font-medium transition-all text-left group",
                          isSelected
                            ? "bg-primary text-primary-foreground border-primary shadow-sm ring-1 ring-primary/30"
                            : "bg-white/40 dark:bg-black/20 border-border/60 text-muted-foreground hover:bg-white/80 dark:hover:bg-white/5 hover:text-foreground"
                        )}
                      >
                        <div>
                          <div className="font-semibold text-xs">{portal.label}</div>
                          <div className={cn("text-[10px] opacity-80", isSelected ? "text-primary-foreground/80" : "text-muted-foreground")}>
                            {portal.desc}
                          </div>
                        </div>
                        {isSelected ? (
                          <Check className="w-4 h-4 shrink-0 ml-1 text-primary-foreground" />
                        ) : (
                          <div className="w-4 h-4 rounded-full border border-border/80 shrink-0 ml-1 opacity-0 group-hover:opacity-60 transition-opacity" />
                        )}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* 3. Vymezení krajů a měst (Lokalita) */}
              <div className="space-y-3 pt-1">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <label className="text-sm font-semibold flex items-center gap-2">
                    <MapPin className="w-4 h-4 text-primary" />
                    <span>Vymezení krajů & měst v ČR</span>
                    <span className={cn(
                      "text-[11px] font-medium px-2 py-0.5 rounded-full",
                      isAllCzechSelected
                        ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30"
                        : "bg-primary/15 text-primary border border-primary/30"
                    )}>
                      {isAllCzechSelected 
                        ? "🇨🇿 Celá ČR (14 krajů)" 
                        : `📍 ${selectedRegions.length} ${selectedRegions.length === 1 ? "vybraný kraj" : selectedRegions.length < 5 ? "vybrané kraje" : "vybraných krajů"}`}
                    </span>
                  </label>
                  
                  {/* Presety */}
                  <div className="flex items-center gap-1.5 text-xs">
                    <button
                      type="button"
                      onClick={() => selectPreset("all")}
                      disabled={exploreMutation.isPending}
                      className={cn(
                        "px-2.5 py-1 rounded-lg text-xs font-medium border transition-all",
                        isAllCzechSelected
                          ? "bg-primary text-primary-foreground border-primary"
                          : "bg-white/40 dark:bg-black/20 border-border/50 text-muted-foreground hover:text-foreground"
                      )}
                    >
                      Celá ČR
                    </button>
                    <button
                      type="button"
                      onClick={() => selectPreset("praha")}
                      disabled={exploreMutation.isPending}
                      className={cn(
                        "px-2.5 py-1 rounded-lg text-xs font-medium border transition-all",
                        selectedRegions.length === 1 && selectedRegions[0] === "praha"
                          ? "bg-primary text-primary-foreground border-primary"
                          : "bg-white/40 dark:bg-black/20 border-border/50 text-muted-foreground hover:text-foreground"
                      )}
                    >
                      Jen Praha
                    </button>
                    <button
                      type="button"
                      onClick={() => selectPreset("praha_brno")}
                      disabled={exploreMutation.isPending}
                      className={cn(
                        "px-2.5 py-1 rounded-lg text-xs font-medium border transition-all",
                        selectedRegions.length === 2 && selectedRegions.includes("praha") && selectedRegions.includes("jihomoravsky")
                          ? "bg-primary text-primary-foreground border-primary"
                          : "bg-white/40 dark:bg-black/20 border-border/50 text-muted-foreground hover:text-foreground"
                      )}
                    >
                      Praha + Brno
                    </button>
                    {selectedRegions.length > 0 && !isAllCzechSelected && (
                      <button
                        type="button"
                        onClick={clearRegions}
                        disabled={exploreMutation.isPending}
                        className="p-1 rounded-lg text-muted-foreground hover:text-rose-500 transition-colors"
                        title="Zrušit výběr (nastavit na celou ČR)"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Filtr pro kraje / města */}
                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    type="text"
                    placeholder="Rychle vyhledat kraj nebo město (např. Plzeň, Jihlava, Ostrava, Olomouc...)"
                    value={regionFilter}
                    onChange={(e) => setRegionFilter(e.target.value)}
                    className="h-9 pl-8 text-xs bg-white/30 dark:bg-black/20 border-border/40"
                    disabled={exploreMutation.isPending}
                  />
                  {regionFilter && (
                    <button
                      type="button"
                      onClick={() => setRegionFilter("")}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                {/* Mřížka 14 českých krajů */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-56 overflow-y-auto p-1 pr-2 rounded-xl border border-border/40 bg-black/5 dark:bg-white/5 scrollbar-thin">
                  {filteredRegions.map((region) => {
                    const isSelected = selectedRegions.includes(region.id)
                    return (
                      <button
                        key={region.id}
                        type="button"
                        onClick={() => toggleRegion(region.id)}
                        disabled={exploreMutation.isPending}
                        className={cn(
                          "flex items-center justify-between p-2 rounded-xl border text-left transition-all group",
                          isSelected
                            ? "bg-primary/10 border-primary text-foreground shadow-sm ring-1 ring-primary/40"
                            : "bg-card/70 border-border/50 text-muted-foreground hover:bg-card hover:text-foreground hover:border-border"
                        )}
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          <span className="text-base shrink-0">{region.icon}</span>
                          <div className="min-w-0">
                            <div className="flex items-center gap-1.5">
                              <span className={cn("text-xs font-semibold truncate", isSelected ? "text-primary dark:text-primary-foreground font-bold" : "text-foreground")}>
                                {region.name}
                              </span>
                              {region.tag && (
                                <span className="text-[9px] px-1.5 py-0.2 rounded bg-primary/10 text-primary shrink-0 hidden sm:inline">
                                  {region.tag}
                                </span>
                              )}
                            </div>
                            <div className="text-[11px] text-muted-foreground truncate">
                              Sídlo: <span className="font-medium text-foreground/80">{region.city}</span>
                            </div>
                          </div>
                        </div>

                        <div className={cn(
                          "w-5 h-5 rounded-lg flex items-center justify-center shrink-0 ml-2 transition-all",
                          isSelected
                            ? "bg-primary text-primary-foreground"
                            : "border border-border/80 bg-background/50"
                        )}>
                          {isSelected && <Check className="w-3.5 h-3.5 stroke-[2.5]" />}
                        </div>
                      </button>
                    )
                  })}
                  {filteredRegions.length === 0 && (
                    <div className="col-span-2 py-6 text-center text-xs text-muted-foreground">
                      Nenalezen žádný kraj ani město pro &quot;{regionFilter}&quot;
                    </div>
                  )}
                </div>

                {/* Vybrané info badge */}
                <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
                  <div className="flex items-center gap-1.5 truncate">
                    <Globe className="w-3.5 h-3.5 text-primary shrink-0" />
                    <span className="truncate">
                      {selectedRegions.length === 0 ? (
                        <span>Prohledává se celá ČR bez omezení</span>
                      ) : (
                        <span>
                          Vybráno: <strong className="text-foreground">{selectedRegions.map(id => CZECH_REGIONS.find(r => r.id === id)?.city).join(", ")}</strong>
                        </span>
                      )}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={selectAllRegions}
                    disabled={exploreMutation.isPending}
                    className="text-xs text-primary hover:underline shrink-0 ml-2"
                  >
                    Vybrat všech 14 krajů
                  </button>
                </div>
              </div>
            </>
          )}

          {/* 4. Počet inzerátů ke stažení */}
          <div className="space-y-2 pt-1 border-t border-border/40">
            <div className="flex items-center justify-between">
              <label htmlFor="count-input" className="text-sm font-semibold flex items-center gap-2">
                <SlidersHorizontal className="w-4 h-4 text-primary" />
                <span>Počet inzerátů ke stažení</span>
              </label>
              <span className="text-xs text-muted-foreground">Doporučeno 5 – 15</span>
            </div>
            <div className="flex items-center gap-3">
              <Input 
                id="count-input"
                type="number"
                min={1}
                max={20}
                placeholder="Zadejte počet (např. 10)"
                value={count}
                onChange={(e) => setCount(e.target.value === "" ? "" : Number(e.target.value))}
                className="w-32 h-11 text-center font-bold text-lg bg-white/50 dark:bg-black/30 border-border/60"
                disabled={exploreMutation.isPending}
              />
              <div className="flex items-center gap-1.5 flex-1">
                {[5, 10, 15, 20].map((num) => (
                  <button
                    key={num}
                    type="button"
                    onClick={() => setCount(num)}
                    disabled={exploreMutation.isPending}
                    className={cn(
                      "flex-1 h-11 rounded-xl text-xs font-semibold border transition-all",
                      count === num
                        ? "bg-primary text-primary-foreground border-primary shadow-sm"
                        : "bg-white/40 dark:bg-black/20 border-border/50 text-muted-foreground hover:bg-white/80 dark:hover:bg-white/5 hover:text-foreground"
                    )}
                  >
                    {num} pozic
                  </button>
                ))}
              </div>
            </div>
          </div>
        </form>

        {/* Footer */}
        <div className="p-4 px-6 border-t border-border/40 bg-card/40 flex items-center justify-between gap-3 shrink-0">
          <Button
            type="button"
            variant="ghost"
            onClick={() => setOpen(false)}
            disabled={exploreMutation.isPending}
            className="text-muted-foreground hover:text-foreground"
          >
            Zrušit
          </Button>

          <Button 
            type="button"
            onClick={handleSubmit}
            disabled={
              count === "" || 
              Number(count) < 1 || 
              Number(count) > 20 || 
              selectedSources.length === 0 || 
              exploreMutation.isPending
            }
            className="h-11 px-6 font-semibold shadow-lg shadow-primary/20 transition-all duration-300 min-w-[220px]"
          >
            {exploreMutation.isPending ? (
              <div className="flex items-center w-full justify-center">
                <RefreshCw className="w-4 h-4 mr-2.5 animate-spin shrink-0" />
                <span className="animate-pulse text-xs truncate max-w-[170px]">
                  {LOADING_MESSAGES[loadingMessageIndex]}
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Compass className="w-4 h-4" />
                <span>Spustit prozkoumávání</span>
              </div>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
