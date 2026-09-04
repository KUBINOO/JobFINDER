import { useState, useMemo } from "react"
import { Job, JobStatus } from "./JobCard"
import { Badge } from "../ui/badge"
import { Button } from "../ui/button"
import { Input } from "../ui/input"
import { ScrollArea } from "../ui/scroll-area"
import {
  History,
  Search,
  Download,
  ExternalLink,
  Eye,
  Trash2,
  CheckCircle2,
  Sparkles,
  Mail,
  Building2,
  Calendar,
  Layers,
  LayoutList,
  LayoutGrid,
  Copy,
  Check,
  Briefcase,
  TrendingUp,
  Award,
} from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "../ui/dialog"

interface HistoryViewProps {
  jobs: Job[]
  isLoading?: boolean
  onStatusChange: (jobId: string, newStatus: JobStatus) => void
  onDeleteJob: (jobId: string) => void
  onSelectJobForDetail: (jobId: string) => void
}

const statusLabelMap: Record<JobStatus, string> = {
  Pending: "Čeká",
  Scraping: "Stahuji",
  Generating: "Analyzuji",
  Generated: "Připraveno",
  Sending: "Odesílám",
  Sent: "Odesláno",
  Completed: "Dokončeno",
  Failed: "Chyba",
  Interview: "Pohovor",
  Rejected: "Zamítnuto",
  Offer: "Nabídka",
}

const statusBadgeVariant: Record<JobStatus, "default" | "secondary" | "destructive" | "outline" | "success" | "warning"> = {
  Pending: "outline",
  Scraping: "warning",
  Generating: "warning",
  Generated: "secondary",
  Sending: "warning",
  Sent: "success",
  Completed: "success",
  Failed: "destructive",
  Interview: "default",
  Rejected: "destructive",
  Offer: "success",
}

type FilterCategory = "all" | "sent" | "interview" | "offer" | "rejected" | "draft"

