import { useState, useEffect } from "react"
import { Job, JobStatus } from "./JobCard"
import { ScrollArea } from "../ui/scroll-area"
import { Button } from "../ui/button"
import { Textarea } from "../ui/textarea"
import { Input } from "../ui/input"
import { 
  Send, 
  RefreshCw, 
  Briefcase, 
  ExternalLink, 
  Globe, 
  Sparkles, 
  Mail, 
  Paperclip, 
  CheckCircle2, 
  Loader2, 
  User, 
  AtSign,
  Check,
  AlertTriangle,
  Key,
  Settings,
  Copy,
  FileText,
  MessageSquare,
  Download
} from "lucide-react"
import { cn } from "../../lib/utils"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import axios from "axios"
import { useSettings } from "../../hooks/useSettings"

const API_BASE = "http://localhost:8000/api"

interface DetailPanelProps {
  job: (Job & { outreach_message?: string | null }) | null;
  onStatusChange: (jobId: string, newStatus: JobStatus) => void;
  onOpenSettings?: (tab?: string) => void;
}

function getPortalName(url?: string): string {
  if (!url) return "Inzerát"
  try {
    const host = new URL(url).hostname.replace("www.", "")
    if (host.includes("jobs.cz")) return "Jobs.cz"
    if (host.includes("startupjobs.cz")) return "StartupJobs.cz"
    if (host.includes("prace.cz")) return "Prace.cz"
    if (host.includes("profesia.cz")) return "Profesia.cz"
    if (host.includes("volnamista.cz")) return "Volnamista.cz"
    return host
  } catch {
    return "Původní inzerát"
  }
}

