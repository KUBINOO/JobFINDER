import React from "react"
import { Job, JobStatus } from "./JobCard"
import { ScrollArea } from "../ui/scroll-area"
import { Button } from "../ui/button"
import { Textarea } from "../ui/textarea"
import { Input } from "../ui/input"
import { Send, RefreshCw, Briefcase } from "lucide-react"
import { cn } from "../../lib/utils"

interface DetailPanelProps {
  job: Job | null;
  onStatusChange: (jobId: string, newStatus: JobStatus) => void;
}

export function DetailPanel({ job, onStatusChange }: DetailPanelProps) {
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

  const getScoreColor = (score?: number) => {
    if (score === undefined) return "text-muted-foreground"
    if (score >= 80) return "text-green-600 dark:text-green-400"
    if (score >= 50) return "text-yellow-600 dark:text-yellow-400"
    return "text-red-600 dark:text-red-400"
  }

  return (
    <>
      <ScrollArea className="flex-1 h-full">
        <div className="p-10 max-w-4xl mx-auto pb-40">
          <div className="mb-10">
            <div className="flex justify-between items-start">
              <div>
                <h1 className="text-4xl font-bold tracking-tight mb-2">{job.title}</h1>
                <div className="flex items-center text-lg text-muted-foreground gap-2">
                  <span className="font-medium text-foreground">{job.company}</span>
                  <span>•</span>
                  <span>Praha (Remote)</span>
                  <span>•</span>
                  <span className="text-sm px-2 py-1 bg-black/5 dark:bg-white/10 rounded-md">Plný úvazek</span>
                </div>
              </div>
              
              {/* Native select as fallback, replace with shadcn Select later */}
              <select 
                className="bg-white/50 dark:bg-black/30 border border-white/20 p-2 rounded-lg text-sm outline-none"
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
            
            {job.match_score !== undefined && (
              <div className="mt-6 p-4 rounded-xl border border-white/20 bg-white/40 dark:bg-black/20 flex items-start gap-4">
                <div className={cn("text-3xl font-bold pt-1", getScoreColor(job.match_score))}>
                  {job.match_score}%
                </div>
                <div>
                  <h4 className="font-semibold text-sm">AI Hodnocení (Match Score)</h4>
                  <p className="text-muted-foreground mt-1 text-sm">{job.match_reason}</p>
                </div>
              </div>
            )}
          </div>

          <div className="space-y-12">
            <section>
              <h3 className="text-xl font-semibold mb-4 border-b border-black/5 dark:border-white/5 pb-2">Popis pozice</h3>
              <div className="prose dark:prose-invert max-w-none text-muted-foreground leading-relaxed whitespace-pre-wrap text-sm">
                {job.description ? job.description : "Popis pozice zatím nebyl načten nebo je prázdný."}
              </div>
            </section>
            
            <section>
              <div className="flex items-center justify-between mb-6 border-b border-black/5 dark:border-white/5 pb-2">
                <h3 className="text-xl font-semibold">Vygenerovaný e-mail</h3>
                <Button variant="ghost" size="sm" className="h-8 gap-1.5 text-primary">
                  <RefreshCw className="w-3.5 h-3.5" />
                  Přegenerovat
                </Button>
              </div>
              
              {job.generated_body ? (
                <div className="space-y-6">
                  <div className="space-y-2">
                    <label className="text-sm font-semibold">Předmět e-mailu</label>
                    <Input defaultValue={job.generated_subject || ""} className="bg-white/50 dark:bg-black/30 text-base py-3 h-auto" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-semibold">Celý text (Upravte dle potřeby)</label>
                    <Textarea 
                      defaultValue={job.generated_body} 
                      className="bg-white/50 dark:bg-black/30 min-h-[350px] text-base leading-relaxed" 
                    />
                  </div>
                </div>
              ) : (
                <div className="space-y-6">
                  <div className="space-y-2">
                    <label className="text-sm font-semibold">Oslovení</label>
                    <Input defaultValue={`Vážený pane / Vážená paní v ${job.company},`} className="bg-white/50 dark:bg-black/30 text-base py-3 h-auto" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-semibold">Úvod</label>
                    <Textarea 
                      defaultValue={`reaguji na vaši nabídku práce na pozici ${job.title} a rád bych se ucházel o tuto příležitost.`} 
                      className="bg-white/50 dark:bg-black/30 min-h-[80px] text-base leading-relaxed" 
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-semibold">Moje zkušenosti</label>
                    <Textarea 
                      defaultValue={`Mám více než 5 let zkušeností s vývojem vysoce interaktivních a výkonných webových aplikací pomocí Reactu. V minulé roli jsem vedl frontend architekturu pro zásadní redesign produktu, který zvýšil zapojení uživatelů o 40 %.`} 
                      className="bg-white/50 dark:bg-black/30 min-h-[120px] text-base leading-relaxed" 
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-semibold">Shoda technologií</label>
                    <Textarea 
                      defaultValue={`Vaše požadavky na hluboké znalosti výkonu webu a responzivního designu dokonale odpovídají mým dovednostem. Jsem nadšený do tvorby plynulých uživatelských zážitků a rychle se orientuji v nových technologiích.`} 
                      className="bg-white/50 dark:bg-black/30 min-h-[120px] text-base leading-relaxed" 
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-semibold">Výzva k akci (CTA)</label>
                    <Textarea 
                      defaultValue={`V příloze zasílám svůj životopis. Těším se na případnou diskusi o tom, jak bych mohl být přínosem pro váš tým.`} 
                      className="bg-white/50 dark:bg-black/30 min-h-[80px] text-base leading-relaxed" 
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-semibold">Podpis</label>
                    <Input defaultValue="S pozdravem,\nJan Novák" className="bg-white/50 dark:bg-black/30 text-base py-3 h-auto" />
                  </div>
                </div>
              )}
            </section>
          </div>
        </div>
      </ScrollArea>
      <div className="absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-zinc-50 via-zinc-50/80 to-transparent dark:from-black dark:via-black/80 flex justify-center pb-8 pt-20 pointer-events-none">
        <Button 
          size="lg" 
          className="pointer-events-auto h-16 px-12 text-lg rounded-full shadow-2xl hover:shadow-primary/25 hover:scale-[1.02] transition-all bg-primary text-primary-foreground"
          onClick={() => onStatusChange(job.id, "Sent")}
        >
          <Send className="w-5 h-5 mr-3" />
          Schválit a odeslat
        </Button>
      </div>
    </>
  )
}