export function HistoryView({
  jobs,
  isLoading,
  onStatusChange,
  onDeleteJob,
  onSelectJobForDetail,
}: HistoryViewProps) {
  const [searchQuery, setSearchQuery] = useState("")
  const [filterCategory, setFilterCategory] = useState<FilterCategory>("all")
  const [sortBy, setSortBy] = useState<"newest" | "oldest" | "score" | "company">("newest")
  const [viewMode, setViewMode] = useState<"table" | "cards">("table")
  const [previewJob, setPreviewJob] = useState<Job | null>(null)
  const [copiedEmail, setCopiedEmail] = useState(false)

  // Statistiky
  const stats = useMemo(() => {
    const total = jobs.length
    const sent = jobs.filter((j) => j.status === "Sent").length
    const interview = jobs.filter((j) => j.status === "Interview").length
    const offer = jobs.filter((j) => j.status === "Offer").length
    const rejected = jobs.filter((j) => j.status === "Rejected").length
    
    const scores = jobs.filter((j) => typeof j.match_score === "number").map((j) => j.match_score as number)
    const avgScore = scores.length > 0 ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null

    return { total, sent, interview, offer, rejected, avgScore }
  }, [jobs])

  // Filtrování a řazení
  const filteredJobs = useMemo(() => {
    return jobs
      .filter((job) => {
        // Textové vyhledávání
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase()
          const matchesTitle = job.title?.toLowerCase().includes(q)
          const matchesCompany = job.company?.toLowerCase().includes(q)
          const matchesSubject = job.generated_subject?.toLowerCase().includes(q)
          const matchesReason = job.match_reason?.toLowerCase().includes(q)
          if (!matchesTitle && !matchesCompany && !matchesSubject && !matchesReason) {
            return false
          }
        }

        // Kategorie filtru
        if (filterCategory === "sent") {
          return job.status === "Sent"
        }
        if (filterCategory === "interview") {
          return job.status === "Interview"
        }
        if (filterCategory === "offer") {
          return job.status === "Offer"
        }
        if (filterCategory === "rejected") {
          return job.status === "Rejected"
        }
        if (filterCategory === "draft") {
          return ["Pending", "Scraping", "Generating", "Generated", "Completed", "Failed"].includes(job.status)
        }

        return true
      })
      .sort((a, b) => {
        if (sortBy === "score") {
          return (b.match_score || 0) - (a.match_score || 0)
        }
        if (sortBy === "company") {
          return (a.company || "").localeCompare(b.company || "")
        }
        if (sortBy === "oldest") {
          return parseInt(a.id, 10) - parseInt(b.id, 10)
        }
        // default newest
        return parseInt(b.id, 10) - parseInt(a.id, 10)
      })
  }, [jobs, searchQuery, filterCategory, sortBy])

  // Export do CSV
  const handleExportCSV = () => {
    if (jobs.length === 0) {
      alert("Není co exportovat, historie je prázdná.")
      return
    }

    const headers = [
      "ID",
      "Datum přidání",
      "Pozice",
      "Společnost",
      "Stav",
      "AI Shoda (%)",
      "AI Odůvodnění",
      "Předmět e-mailu",
      "Odkaz na inzerát",
    ]

    const escapeCsv = (val: any) => {
      if (val === null || val === undefined) return '""'
      const str = String(val).replace(/"/g, '""')
      return `"${str}"`
    }

    const rows = filteredJobs.map((j) => [
      escapeCsv(j.id),
      escapeCsv(j.dateAdded),
      escapeCsv(j.title),
      escapeCsv(j.company),
      escapeCsv(statusLabelMap[j.status] || j.status),
      escapeCsv(j.match_score !== undefined ? `${j.match_score}%` : ""),
      escapeCsv(j.match_reason || ""),
      escapeCsv(j.generated_subject || ""),
      escapeCsv(j.source_url || j.url || ""),
    ])

    const csvContent = "\uFEFF" + [headers.join(";"), ...rows.map((r) => r.join(";"))].join("\r\n")
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.setAttribute("href", url)
    link.setAttribute("download", `jobfinder_historie_${new Date().toISOString().slice(0, 10)}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const handleCopyEmail = (subject?: string, body?: string) => {
    if (!body) return
    const text = `${subject ? `Předmět: ${subject}\n\n` : ""}${body}`
    navigator.clipboard.writeText(text)
    setCopiedEmail(true)
    setTimeout(() => setCopiedEmail(false), 2000)
  }

  const renderScoreBadge = (score?: number) => {
    if (score === undefined || score === null) {
      return (
        <span className="text-xs text-muted-foreground italic px-2 py-0.5 rounded-full bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5">
          Nevyhodnoceno
        </span>
      )
    }

    let color = "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
    if (score < 50) {
      color = "bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30"
    } else if (score < 75) {
      color = "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30"
    }

    return (
      <span className={`inline-flex items-center gap-1 font-bold text-xs px-2.5 py-0.5 rounded-full border ${color}`}>
        <Sparkles className="w-3 h-3" />
        {score}%
      </span>
    )
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-transparent">
      {/* HEADER HISTORIE */}
      <div className="p-6 border-b border-white/20 dark:border-white/10 bg-white/40 dark:bg-black/40 backdrop-blur-xl shrink-0">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                <History className="w-4 h-4" />
              </div>
              <h1 className="text-2xl font-bold tracking-tight">Historie žádostí</h1>
              <Badge variant="outline" className="ml-2 font-mono text-xs">
                SQLite DB ({jobs.length})
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Kompletní audit a záznamy všech vašich pozic, vygenerovaných e-mailů a stavů odeslání.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportCSV}
              className="gap-2 rounded-xl border-white/30 dark:border-white/10 shadow-sm hover:bg-white/60 dark:hover:bg-white/10 text-xs font-medium cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              Exportovat do CSV
            </Button>
          </div>
        </div>

        {/* METRICS / STATS CARDS */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6">
          <div className="p-3.5 rounded-xl border border-white/20 dark:border-white/10 bg-white/50 dark:bg-black/30 backdrop-blur-md">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
              <span>Všechny pozice</span>
              <Briefcase className="w-3.5 h-3.5 opacity-60" />
            </div>
            <div className="text-2xl font-bold">{stats.total}</div>
          </div>

          <div className="p-3.5 rounded-xl border border-emerald-500/20 bg-emerald-500/5 backdrop-blur-md">
            <div className="flex items-center justify-between text-xs text-emerald-600 dark:text-emerald-400 mb-1">
              <span>Odesláno / Vyřízeno</span>
              <CheckCircle2 className="w-3.5 h-3.5" />
            </div>
            <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{stats.sent}</div>
          </div>

          <div className="p-3.5 rounded-xl border border-blue-500/20 bg-blue-500/5 backdrop-blur-md">
            <div className="flex items-center justify-between text-xs text-blue-600 dark:text-blue-400 mb-1">
              <span>Pohovory & Nabídky</span>
              <Award className="w-3.5 h-3.5" />
            </div>
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {stats.interview + stats.offer}
              {stats.offer > 0 && <span className="text-xs ml-1.5 font-normal text-emerald-500">({stats.offer} nabídka)</span>}
            </div>
          </div>

          <div className="p-3.5 rounded-xl border border-indigo-500/20 bg-indigo-500/5 backdrop-blur-md">
            <div className="flex items-center justify-between text-xs text-indigo-600 dark:text-indigo-400 mb-1">
              <span>Průměrná AI Shoda</span>
              <TrendingUp className="w-3.5 h-3.5" />
            </div>
            <div className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">
              {stats.avgScore !== null ? `${stats.avgScore}%` : "–"}
            </div>
          </div>
        </div>
      </div>

      {/* FILTER & SEARCH BAR */}
      <div className="p-4 border-b border-white/20 dark:border-white/10 bg-white/20 dark:bg-black/20 backdrop-blur-lg flex flex-col md:flex-row items-center justify-between gap-3 shrink-0">
        {/* Vyhledávací pole */}
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Hledat firmu, pozici, e-mail..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 h-9 rounded-xl bg-white/60 dark:bg-black/40 border-white/30 dark:border-white/10 text-xs"
          />
        </div>

        {/* Kategorie / Filtry */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto pb-1 md:pb-0 scrollbar-none">
          <button
            onClick={() => setFilterCategory("all")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 cursor-pointer ${
              filterCategory === "all"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:bg-black/5 dark:hover:bg-white/5 hover:text-foreground"
            }`}
          >
            Vše ({stats.total})
          </button>
          <button
            onClick={() => setFilterCategory("sent")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 cursor-pointer ${
              filterCategory === "sent"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:bg-black/5 dark:hover:bg-white/5 hover:text-foreground"
            }`}
          >
            Odesláno ({stats.sent})
          </button>
          <button
            onClick={() => setFilterCategory("interview")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 cursor-pointer ${
              filterCategory === "interview"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:bg-black/5 dark:hover:bg-white/5 hover:text-foreground"
            }`}
          >
            Pohovor ({stats.interview})
          </button>
          <button
            onClick={() => setFilterCategory("offer")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 cursor-pointer ${
              filterCategory === "offer"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:bg-black/5 dark:hover:bg-white/5 hover:text-foreground"
            }`}
          >
            Nabídka ({stats.offer})
          </button>
          <button
            onClick={() => setFilterCategory("rejected")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 cursor-pointer ${
              filterCategory === "rejected"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:bg-black/5 dark:hover:bg-white/5 hover:text-foreground"
            }`}
          >
            Zamítnuto ({stats.rejected})
          </button>
          <button
            onClick={() => setFilterCategory("draft")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 cursor-pointer ${
              filterCategory === "draft"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:bg-black/5 dark:hover:bg-white/5 hover:text-foreground"
            }`}
          >
            Koncepty
          </button>
        </div>

        {/* Řazení a přepínání zobrazení */}
        <div className="flex items-center gap-2 shrink-0">
          <select
            value={sortBy}
            onChange={(e: any) => setSortBy(e.target.value)}
            className="h-9 px-2.5 rounded-xl bg-white dark:bg-zinc-900 border border-black/10 dark:border-white/15 text-xs font-medium text-foreground focus:outline-none cursor-pointer shadow-sm"
          >
            <option value="newest" className="bg-white dark:bg-zinc-900 text-foreground">Nejnovější</option>
            <option value="oldest" className="bg-white dark:bg-zinc-900 text-foreground">Nejstarší</option>
            <option value="score" className="bg-white dark:bg-zinc-900 text-foreground">Nejvyšší AI shoda</option>
            <option value="company" className="bg-white dark:bg-zinc-900 text-foreground">Firma (A-Z)</option>
          </select>

          <div className="flex p-0.5 bg-black/5 dark:bg-white/10 rounded-lg">
            <button
              onClick={() => setViewMode("table")}
              title="Tabulkové zobrazení"
              className={`p-1.5 rounded-md transition-all ${
                viewMode === "table" ? "bg-white dark:bg-black/50 text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <LayoutList className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setViewMode("cards")}
              title="Karty"
              className={`p-1.5 rounded-md transition-all ${
                viewMode === "cards" ? "bg-white dark:bg-black/50 text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <LayoutGrid className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* HLAVNÍ OBSAH / SEZNAM ŽÁDOSTÍ */}
      <ScrollArea className="flex-1 p-6">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground gap-3">
            <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
            <p className="text-sm font-medium">Načítám historii ze SQLite databáze...</p>
          </div>
        ) : filteredJobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="w-12 h-12 rounded-2xl bg-black/5 dark:bg-white/5 flex items-center justify-center text-muted-foreground mb-4">
              <History className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold mb-1">Žádné záznamy nenalezeny</h3>
            <p className="text-xs text-muted-foreground max-w-sm">
              {searchQuery || filterCategory !== "all"
                ? "Pro zadaný filtr nebo vyhledávání nebyly nalezeny žádné žádosti."
                : "Zatím jste nepřidali žádné pracovní pozice. Přidejte první nabídku přes záložku Hledat."}
            </p>
          </div>
        ) : viewMode === "table" ? (
          /* TABULKOVÝ POHLED */
          <div className="rounded-2xl border border-white/20 dark:border-white/10 bg-white/40 dark:bg-black/40 backdrop-blur-xl overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-white/10 dark:border-white/5 bg-black/5 dark:bg-white/5 text-muted-foreground font-semibold">
                    <th className="py-3 px-4">Datum</th>
                    <th className="py-3 px-4">Pozice & Firma</th>
                    <th className="py-3 px-4">AI Shoda</th>
                    <th className="py-3 px-4">Stav žádosti</th>
                    <th className="py-3 px-4">Vygenerovaný e-mail</th>
                    <th className="py-3 px-4 text-right">Akce</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10 dark:divide-white/5">
                  {filteredJobs.map((job) => (
                    <tr
                      key={job.id}
                      className="hover:bg-black/5 dark:hover:bg-white/5 transition-colors group"
                    >
                      <td className="py-3.5 px-4 text-muted-foreground whitespace-nowrap font-mono text-[11px]">
                        <div className="flex items-center gap-1.5">
                          <Calendar className="w-3 h-3 opacity-60" />
                          <span>{job.dateAdded}</span>
                        </div>
                      </td>

                      <td className="py-3.5 px-4">
                        <div className="flex flex-col min-w-[200px]">
                          <span className="font-semibold text-sm text-foreground line-clamp-1 group-hover:text-primary transition-colors">
                            {job.title}
                          </span>
                          <div className="flex items-center gap-2 text-muted-foreground text-[11px] mt-0.5">
                            <span className="flex items-center gap-1">
                              <Building2 className="w-3 h-3" />
                              {job.company}
                            </span>
                            {job.source_url && (
                              <a
                                href={job.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                title="Otevřít původní inzerát"
                                className="hover:text-foreground inline-flex items-center gap-0.5 text-[10px] text-blue-500"
                              >
                                <ExternalLink className="w-2.5 h-2.5" />
                              </a>
                            )}
                          </div>
                        </div>
                      </td>

                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {renderScoreBadge(job.match_score)}
                      </td>

                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <select
                          value={job.status}
                          onChange={(e: any) => onStatusChange(job.id, e.target.value as JobStatus)}
                          className="h-7 px-2 text-[11px] font-semibold rounded-lg bg-white dark:bg-zinc-900 text-foreground border border-black/10 dark:border-white/15 hover:border-black/20 dark:hover:border-white/30 focus:outline-none cursor-pointer shadow-sm"
                        >
                          <option value="Pending" className="bg-white dark:bg-zinc-900 text-foreground">Čeká</option>
                          <option value="Scraping" className="bg-white dark:bg-zinc-900 text-foreground">Stahuji</option>
                          <option value="Generating" className="bg-white dark:bg-zinc-900 text-foreground">Analyzuji</option>
                          <option value="Generated" className="bg-white dark:bg-zinc-900 text-foreground">Připraveno</option>
                          <option value="Sending" className="bg-white dark:bg-zinc-900 text-foreground">Odesílám</option>
                          <option value="Sent" className="bg-white dark:bg-zinc-900 text-foreground">Odesláno</option>
                          <option value="Completed" className="bg-white dark:bg-zinc-900 text-foreground">Dokončeno</option>
                          <option value="Interview" className="bg-white dark:bg-zinc-900 text-foreground">Pohovor 🎯</option>
                          <option value="Offer" className="bg-white dark:bg-zinc-900 text-foreground">Nabídka 🎉</option>
                          <option value="Rejected" className="bg-white dark:bg-zinc-900 text-foreground">Zamítnuto ❌</option>
                          <option value="Failed" className="bg-white dark:bg-zinc-900 text-foreground">Chyba</option>
                        </select>
                      </td>

                      <td className="py-3.5 px-4 max-w-[220px]">
                        {job.generated_subject ? (
                          <div
                            onClick={() => setPreviewJob(job)}
                            className="cursor-pointer group/mail flex items-center gap-1.5 text-muted-foreground hover:text-foreground"
                          >
                            <Mail className="w-3.5 h-3.5 text-primary shrink-0" />
                            <span className="truncate text-[11px] underline decoration-dotted decoration-muted-foreground/50 underline-offset-2">
                              {job.generated_subject}
                            </span>
                          </div>
                        ) : (
                          <span className="text-muted-foreground/50 text-[11px] italic">Zatím nevygenerováno</span>
                        )}
                      </td>

                      <td className="py-3.5 px-4 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setPreviewJob(job)}
                            className="h-8 px-2 text-xs gap-1 hover:bg-black/10 dark:hover:bg-white/10 rounded-lg"
                            title="Zobrazit kompletní náhled"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            <span className="hidden sm:inline">Detail</span>
                          </Button>

                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onSelectJobForDetail(job.id)}
                            className="h-8 px-2 text-xs gap-1 hover:bg-black/10 dark:hover:bg-white/10 rounded-lg text-primary"
                            title="Otevřít v hlavním panelu a upravit"
                          >
                            <Layers className="w-3.5 h-3.5" />
                            <span className="hidden sm:inline">Otevřít</span>
                          </Button>

                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onDeleteJob(job.id)}
                            className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg"
                            title="Smazat žádost z databáze"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          /* KARTY POHLED */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredJobs.map((job) => (
              <div
                key={job.id}
                className="p-5 rounded-2xl border border-white/20 dark:border-white/10 bg-white/40 dark:bg-black/40 backdrop-blur-xl shadow-sm hover:shadow-md transition-all flex flex-col justify-between group"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <span className="text-[11px] text-muted-foreground font-mono flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {job.dateAdded}
                    </span>
                    {renderScoreBadge(job.match_score)}
                  </div>

                  <h3 className="font-bold text-base text-foreground mb-1 line-clamp-2 group-hover:text-primary transition-colors">
                    {job.title}
                  </h3>

                  <div className="flex items-center justify-between text-xs text-muted-foreground mb-4">
                    <span className="flex items-center gap-1 font-medium">
                      <Building2 className="w-3.5 h-3.5" />
                      {job.company}
                    </span>
                    {job.source_url && (
                      <a
                        href={job.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-500 hover:underline flex items-center gap-0.5 text-[11px]"
                      >
                        Inzerát <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    )}
                  </div>

                  {job.generated_subject && (
                    <div
                      onClick={() => setPreviewJob(job)}
                      className="p-2.5 rounded-xl bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5 mb-4 cursor-pointer hover:bg-black/10 dark:hover:bg-white/10 transition-colors"
                    >
                      <div className="flex items-center gap-1.5 text-xs font-medium text-foreground mb-1">
                        <Mail className="w-3 h-3 text-primary" />
                        <span className="truncate">{job.generated_subject}</span>
                      </div>
                      <p className="text-[11px] text-muted-foreground line-clamp-2">
                        {job.generated_body || "Klikněte pro zobrazení celého textu e-mailu..."}
                      </p>
                    </div>
                  )}
                </div>

                <div className="pt-3 border-t border-white/10 dark:border-white/5 flex items-center justify-between gap-2">
                  <Badge variant={statusBadgeVariant[job.status]}>
                    {statusLabelMap[job.status] || job.status}
                  </Badge>

                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setPreviewJob(job)}
                      className="h-8 px-2 text-xs gap-1 rounded-lg"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      Detail
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onSelectJobForDetail(job.id)}
                      className="h-8 px-2 text-xs gap-1 rounded-lg text-primary"
                    >
                      <Layers className="w-3.5 h-3.5" />
                      Otevřít
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </ScrollArea>

      {/* DETAIL PREVIEW DIALOG */}
      <Dialog open={!!previewJob} onOpenChange={(open) => !open && setPreviewJob(null)}>
        {previewJob && (
          <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col p-6 overflow-hidden">
            <DialogHeader className="shrink-0 pb-3 border-b border-border">
              <div className="flex items-start justify-between gap-4 pr-6">
                <div>
                  <DialogTitle className="text-xl font-bold leading-snug">
                    {previewJob.title}
                  </DialogTitle>
                  <DialogDescription className="flex items-center gap-2 mt-1">
                    <span className="font-semibold text-foreground">{previewJob.company}</span>
                    <span>•</span>
                    <span>{previewJob.dateAdded}</span>
                  </DialogDescription>
                </div>
                {renderScoreBadge(previewJob.match_score)}
              </div>
            </DialogHeader>

            <ScrollArea className="flex-1 pr-2 py-4">
              <div className="space-y-5">
                {/* AI ZDŮVODNĚNÍ SHODY */}
                {previewJob.match_reason && (
                  <div className="p-4 rounded-xl bg-blue-500/10 border border-blue-500/20 text-xs">
                    <div className="flex items-center gap-2 font-semibold text-blue-600 dark:text-blue-400 mb-1.5">
                      <Sparkles className="w-4 h-4" />
                      <span>AI Analýza shody s vaším životopisem</span>
                    </div>
                    <p className="text-foreground leading-relaxed">
                      {previewJob.match_reason}
                    </p>
                  </div>
                )}

                {/* VYGENEROVANÝ E-MAIL */}
                {previewJob.generated_body ? (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm font-semibold">
                        <Mail className="w-4 h-4 text-primary" />
                        <span>Připravený motivační e-mail</span>
                      </div>

                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleCopyEmail(previewJob.generated_subject, previewJob.generated_body)}
                        className="h-7 text-xs gap-1.5 rounded-lg cursor-pointer"
                      >
                        {copiedEmail ? (
                          <>
                            <Check className="w-3.5 h-3.5 text-emerald-500" />
                            <span className="text-emerald-500 font-medium">Zkopírováno!</span>
                          </>
                        ) : (
                          <>
                            <Copy className="w-3.5 h-3.5" />
                            <span>Kopírovat text</span>
                          </>
                        )}
                      </Button>
                    </div>

                    {previewJob.generated_subject && (
                      <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5 text-xs">
                        <span className="font-semibold text-muted-foreground mr-2">Předmět:</span>
                        <span className="font-medium text-foreground">{previewJob.generated_subject}</span>
                      </div>
                    )}

                    <div className="p-4 rounded-xl bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5 text-xs whitespace-pre-wrap leading-relaxed font-sans text-foreground">
                      {previewJob.generated_body}
                    </div>
                  </div>
                ) : (
                  <div className="p-4 rounded-xl bg-black/5 dark:bg-white/5 text-center text-xs text-muted-foreground">
                    E-mail pro tuto žádost zatím nebyl vygenerován.
                  </div>
                )}

                {/* POPIS POZICE / INZERÁT */}
                {previewJob.description && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      Původní text inzerátu
                    </h4>
                    <div className="p-4 rounded-xl bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5 text-xs whitespace-pre-wrap text-muted-foreground max-h-48 overflow-y-auto leading-relaxed">
                      {previewJob.description}
                    </div>
                  </div>
                )}
              </div>
            </ScrollArea>

            {/* PATIČKA MODÁLU */}
            <div className="shrink-0 pt-4 border-t border-border flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Změnit stav:</span>
                <select
                  value={previewJob.status}
                  onChange={(e: any) => {
                    const newStatus = e.target.value as JobStatus
                    onStatusChange(previewJob.id, newStatus)
                    setPreviewJob({ ...previewJob, status: newStatus })
                  }}
                  className="h-8 px-2.5 text-xs font-medium rounded-lg bg-white dark:bg-zinc-900 text-foreground border border-black/10 dark:border-white/20 focus:outline-none cursor-pointer shadow-sm"
                >
                  <option value="Pending" className="bg-white dark:bg-zinc-900 text-foreground">Čeká</option>
                  <option value="Generated" className="bg-white dark:bg-zinc-900 text-foreground">Připraveno</option>
                  <option value="Sent" className="bg-white dark:bg-zinc-900 text-foreground">Odesláno</option>
                  <option value="Completed" className="bg-white dark:bg-zinc-900 text-foreground">Dokončeno</option>
                  <option value="Interview" className="bg-white dark:bg-zinc-900 text-foreground">Pohovor 🎯</option>
                  <option value="Offer" className="bg-white dark:bg-zinc-900 text-foreground">Nabídka 🎉</option>
                  <option value="Rejected" className="bg-white dark:bg-zinc-900 text-foreground">Zamítnuto ❌</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                {previewJob.source_url && (
                  <Button
                    variant="outline"
                    size="sm"
                    asChild
                    className="h-8 text-xs gap-1.5 rounded-xl cursor-pointer"
                  >
                    <a href={previewJob.source_url} target="_blank" rel="noopener noreferrer">
                      <ExternalLink className="w-3.5 h-3.5" />
                      Přejít na inzerát
                    </a>
                  </Button>
                )}

                <Button
                  size="sm"
                  onClick={() => {
                    const id = previewJob.id
                    setPreviewJob(null)
                    onSelectJobForDetail(id)
                  }}
                  className="h-8 text-xs gap-1.5 rounded-xl bg-primary text-primary-foreground cursor-pointer"
                >
                  <Layers className="w-3.5 h-3.5" />
                  Otevřít v editoru
                </Button>
              </div>
            </div>
          </DialogContent>
        )}
      </Dialog>
    </div>
  )
}