export function DetailPanel({ job, onStatusChange, onOpenSettings }: DetailPanelProps) {
  const queryClient = useQueryClient()
  const { data: settings } = useSettings()

  const [recipientEmail, setRecipientEmail] = useState("")
  const [emailSubject, setEmailSubject] = useState("")
  const [emailBody, setEmailBody] = useState("")
  const [copied, setCopied] = useState(false)

  type CopilotTab = "email" | "outreach" | "cv"
  const [copilotTab, setCopilotTab] = useState<CopilotTab>("email")
  const [outreachMessage, setOutreachMessage] = useState("")
  const [customFocus, setCustomFocus] = useState("")
  const [outreachCopied, setOutreachCopied] = useState(false)
  const [isDownloadingCv, setIsDownloadingCv] = useState(false)

  const hasCv = Boolean(settings?.cv_file_path)
  const hasProfile = Boolean(settings?.full_name || settings?.industry || settings?.education)
  const isOllama = settings?.llm_provider === "Ollama"
  const rawKey = settings?.llm_api_key?.trim() || ""
  const hasApiKey = isOllama ? true : Boolean(rawKey)
  const isMissingCv = !hasCv && !hasProfile
  const isMissingKey = !hasApiKey
  const hasValidConfig = !isMissingCv && !isMissingKey

  // Synchronizace lokálního stavu editoru při změně vybraného inzerátu nebo vygenerování textu
  useEffect(() => {
    if (job) {
      setEmailSubject(job.generated_subject || `Zájem o pozici: ${job.title}`)
      setEmailBody(job.generated_body || "")
      setOutreachMessage((job as any).outreach_message || "")
    }
  }, [job?.id, job?.generated_body, job?.generated_subject, (job as any)?.outreach_message])

  useEffect(() => {
    setRecipientEmail("")
  }, [job?.id])

  // Mutace pro samostatné vyhodnocení AI shody (Match score)
  const matchMutation = useMutation({
    mutationFn: async (jobId: string) => {
      const res = await axios.post(`${API_BASE}/applications/${jobId}/match`)
      return res.data
    },
    onSuccess: () => {
      // Okamžitě znovu načti data a pak po 2s znovu (aby se zachytil výsledek background tasku)
      queryClient.invalidateQueries({ queryKey: ["jobs"] })
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["jobs"] }), 2000)
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["jobs"] }), 5000)
    },
    onError: (err: any) => {
      alert("Chyba při vyhodnocování AI shody: " + (err.response?.data?.detail || err.message))
    }
  })

  // Mutace pro AI generování motivačního e-mailu na vyžádání
  const generateMutation = useMutation({
    mutationFn: async (jobId: string) => {
      const res = await axios.post(`${API_BASE}/applications/${jobId}/generate`)
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] })
    },
    onError: (err: any) => {
      alert("Chyba při generování e-mailu: " + (err.response?.data?.detail || err.message))
    }
  })

  // Mutace pro odeslání e-mailu přes SMTP
  const sendEmailMutation = useMutation({
    mutationFn: async ({ jobId, recipient, subject, body }: { jobId: string, recipient?: string, subject: string, body: string }) => {
      const res = await axios.post(`${API_BASE}/applications/${jobId}/send`, {
        recipient_email: recipient || undefined,
        subject: subject,
        body: body
      })
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] })
      if (job) {
        onStatusChange(job.id, "Sent")
      }
    },
    onError: (err: any) => {
      alert("Chyba při odesílání e-mailu přes SMTP: " + (err.response?.data?.detail || err.message))
    }
  })

  // Mutace pro AI generování cold outreach zprávy pro Hiring Managera
  const outreachMutation = useMutation({
    mutationFn: async ({ jobId, focus }: { jobId: string; focus?: string }) => {
      const res = await axios.post(`${API_BASE}/applications/${jobId}/outreach`, {
        custom_focus: focus?.trim() || undefined
      })
      return res.data
    },
    onSuccess: (data) => {
      if (data?.outreach_message) {
        setOutreachMessage(data.outreach_message)
      }
      queryClient.invalidateQueries({ queryKey: ["jobs"] })
    },
    onError: (err: any) => {
      alert("Chyba při generování cold outreach zprávy: " + (err.response?.data?.detail || err.message))
    }
  })

  // Stažení a vygenerování 1-stránkového ATS CV na míru (PDF)
  const handleDownloadTailoredCv = async () => {
    if (!job) return
    setIsDownloadingCv(true)
    try {
      // 1. Zavoláme vygenerování CV
      const genRes = await axios.post(`${API_BASE}/applications/${job.id}/cv/generate`, {}, {
        timeout: 45000
      })
      const defaultFilename = `CV_Jakub_Slavik_${job.company.replace(/[^a-zA-Z0-9]/g, '_')}.pdf`
      const filename = genRes.data?.filename || defaultFilename

      // 2. Stáhneme binární blob souboru
      const dlRes = await axios.get(`${API_BASE}/applications/${job.id}/cv/download`, {
        responseType: "blob",
        timeout: 45000
      })

      // 3. Automatické 1-kliknutí stažení v prohlížeči
      const blob = new Blob([dlRes.data], { type: "application/pdf" })
      const blobUrl = window.URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = blobUrl
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(blobUrl)

      // Invalidate queries pro aktualizaci tailored_cv_path
      queryClient.invalidateQueries({ queryKey: ["jobs"] })
    } catch (err: any) {
      console.error("Chyba při stahování ATS CV:", err)
      alert("Nepodařilo se vygenerovat či stáhnout ATS CV: " + (err.response?.data?.detail || err.message || "Neznámá chyba"))
    } finally {
      setIsDownloadingCv(false)
    }
  }

  if (!job) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground h-full">
        <div className="text-center">
          <Briefcase className="w-12 h-12 mx-auto mb-4 opacity-20" />
          <p>Vyberte pozici pro zobrazení detailů</p>
        </div>
      </div>
    )
  }

  const isMatching = matchMutation.isPending
  const isGenerating = job.status === "Generating" || generateMutation.isPending
  const isSending = job.status === "Sending" || sendEmailMutation.isPending
  const hasGeneratedEmail = Boolean(job.generated_body || emailBody)
  const isSent = job.status === "Sent"

  const outreachWords = outreachMessage.trim() ? outreachMessage.trim().split(/\s+/).length : 0
  const isWordCountInRange = outreachWords >= 100 && outreachWords <= 160
  const isOutreachGenerating = outreachMutation.isPending
  const hasGeneratedOutreach = Boolean((job as any)?.outreach_message || outreachMessage)

  const handleCopyOutreach = () => {
    if (!outreachMessage) return
    navigator.clipboard.writeText(outreachMessage)
    setOutreachCopied(true)
    setTimeout(() => setOutreachCopied(false), 2000)
  }

  const hasScore = typeof job.match_score === "number" && job.match_score !== null

  // Získání a ověření URL adresy zdroje inzerátu
  let sourceUrl = job.url || job.source_url || ""
  let descriptionText = job.description || ""

  if (!sourceUrl && descriptionText.includes("URL Source:")) {
    const match = descriptionText.match(/URL Source:\s*(\S+)/)
    if (match && match[1]) {
      sourceUrl = match[1]
    }
  }

  // Vyčištění případných metadatových hlaviček z Jina AI
  if (descriptionText.includes("Markdown Content:")) {
    descriptionText = descriptionText.split("Markdown Content:")[1].trim()
  } else if (descriptionText.includes("URL Source:")) {
    descriptionText = descriptionText
      .replace(/Title:[^\n]*\n?/g, "")
      .replace(/URL Source:[^\n]*\n?/g, "")
      .trim()
  }

  const portalName = getPortalName(sourceUrl)
  const cvFileName = settings?.cv_file_path ? settings.cv_file_path.split(/[/\\]/).pop() : "Životopis.pdf"

  const handleCopyBody = () => {
    navigator.clipboard.writeText(emailBody)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <ScrollArea className="flex-1 h-full">
      <div className="p-10 max-w-4xl mx-auto pb-12">
        {/* HLAVIČKA POZICE */}

          <div className="mb-10">
            <div className="flex justify-between items-start">
              <div>
                <h1 className="text-4xl font-bold tracking-tight mb-2">{job.title}</h1>
                <div className="flex flex-wrap items-center text-lg text-muted-foreground gap-2">
                  <span className="font-medium text-foreground">{job.company}</span>
                  <span>•</span>
                  <span>Praha (Remote)</span>
                  <span>•</span>
                  <span className="text-sm px-2 py-1 bg-black/5 dark:bg-white/10 rounded-md">Plný úvazek</span>
                  {sourceUrl && (
                    <>
                      <span>•</span>
                      <a
                        href={sourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs px-2.5 py-1 bg-primary/10 hover:bg-primary/20 text-primary font-medium rounded-md transition-colors"
                        title={sourceUrl}
                      >
                        <Globe className="w-3.5 h-3.5" />
                        <span>{portalName}</span>
                        <ExternalLink className="w-3 h-3 ml-0.5 opacity-70" />
                      </a>
                    </>
                  )}
                </div>
              </div>
              
              {/* Výběr stavu žádosti */}
              <select 
                className="bg-white dark:bg-zinc-900 text-foreground border border-black/10 dark:border-white/20 p-2 rounded-lg text-sm outline-none font-medium shadow-sm cursor-pointer"
                value={job.status}
                onChange={(e) => onStatusChange(job.id, e.target.value as JobStatus)}
              >
                <option value="Pending" className="bg-white dark:bg-zinc-900 text-foreground">Čeká</option>
                <option value="Scraping" className="bg-white dark:bg-zinc-900 text-foreground">Stahuji data</option>
                <option value="Generating" className="bg-white dark:bg-zinc-900 text-foreground">Analyzuji</option>
                <option value="Generated" className="bg-white dark:bg-zinc-900 text-foreground">Připraveno</option>
                <option value="Sending" className="bg-white dark:bg-zinc-900 text-foreground">Odesílám</option>
                <option value="Sent" className="bg-white dark:bg-zinc-900 text-foreground">Posláno</option>
                <option value="Completed" className="bg-white dark:bg-zinc-900 text-foreground">Dokončeno</option>
                <option value="Failed" className="bg-white dark:bg-zinc-900 text-foreground">Selhalo</option>
                <option value="Interview" className="bg-white dark:bg-zinc-900 text-foreground">Pohovor</option>
                <option value="Rejected" className="bg-white dark:bg-zinc-900 text-foreground">Zamítnuto</option>
                <option value="Offer" className="bg-white dark:bg-zinc-900 text-foreground">Nabídka</option>
              </select>
            </div>
            
            {/* UPOZORNĚNÍ: Chybí životopis / profil */}
            {isMissingCv && (
              <div className="mt-4 p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200 text-sm flex items-start justify-between gap-4 shadow-sm">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-semibold text-amber-950 dark:text-amber-100">Chybí životopis nebo profil</h4>
                    <p className="text-xs text-amber-800/90 dark:text-amber-300/90 mt-0.5">
                      Systém o vás zatím nemá žádné informace. Nahrajte svůj životopis (PDF) nebo vyplňte profil, aby AI mohla vyhodnotit shodu s touto pozicí a vytvořit personalizovaný dopis.
                    </p>
                  </div>
                </div>
                {onOpenSettings && (
                  <Button 
                    size="sm" 
                    variant="outline" 
                    onClick={() => onOpenSettings("profile")}
                    className="shrink-0 border-amber-500/40 text-amber-900 dark:text-amber-200 hover:bg-amber-500/20 text-xs font-semibold gap-1.5"
                  >
                    <User className="w-3.5 h-3.5" />
                    Doplnit profil / CV
                  </Button>
                )}
              </div>
            )}

            {/* UPOZORNĚNÍ: Chybí nebo je neplatný API klíč */}
            {isMissingKey && (
              <div className="mt-3 p-4 rounded-xl border border-red-500/30 bg-red-500/10 text-red-900 dark:text-red-200 text-sm flex items-start justify-between gap-4 shadow-sm">
                <div className="flex items-start gap-3">
                  <Key className="w-5 h-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-semibold text-red-950 dark:text-red-100">
                      Chybí API klíč{settings?.llm_provider ? ` pro ${settings.llm_provider}` : " pro AI"}
                    </h4>
                    <p className="text-xs text-red-800/90 dark:text-red-300/90 mt-0.5">
                      Pro spuštění AI hodnocení a generování e-mailů je potřeba nastavit platný API klíč{settings?.llm_provider ? ` pro ${settings.llm_provider}` : ""} v Nastavení → AI a Chování.
                    </p>
                  </div>
                </div>
                {onOpenSettings && (
                  <Button 
                    size="sm" 
                    variant="outline" 
                    onClick={() => onOpenSettings("ai")}
                    className="shrink-0 border-red-500/40 text-red-900 dark:text-red-200 hover:bg-red-500/20 text-xs font-semibold gap-1.5"
                  >
                    <Settings className="w-3.5 h-3.5" />
                    Nastavit API klíč
                  </Button>
                )}
              </div>
            )}

            {/* AI Hodnocení (Match Score) */}
            {hasScore ? (
              <div className="mt-6 p-5 rounded-2xl border border-white/20 bg-white/60 dark:bg-black/30 backdrop-blur-md shadow-sm space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      "flex items-center justify-center w-14 h-14 rounded-2xl font-black text-2xl border shadow-inner",
                      job.match_score! >= 80 
                        ? "bg-green-500/15 border-green-500/30 text-green-600 dark:text-green-400"
                        : job.match_score! >= 50
                        ? "bg-amber-500/15 border-amber-500/30 text-amber-600 dark:text-amber-400"
                        : "bg-red-500/15 border-red-500/30 text-red-600 dark:text-red-400"
                    )}>
                      {job.match_score}%
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-bold text-sm text-foreground">AI Hodnocení shody s vaším profilem</h4>
                        <span className={cn(
                          "text-[11px] px-2 py-0.5 rounded-full font-semibold border",
                          job.match_score! >= 80 
                            ? "bg-green-500/10 border-green-500/20 text-green-700 dark:text-green-300"
                            : job.match_score! >= 50
                            ? "bg-amber-500/10 border-amber-500/20 text-amber-700 dark:text-amber-300"
                            : "bg-red-500/10 border-red-500/20 text-red-700 dark:text-red-300"
                        )}>
                          {job.match_score! >= 80 ? "Vynikající shoda" : job.match_score! >= 50 ? "Dobrá shoda" : "Nízká shoda"}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Kriticky porovnáno s vaším nahraným životopisem a zkušenostmi
                      </p>
                    </div>
                  </div>

                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={isMatching}
                    onClick={() => matchMutation.mutate(job.id)}
                    className="h-8 gap-1.5 text-xs text-muted-foreground hover:text-primary"
                  >
                    {isMatching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                    {isMatching ? "Počítám..." : "Přepočítat shodu"}
                  </Button>
                </div>

                {job.match_reason && (
                  <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5 text-sm text-foreground leading-relaxed">
                    <p className="font-semibold text-xs text-muted-foreground uppercase tracking-wider mb-1">
                      Zdůvodnění AI:
                    </p>
                    {job.match_reason}
                  </div>
                )}

                {/* Detailní rozpad: PROs, CONs, Chybějící technologie */}
                {(job.pros?.length || job.cons?.length || job.missing_skills?.length || job.part_time_viability) ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3 pt-3 border-t border-border/40">
                    {job.pros && job.pros.length > 0 && (
                      <div className="p-3 rounded-xl bg-green-500/5 border border-green-500/15 space-y-1.5">
                        <div className="text-xs font-bold text-green-700 dark:text-green-400 flex items-center gap-1.5">
                          <span>✅</span> Silné stránky
                        </div>
                        <ul className="text-xs space-y-1 text-foreground/90 list-disc list-inside">
                          {job.pros.map((p, idx) => (
                            <li key={idx} className="leading-snug">{p}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {job.cons && job.cons.length > 0 && (
                      <div className="p-3 rounded-xl bg-red-500/5 border border-red-500/15 space-y-1.5">
                        <div className="text-xs font-bold text-red-700 dark:text-red-400 flex items-center gap-1.5">
                          <span>⚠️</span> Rizika / Mezery
                        </div>
                        <ul className="text-xs space-y-1 text-foreground/90 list-disc list-inside">
                          {job.cons.map((c, idx) => (
                            <li key={idx} className="leading-snug">{c}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {job.missing_skills && job.missing_skills.length > 0 && (
                      <div className="sm:col-span-2 p-3 rounded-xl bg-amber-500/5 border border-amber-500/15 space-y-1.5">
                        <div className="text-xs font-bold text-amber-700 dark:text-amber-400">
                          Chybějící technologie a požadavky:
                        </div>
                        <div className="flex flex-wrap gap-1.5 pt-0.5">
                          {job.missing_skills.map((s, idx) => (
                            <span key={idx} className="px-2 py-0.5 text-[11px] rounded-md bg-amber-500/10 text-amber-800 dark:text-amber-300 font-medium">
                              {s}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {job.part_time_viability && (
                      <div className="sm:col-span-2 p-2.5 rounded-lg bg-black/5 dark:bg-white/5 text-xs text-muted-foreground">
                        <strong className="text-foreground">Posouzení Part-time / Kontraktu:</strong> {job.part_time_viability}
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            ) : (
              /* Informační box, pokud shoda ještě nebyla spočítána */
              <div className="mt-6 p-5 rounded-2xl border border-dashed border-primary/25 bg-primary/5 flex items-center justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0 mt-0.5">
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="font-bold text-sm text-foreground">AI Hodnocení shody zatím nebylo provedeno</h4>
                    <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
                      {hasValidConfig 
                        ? "Kliknutím na tlačítko můžete okamžitě spustit samostatnou AI analýzu této pozice a zjistit přesné procento shody."
                        : isMissingKey
                        ? "Pro výpočet AI shody musíte nejprve nastavit platný API klíč v Nastavení."
                        : "Pro výpočet AI shody je nutné nahrát životopis nebo vyplnit profil v Nastavení."}
                    </p>
                  </div>
                </div>

                {hasValidConfig ? (
                  <Button
                    size="sm"
                    disabled={isMatching}
                    onClick={() => matchMutation.mutate(job.id)}
                    className="shrink-0 gap-1.5 rounded-xl font-semibold shadow-sm"
                  >
                    {isMatching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                    {isMatching ? "Počítám shodu..." : "Spočítat AI shodu"}
                  </Button>
                ) : (
                  onOpenSettings && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onOpenSettings(isMissingCv ? "profile" : "ai")}
                      className="shrink-0 text-xs font-semibold rounded-xl"
                    >
                      {isMissingCv ? "Nahrát CV" : "Nastavit klíč"}
                    </Button>
                  )
                )}
              </div>
            )}

            {/* Chybová hláška (zobrazí se vždy když je error_logs přítomný, nejen u Failed) */}
            {job.error_logs && (
              <div className="mt-6 p-4 rounded-xl border border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300 text-sm flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-red-600 dark:text-red-400 shrink-0" />
                    <span className="font-semibold">Chyba při zpracování AI:</span>
                  </div>
                  {onOpenSettings && (
                    <Button 
                      size="sm" 
                      variant="outline" 
                      onClick={() => onOpenSettings("ai")}
                      className="h-7 text-xs border-red-400 text-red-700 dark:text-red-300 hover:bg-red-500/20"
                    >
                      Přejít do Nastavení
                    </Button>
                  )}
                </div>
                <p className="whitespace-pre-wrap font-sans text-xs leading-relaxed opacity-90">{job.error_logs}</p>
              </div>
            )}
          </div>

          <div className="space-y-12">
            {/* SEKCE 1: POPIS POZICE */}
            <section>
              <div className="flex items-center justify-between mb-4 border-b border-black/5 dark:border-white/5 pb-2">
                <h3 className="text-xl font-semibold">Popis pozice</h3>
                {sourceUrl && (
                  <a
                    href={sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline hover:text-primary/80 bg-primary/10 hover:bg-primary/20 px-3 py-1.5 rounded-lg transition-colors"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>Přejít na původní inzerát</span>
                  </a>
                )}
              </div>

              {/* URL ZDROJ INZERÁTU NAD POPISEM */}
              {sourceUrl && (
                <div className="mb-5 p-3.5 rounded-xl border border-white/20 bg-white/50 dark:bg-black/30 flex items-center justify-between gap-3 text-xs shadow-sm">
                  <div className="flex items-center gap-2.5 min-w-0 flex-1">
                    <Globe className="w-4 h-4 text-primary shrink-0" />
                    <span className="font-semibold text-foreground shrink-0">Zdroj inzerátu:</span>
                    <a
                      href={sourceUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline truncate font-mono text-xs select-all"
                      title={sourceUrl}
                    >
                      {sourceUrl}
                    </a>
                  </div>
                  <a
                    href={sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:text-primary/80 shrink-0 font-medium px-2.5 py-1 rounded hover:bg-primary/10 transition-colors"
                  >
                    <span>Otevřít</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              )}

              <div className="prose dark:prose-invert max-w-none text-muted-foreground leading-relaxed whitespace-pre-wrap text-sm bg-white/30 dark:bg-black/20 p-5 rounded-2xl border border-white/10">
                {descriptionText ? descriptionText : "Popis pozice zatím nebyl načten nebo je prázdný."}
              </div>
            </section>
            
            {/* SEKCE 2: KARIÉRNÍ COPILOT S 3 ZÁLOŽKAMI */}
            <section className="pt-4">
              {/* LIŠTA ZÁLOŽEK COPILOTU */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 border-b border-black/10 dark:border-white/10 pb-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-primary" />
                  <h3 className="text-xl font-semibold">Kariérní Copilot</h3>
                </div>

                <div className="flex items-center gap-1.5 p-1 bg-black/5 dark:bg-white/5 rounded-xl border border-black/5 dark:border-white/5">
                  <button
                    type="button"
                    onClick={() => setCopilotTab("email")}
                    className={cn(
                      "flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer",
                      copilotTab === "email"
                        ? "bg-white dark:bg-zinc-800 text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <Mail className="w-3.5 h-3.5" />
                    <span>E-mail na HR</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setCopilotTab("outreach")}
                    className={cn(
                      "flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer",
                      copilotTab === "outreach"
                        ? "bg-white dark:bg-zinc-800 text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <MessageSquare className="w-3.5 h-3.5 text-primary" />
                    <span>Cold Outreach</span>
                    {Boolean((job as any)?.outreach_message || outreachMessage) && (
                      <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={() => setCopilotTab("cv")}
                    className={cn(
                      "flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer",
                      copilotTab === "cv"
                        ? "bg-white dark:bg-zinc-800 text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <FileText className="w-3.5 h-3.5 text-amber-500" />
                    <span>ATS CV na míru</span>
                    {Boolean((job as any)?.tailored_cv_path) && (
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                    )}
                  </button>
                </div>
              </div>

              {/* OBSAH ZÁLOŽKY 1: E-MAIL NA HR */}
              {copilotTab === "email" && (
                <div>
                  <div className="flex items-center justify-between mb-6 border-b border-black/5 dark:border-white/5 pb-2">
                    <div className="flex items-center gap-2">
                      <Mail className="w-5 h-5 text-primary" />
                      <h3 className="text-xl font-semibold">Motivační e-mail a odeslání</h3>
                    </div>
                    
                    {hasGeneratedEmail && (
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        disabled={isGenerating || isSending}
                        onClick={() => generateMutation.mutate(job.id)}
                        className="h-8 gap-1.5 text-primary hover:text-primary hover:bg-primary/10"
                      >
                        {isGenerating ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Sparkles className="w-3.5 h-3.5" />
                        )}
                        Přegenerovat s AI
                      </Button>
                    )}
                  </div>

                  {/* STAV 1: Probíhá generování AI */}
                  {isGenerating ? (
                    <div className="p-8 rounded-2xl border border-primary/30 bg-primary/5 dark:bg-primary/10 flex flex-col items-center justify-center text-center gap-4 py-16 animate-pulse">
                      <div className="w-14 h-14 rounded-2xl bg-primary/20 flex items-center justify-center text-primary shadow-inner">
                        <Loader2 className="w-7 h-7 animate-spin" />
                      </div>
                      <div>
                        <h4 className="font-bold text-lg">AI analyzuje pozici a váš životopis...</h4>
                        <p className="text-sm text-muted-foreground mt-1 max-w-md">
                          Porovnáváme klíčová slova, vytváříme personalizované argumenty a sestavujeme profesionální e-mail.
                        </p>
                      </div>
                    </div>
                  ) : !hasGeneratedEmail ? (
                    /* STAV 2: E-mail ještě nebyl vygenerován -> Tlačítko pro spuštění AI generování */
                    <div className="p-8 rounded-2xl border border-white/20 bg-white/40 dark:bg-black/30 flex flex-col items-center justify-center text-center gap-5 py-12 shadow-sm backdrop-blur-xl">
                      <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center text-primary shadow-sm">
                        <Sparkles className="w-7 h-7" />
                      </div>
                      <div className="max-w-md">
                        <h4 className="font-bold text-xl mb-1">Generování motivačního e-mailu pomocí AI</h4>
                        <p className="text-sm text-muted-foreground leading-relaxed">
                          AI prostuduje požadavky tohoto inzerátu, porovná je s vaším životopisem, spočítá shodu a vytvoří personalizovaný text e-mailu.
                        </p>
                      </div>

                      {!hasValidConfig ? (
                        <div className="w-full max-w-md p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-left space-y-3 text-xs">
                          <div className="flex items-center gap-2 font-semibold text-amber-900 dark:text-amber-200">
                            <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                            <span>Před generováním je nutné doplnit údaje v Nastavení:</span>
                          </div>
                          <div className="space-y-2">
                            {isMissingCv && (
                              <div className="flex items-center justify-between bg-white/50 dark:bg-black/40 p-2 rounded-lg">
                                <span className="text-muted-foreground">📄 Životopis (CV v PDF)</span>
                                {onOpenSettings && (
                                  <Button 
                                    size="sm" 
                                    variant="outline" 
                                    onClick={() => onOpenSettings("profile")} 
                                    className="h-6 text-[11px] px-2 font-semibold text-primary"
                                  >
                                    Nahrát CV
                                  </Button>
                                )}
                              </div>
                            )}
                            {isMissingKey && (
                              <div className="flex items-center justify-between bg-white/50 dark:bg-black/40 p-2 rounded-lg">
                                <span className="text-muted-foreground">🔑 Platný AI API klíč ({settings?.llm_provider || "AI"})</span>
                                {onOpenSettings && (
                                  <Button 
                                    size="sm" 
                                    variant="outline" 
                                    onClick={() => onOpenSettings("ai")} 
                                    className="h-6 text-[11px] px-2 font-semibold text-primary"
                                  >
                                    Nastavit klíč
                                  </Button>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      ) : null}

                      <Button 
                        size="lg"
                        onClick={() => {
                          if (!hasValidConfig && onOpenSettings) {
                            onOpenSettings(isMissingCv ? "profile" : "ai")
                            return
                          }
                          generateMutation.mutate(job.id)
                        }}
                        className="gap-2 px-8 h-12 text-base font-semibold shadow-lg hover:shadow-primary/25 hover:scale-[1.02] transition-all bg-primary text-primary-foreground"
                      >
                        <Sparkles className="w-5 h-5" />
                        {hasValidConfig ? "Vygenerovat e-mail pomocí AI" : "Doplnit nastavení pro AI"}
                      </Button>
                    </div>
                  ) : (
                    /* STAV 3: E-mail je vygenerován -> Zobrazení kompletní SMTP struktury a editoru */
                    <div className="space-y-6">
                      {/* SMTP STRUKTURA HLAVIČKY */}
                      <div className="p-5 rounded-2xl border border-white/20 bg-white/60 dark:bg-black/40 backdrop-blur-xl shadow-sm space-y-4">
                        <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
                          <AtSign className="w-3.5 h-3.5" />
                          <span>SMTP Parametry zprávy</span>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {/* ODESÍLATEL (FROM) */}
                          <div className="space-y-1.5">
                            <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
                              <User className="w-3.5 h-3.5 text-primary" />
                              <span>Od (Váš SMTP účet):</span>
                            </label>
                            <div className="flex items-center justify-between p-2.5 rounded-xl bg-white/50 dark:bg-black/30 border border-white/10 text-sm">
                              <span className="font-medium truncate text-foreground">{settings?.smtp_email || "Nenastaveno v nastavení"}</span>
                              <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-green-500/10 text-green-600 dark:text-green-400 font-medium shrink-0">
                                <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
                                SMTP Aktivní
                              </span>
                            </div>
                          </div>

                          {/* PŘÍJEMCE (TO / HR) */}
                          <div className="space-y-1.5">
                            <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
                              <Mail className="w-3.5 h-3.5 text-primary" />
                              <span>Komu (E-mail na HR / Firmu):</span>
                            </label>
                            <Input 
                              placeholder={`napr. kariera@${job.company.toLowerCase().replace(/[^a-z0-9]/g, '') || "firma"}.cz`}
                              value={recipientEmail}
                              onChange={(e) => setRecipientEmail(e.target.value)}
                              className="bg-white/50 dark:bg-black/30 border-white/10 text-sm h-10"
                            />
                          </div>
                        </div>

                        {/* PŘÍLOHA CV */}
                        <div className="pt-2 border-t border-black/5 dark:border-white/5 flex flex-wrap items-center justify-between gap-2 text-xs">
                          <div className="flex items-center gap-2 text-muted-foreground">
                            <Paperclip className="w-3.5 h-3.5 text-primary" />
                            <span className="font-medium text-foreground">Přiložený životopis:</span>
                            <span className="px-2.5 py-1 rounded-lg bg-black/5 dark:bg-white/10 font-mono text-foreground font-semibold">
                              📄 {cvFileName}
                            </span>
                          </div>
                          <span className="text-muted-foreground italic text-[11px]">
                            (Automaticky se odešle jako PDF příloha přes SMTP)
                          </span>
                        </div>
                      </div>

                      {/* PŘEDMĚT E-MAILU */}
                      <div className="space-y-2">
                        <label className="text-sm font-semibold flex items-center justify-between">
                          <span>Předmět e-mailu</span>
                          <span className="text-xs text-muted-foreground font-normal">Předmět zprávy</span>
                        </label>
                        <Input 
                          value={emailSubject}
                          onChange={(e) => setEmailSubject(e.target.value)}
                          className="bg-white/50 dark:bg-black/30 text-base py-3 h-auto border-white/20 font-medium" 
                        />
                      </div>

                      {/* TĚLO E-MAILU */}
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <label className="text-sm font-semibold">Tělo e-mailu (Upravte dle potřeby)</label>
                          <button
                            type="button"
                            onClick={handleCopyBody}
                            className="text-xs text-primary hover:underline inline-flex items-center gap-1 font-medium"
                          >
                            {copied ? <Check className="w-3 h-3 text-green-500" /> : null}
                            {copied ? "Zkopírováno!" : "Kopírovat text"}
                          </button>
                        </div>
                        <Textarea 
                          value={emailBody} 
                          onChange={(e) => setEmailBody(e.target.value)}
                          className="bg-white/50 dark:bg-black/30 min-h-[320px] text-base leading-relaxed border-white/20 p-4 font-sans" 
                        />
                      </div>

                      {/* STAV ODESLÁNÍ */}
                      {isSent && (
                        <div className="p-4 rounded-xl bg-green-500/10 border border-green-500/30 text-green-700 dark:text-green-300 flex items-center gap-3 text-sm">
                          <CheckCircle2 className="w-5 h-5 shrink-0" />
                          <span>E-mail pro tuto pozici byl úspěšně odeslán přes SMTP server.</span>
                        </div>
                      )}

                      {/* AKČNÍ PANEL POD TEXTEM */}
                      <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
                        <Button 
                          variant="outline"
                          disabled={isGenerating || isSending}
                          onClick={() => generateMutation.mutate(job.id)}
                          className="gap-2 bg-white/40 dark:bg-black/30 border-white/20"
                        >
                          <RefreshCw className={cn("w-4 h-4", isGenerating && "animate-spin")} />
                          Znovu vygenerovat s AI
                        </Button>

                        <Button 
                          size="lg"
                          disabled={isSending || isGenerating}
                          onClick={() => {
                            const targetEmail = recipientEmail.trim()
                            if (!targetEmail || !targetEmail.includes("@")) {
                              alert("Zadejte prosím platnou e-mailovou adresu firmy / HR v poli 'Komu' před odesláním.")
                              return
                            }
                            sendEmailMutation.mutate({
                              jobId: job.id,
                              recipient: targetEmail,
                              subject: emailSubject,
                              body: emailBody
                            })
                          }}
                          className="gap-2 px-8 bg-primary text-primary-foreground font-semibold shadow-lg hover:shadow-primary/25 hover:scale-[1.02] transition-all"
                        >
                          {isSending ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Send className="w-4 h-4" />
                          )}
                          {isSending ? "Odesílám přes SMTP..." : isSent ? "Odeslat znovu přes SMTP" : "Poslat e-mail přes SMTP"}
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* OBSAH ZÁLOŽKY 2: COLD OUTREACH PRO HIRING MANAGERA */}
              {copilotTab === "outreach" && (
                <div className="space-y-6">
                  {/* POPIS A VOLITELNÝ CUSTOM FOCUS */}
                  <div className="p-5 rounded-2xl border border-white/20 bg-white/60 dark:bg-black/40 backdrop-blur-xl shadow-sm space-y-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div>
                        <h4 className="font-semibold text-base flex items-center gap-2">
                          <MessageSquare className="w-4 h-4 text-primary" />
                          <span>Zpráva pro Hiring Managera / Tech Leada</span>
                        </h4>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Stručná, úderná zpráva (100–160 slov) pro LinkedIn InMail nebo přímý e-mail. Propojuje výzvy inzerátu s vašimi technologickými úspěchy.
                        </p>
                      </div>

                      {hasGeneratedOutreach && (
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={isOutreachGenerating}
                          onClick={() => outreachMutation.mutate({ jobId: job.id, focus: customFocus })}
                          className="h-8 gap-1.5 text-primary hover:text-primary hover:bg-primary/10 shrink-0 cursor-pointer"
                        >
                          {isOutreachGenerating ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <RefreshCw className="w-3.5 h-3.5" />
                          )}
                          Přegenerovat s AI
                        </Button>
                      )}
                    </div>

                    {/* Vstup pro volitelný custom focus */}
                    <div className="pt-2 border-t border-black/5 dark:border-white/5 space-y-1.5">
                      <label className="text-xs font-semibold text-muted-foreground flex items-center justify-between">
                        <span>Klíčové zaměření / úhel zprávy (volitelné):</span>
                        <span className="text-[11px] text-muted-foreground font-normal">např. latence, distribuované systémy, FastAPI</span>
                      </label>
                      <Input
                        placeholder="např. Optimalizace propustnosti pipeline, asynchronní zpracování, PostgreSQL výkon"
                        value={customFocus}
                        onChange={(e) => setCustomFocus(e.target.value)}
                        className="bg-white/50 dark:bg-black/30 border-white/10 text-sm h-9"
                        disabled={isOutreachGenerating}
                      />
                    </div>
                  </div>

                  {/* STAV 1: Probíhá generování cold outreach */}
                  {isOutreachGenerating ? (
                    <div className="p-8 rounded-2xl border border-primary/30 bg-primary/5 dark:bg-primary/10 flex flex-col items-center justify-center text-center gap-4 py-16 animate-pulse">
                      <div className="w-14 h-14 rounded-2xl bg-primary/20 flex items-center justify-center text-primary shadow-inner">
                        <Loader2 className="w-7 h-7 animate-spin" />
                      </div>
                      <div>
                        <h4 className="font-bold text-lg">AI sestavuje cold outreach zprávu...</h4>
                        <p className="text-sm text-muted-foreground mt-1 max-w-md">
                          Propojujeme technologické výzvy inzerátu s vašimi úspěchy v životopisu s důrazem na rozsah 100–160 slov.
                        </p>
                      </div>
                    </div>
                  ) : !hasGeneratedOutreach ? (
                    /* STAV 2: Zatím nevygenerováno */
                    <div className="p-8 rounded-2xl border border-white/20 bg-white/40 dark:bg-black/30 flex flex-col items-center justify-center text-center gap-5 py-12 shadow-sm backdrop-blur-xl">
                      <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center text-primary shadow-sm">
                        <Sparkles className="w-7 h-7" />
                      </div>
                      <div className="max-w-md">
                        <h4 className="font-bold text-xl mb-1">Cílený Cold Outreach na Hiring Managera</h4>
                        <p className="text-sm text-muted-foreground leading-relaxed">
                          AI vytvoří vysoce personalizovanou zprávu (100–160 slov) přímo pro vedoucího vývoje nebo hiring manažera. Zpráva vyzdvihne přesně ty technologie, které firma v inzerátu poptává.
                        </p>
                      </div>

                      <Button
                        size="lg"
                        disabled={isOutreachGenerating}
                        onClick={() => outreachMutation.mutate({ jobId: job.id, focus: customFocus })}
                        className="gap-2 px-8 h-12 text-base font-semibold shadow-lg hover:shadow-primary/25 hover:scale-[1.02] transition-all bg-primary text-primary-foreground cursor-pointer"
                      >
                        <Sparkles className="w-5 h-5" />
                        Vygenerovat zprávu pro Hiring Managera
                      </Button>
                    </div>
                  ) : (
                    /* STAV 3: Vygenerováno -> Textarea, Word Count indikátor a One-click Copy */
                    <div className="space-y-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex items-center gap-2.5">
                          <label className="text-sm font-semibold">Text zprávy (upravte dle potřeby):</label>
                          {/* Live word count indicator */}
                          {isWordCountInRange ? (
                            <span className="inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full bg-green-500/10 text-green-600 dark:text-green-400 font-semibold border border-green-500/20">
                              <Check className="w-3 h-3" />
                              {outreachWords} slov (Ideální: 100–160)
                            </span>
                          ) : outreachWords < 100 ? (
                            <span className="inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 font-medium border border-amber-500/20">
                              <AlertTriangle className="w-3 h-3" />
                              {outreachWords} slov (Cíl: 100–160, chybí {100 - outreachWords})
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full bg-red-500/10 text-red-600 dark:text-red-400 font-medium border border-red-500/20">
                              <AlertTriangle className="w-3 h-3" />
                              {outreachWords} slov (Cíl: 100–160, přebývá {outreachWords - 160})
                            </span>
                          )}
                        </div>

                        {/* One-click copy button with feedback */}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleCopyOutreach}
                          className="gap-1.5 h-8 bg-white/60 dark:bg-black/40 border-white/20 hover:bg-primary/10 hover:text-primary transition-colors font-medium text-xs cursor-pointer"
                        >
                          {outreachCopied ? (
                            <>
                              <Check className="w-3.5 h-3.5 text-green-500" />
                              <span className="text-green-600 dark:text-green-400 font-semibold">Zkopírováno!</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3.5 h-3.5" />
                              <span>Zkopírovat do schránky</span>
                            </>
                          )}
                        </Button>
                      </div>

                      <Textarea
                        value={outreachMessage}
                        onChange={(e) => setOutreachMessage(e.target.value)}
                        className="bg-white/50 dark:bg-black/30 min-h-[280px] text-base leading-relaxed border-white/20 p-4 font-sans focus:border-primary/50"
                        placeholder="Zde se zobrazí vygenerovaná cold outreach zpráva..."
                      />

                      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={isOutreachGenerating}
                          onClick={() => outreachMutation.mutate({ jobId: job.id, focus: customFocus })}
                          className="gap-2 bg-white/40 dark:bg-black/30 border-white/20 text-xs cursor-pointer"
                        >
                          <RefreshCw className={cn("w-3.5 h-3.5", isOutreachGenerating && "animate-spin")} />
                          Znovu vygenerovat s AI
                        </Button>

                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span>💡 Zkopírujte a odešlete na LinkedInu jako InMail nebo přímou zprávu Tech Leadovi.</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* OBSAH ZÁLOŽKY 3: ATS CV NA MÍRU */}
              {copilotTab === "cv" && (
                <div className="space-y-6">
                  <div className="p-6 rounded-2xl border border-white/20 bg-white/60 dark:bg-black/40 backdrop-blur-xl shadow-sm space-y-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center text-amber-500">
                        <FileText className="w-5 h-5" />
                      </div>
                      <div>
                        <h4 className="font-semibold text-lg">Dynamické 1-stránkové ATS CV na míru</h4>
                        <p className="text-xs text-muted-foreground">
                          Algoritmus vybere nejrelevantnější projekty a přeformuluje odrážky zkušeností do formátu STAR s důrazem na klíčová slova tohoto inzerátu.
                        </p>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                      <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5 text-center">
                        <span className="text-xs font-semibold block text-foreground">1 stránka A4</span>
                        <span className="text-[11px] text-muted-foreground">Přísné dodržení limitu</span>
                      </div>
                      <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5 text-center">
                        <span className="text-xs font-semibold block text-foreground">100% selektovatelný</span>
                        <span className="text-[11px] text-muted-foreground">Strojově čitelný text</span>
                      </div>
                      <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5 text-center">
                        <span className="text-xs font-semibold block text-foreground">STAR formát</span>
                        <span className="text-[11px] text-muted-foreground">Měřitelné výsledky</span>
                      </div>
                      <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5 text-center">
                        <span className="text-xs font-semibold block text-foreground">ATS Klíčová slova</span>
                        <span className="text-[11px] text-muted-foreground">Vysoká propustnost</span>
                      </div>
                    </div>
                  </div>

                  {isDownloadingCv ? (
                    <div className="p-8 rounded-2xl border border-amber-500/30 bg-amber-500/5 dark:bg-amber-500/10 flex flex-col items-center justify-center text-center gap-4 py-16 animate-pulse">
                      <div className="w-14 h-14 rounded-2xl bg-amber-500/20 flex items-center justify-center text-amber-500 shadow-inner">
                        <Loader2 className="w-7 h-7 animate-spin" />
                      </div>
                      <div>
                        <h4 className="font-bold text-lg">Generuji a optimalizuji ATS CV na míru (PDF)...</h4>
                        <p className="text-sm text-muted-foreground mt-1 max-w-md">
                          Přizpůsobujeme odrážky do formátu STAR, formátujeme na 1 stránku A4 a kompilujeme strojově čitelný PDF soubor.
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="p-8 rounded-2xl border border-white/20 bg-white/40 dark:bg-black/30 flex flex-col items-center justify-center text-center gap-5 py-12 shadow-sm backdrop-blur-xl">
                      <div className="w-14 h-14 rounded-2xl bg-amber-500/10 flex items-center justify-center text-amber-500 shadow-sm">
                        <FileText className="w-7 h-7" />
                      </div>
                      <div className="max-w-md">
                        <h4 className="font-bold text-xl mb-1">
                          {(job as any)?.tailored_cv_path ? "Přizpůsobené ATS CV je připraveno" : "Vygenerovat přizpůsobené ATS CV (PDF)"}
                        </h4>
                        <p className="text-sm text-muted-foreground leading-relaxed">
                          {(job as any)?.tailored_cv_path
                            ? "Životopis na míru byl pro tuto pozici úspěšně vytvořen. Můžete jej přímo stáhnout jedním kliknutím nebo přegenerovat."
                            : "Sestaví z vašeho profilu a textu pozice validní, strojově čitelné 1-stránkové PDF připravené k okamžitému odeslání."}
                        </p>
                      </div>

                      {(job as any)?.tailored_cv_path && (
                        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-500/10 border border-green-500/20 text-green-600 dark:text-green-400 text-xs font-semibold">
                          <Check className="w-3.5 h-3.5" />
                          <span>PDF zkompilováno na 1 stránku A4 (strojově čitelný text)</span>
                        </div>
                      )}

                      <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
                        <Button
                          size="lg"
                          disabled={isDownloadingCv}
                          onClick={handleDownloadTailoredCv}
                          className="gap-2 px-8 h-12 text-base font-semibold shadow-lg hover:shadow-amber-500/25 hover:scale-[1.02] transition-all bg-amber-500 text-white hover:bg-amber-600 cursor-pointer"
                        >
                          {isDownloadingCv ? (
                            <Loader2 className="w-5 h-5 animate-spin" />
                          ) : (
                            <Download className="w-5 h-5" />
                          )}
                          <span>Stáhnout ATS CV na míru (PDF)</span>
                        </Button>

                        {(job as any)?.tailored_cv_path && (
                          <Button
                            variant="outline"
                            size="lg"
                            disabled={isDownloadingCv}
                            onClick={handleDownloadTailoredCv}
                            className="gap-2 h-12 bg-white/50 dark:bg-black/40 border-white/20 text-xs cursor-pointer hover:bg-white/70 dark:hover:bg-black/60"
                          >
                            <RefreshCw className="w-4 h-4" />
                            <span>Přegenerovat</span>
                          </Button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </section>
          </div>
        </div>
      </ScrollArea>
  )
}
