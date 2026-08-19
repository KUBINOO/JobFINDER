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
  Check
} from "lucide-react"
import { cn } from "../../lib/utils"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import axios from "axios"
import { useSettings } from "../../hooks/useSettings"

const API_BASE = "http://localhost:8000/api"

interface DetailPanelProps {
  job: Job | null;
  onStatusChange: (jobId: string, newStatus: JobStatus) => void;
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

export function DetailPanel({ job, onStatusChange }: DetailPanelProps) {
  const queryClient = useQueryClient()
  const { data: settings } = useSettings()

  const [recipientEmail, setRecipientEmail] = useState("")
  const [emailSubject, setEmailSubject] = useState("")
  const [emailBody, setEmailBody] = useState("")
  const [copied, setCopied] = useState(false)

  // Synchronizace lokálního stavu editoru při změně vybraného inzerátu nebo vygenerování textu
  useEffect(() => {
    if (job) {
      setEmailSubject(job.generated_subject || `Zájem o pozici: ${job.title}`)
      setEmailBody(job.generated_body || "")
      setRecipientEmail("")
    }
  }, [job?.id, job?.generated_body, job?.generated_subject, job?.title])

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

  const isGenerating = job.status === "Generating" || generateMutation.isPending
  const isSending = job.status === "Sending" || sendEmailMutation.isPending
  const hasGeneratedEmail = Boolean(job.generated_body || emailBody)
  const isSent = job.status === "Sent" || job.status === "Completed"

  const getScoreColor = (score?: number) => {
    if (score === undefined) return "text-muted-foreground"
    if (score >= 80) return "text-green-600 dark:text-green-400"
    if (score >= 50) return "text-yellow-600 dark:text-yellow-400"
    return "text-red-600 dark:text-red-400"
  }

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
                className="bg-white/50 dark:bg-black/30 border border-white/20 p-2 rounded-lg text-sm outline-none font-medium"
                value={job.status}
                onChange={(e) => onStatusChange(job.id, e.target.value as JobStatus)}
              >
                <option value="Pending">Čeká</option>
                <option value="Scraping">Stahuji data</option>
                <option value="Generating">Analyzuji</option>
                <option value="Generated">Připraveno</option>
                <option value="Sending">Odesílám</option>
                <option value="Sent">Posláno</option>
                <option value="Completed">Hotovo</option>
                <option value="Failed">Selhalo</option>
                <option value="Interview">Pohovor</option>
                <option value="Rejected">Zamítnuto</option>
                <option value="Offer">Nabídka</option>
              </select>
            </div>
            
            {/* AI Hodnocení (Match Score) pokud existuje */}
            {job.match_score !== undefined && (
              <div className="mt-6 p-4 rounded-xl border border-white/20 bg-white/40 dark:bg-black/20 flex items-start gap-4 shadow-sm">
                <div className={cn("text-3xl font-bold pt-1", getScoreColor(job.match_score))}>
                  {job.match_score}%
                </div>
                <div>
                  <h4 className="font-semibold text-sm">AI Hodnocení shody s vaším profilem</h4>
                  <p className="text-muted-foreground mt-1 text-sm">{job.match_reason}</p>
                </div>
              </div>
            )}

            {/* Chybová hláška */}
            {job.status === "Failed" && job.error_logs && (
              <div className="mt-6 p-4 rounded-xl border border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300 text-sm flex flex-col gap-1">
                <span className="font-semibold">Chyba zpracování inzerátu:</span>
                <p className="whitespace-pre-wrap font-mono text-xs">{job.error_logs}</p>
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
            
            {/* SEKCE 2: AI GENEROVÁNÍ A SMTP STRUKTURA E-MAILU */}
            <section className="pt-4">
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
                  <Button 
                    size="lg"
                    onClick={() => generateMutation.mutate(job.id)}
                    className="gap-2 px-8 h-12 text-base font-semibold shadow-lg hover:shadow-primary/25 hover:scale-[1.02] transition-all bg-primary text-primary-foreground"
                  >
                    <Sparkles className="w-5 h-5" />
                    Vygenerovat e-mail pomocí AI
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
                      onClick={() => sendEmailMutation.mutate({
                        jobId: job.id,
                        recipient: recipientEmail,
                        subject: emailSubject,
                        body: emailBody
                      })}
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
            </section>
          </div>
        </div>
      </ScrollArea>
  )
}
