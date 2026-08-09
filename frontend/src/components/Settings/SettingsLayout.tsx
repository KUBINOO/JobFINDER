import React, { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import axios from "axios"
import { User, Cpu, Mail, Database, Save, Loader2, AlertTriangle } from "lucide-react"

import { Input } from "../ui/input"
import { Button } from "../ui/button"
import { Textarea } from "../ui/textarea"

const API_BASE = "http://localhost:8000/api"

export function SettingsLayout() {
  const [activeTab, setActiveTab] = useState("profile")
  const queryClient = useQueryClient()

  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: async () => {
      const res = await axios.get(`${API_BASE}/settings`)
      return res.data
    },
  })

  const updateMutation = useMutation({
    mutationFn: async (newSettings: any) => {
      const res = await axios.put(`${API_BASE}/settings`, newSettings)
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] })
      alert("Nastavení bylo úspěšně uloženo.")
    },
    onError: (err: any) => {
      alert("Chyba při ukládání nastavení: " + err.message)
    }
  })

  const testSmtpMutation = useMutation({
    mutationFn: async (smtpData: any) => {
      const res = await axios.post(`${API_BASE}/settings/test-smtp`, smtpData)
      return res.data
    },
    onSuccess: (data) => {
      alert("Úspěch: " + data.message)
    },
    onError: (err: any) => {
      alert("Chyba SMTP: " + (err.response?.data?.detail || err.message))
    }
  })

  const wipeDbMutation = useMutation({
    mutationFn: async () => {
      const res = await axios.delete(`${API_BASE}/applications/action/wipe`)
      return res.data
    },
    onSuccess: (data) => {
      alert("Úspěch: " + data.message)
      queryClient.invalidateQueries({ queryKey: ["jobs"] })
    },
    onError: (err: any) => {
      alert("Chyba při mazání: " + (err.response?.data?.detail || err.message))
    }
  })

  if (isLoading || !settings) {
    return <div className="flex-1 flex items-center justify-center">Načítání nastavení...</div>
  }

  const handleSave = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)
    const data = Object.fromEntries(formData.entries())
    
    if (data.smtp_port) data.smtp_port = parseInt(data.smtp_port as string, 10)
    if (data.scraper_delay_min) data.scraper_delay_min = parseFloat(data.scraper_delay_min as string)
    if (data.scraper_delay_max) data.scraper_delay_max = parseFloat(data.scraper_delay_max as string)

    const finalSettings = { ...settings, ...data }
    updateMutation.mutate(finalSettings)
  }

  const handleTestSmtp = () => {
    const host = prompt("Zadejte SMTP Host:", "smtp.gmail.com")
    if (!host) return
    testSmtpMutation.mutate({
      host,
      port: settings.smtp_port,
      username: settings.smtp_email,
      password: settings.smtp_password
    })
  }

  const handleWipe = () => {
    if (window.confirm("VAROVÁNÍ: Opravdu chcete smazat VŠECHNY uložené pozice a žádosti? Tato akce je nevratná!")) {
      wipeDbMutation.mutate()
    }
  }

  const handleExport = () => {
    alert("Export dat do CSV zatím není plně implementován, ale brzy bude!")
  }

  const tabs = [
    { id: "profile", label: "Můj profil", icon: User },
    { id: "ai", label: "AI a Chování", icon: Cpu },
    { id: "smtp", label: "Odesílání (SMTP)", icon: Mail },
    { id: "system", label: "Systém a Data", icon: Database },
  ]

  const labelClass = "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
  const selectClass = "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 bg-white dark:bg-black"

  return (
    <div className="flex flex-1 h-full bg-white/50 dark:bg-black/50 text-foreground overflow-hidden">
      <div className="w-64 border-r border-border bg-white dark:bg-black p-6 flex flex-col gap-2 shrink-0">
        <h2 className="text-xl font-bold mb-6 tracking-tight">Nastavení</h2>
        {tabs.map(tab => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all text-sm font-medium
                ${isActive 
                  ? "bg-black text-white dark:bg-white dark:text-black shadow-md" 
                  : "text-muted-foreground hover:bg-black/5 dark:hover:bg-white/10 hover:text-foreground"
                }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      <div className="flex-1 p-8 overflow-y-auto">
        <form onSubmit={handleSave} className="max-w-3xl mx-auto h-full flex flex-col">
          <div className="flex justify-between items-center mb-8 shrink-0">
            <h1 className="text-2xl font-bold">{tabs.find(t => t.id === activeTab)?.label}</h1>
            <Button type="submit" disabled={updateMutation.isPending} className="gap-2 rounded-xl px-6">
              {updateMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Uložit změny
            </Button>
          </div>

          <div className="flex-1 relative">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="space-y-8"
              >
                {activeTab === "profile" && (
                  <div className="space-y-6">
                    <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <label className={labelClass}>Celé jméno</label>
                        <Input name="full_name" defaultValue={settings.full_name || ""} placeholder="Jan Novák" className="bg-white dark:bg-black" />
                      </div>
                      <div className="space-y-2">
                        <label className={labelClass}>Telefon</label>
                        <Input name="phone_number" defaultValue={settings.phone_number || ""} placeholder="+420 123 456 789" className="bg-white dark:bg-black" />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <label className={labelClass}>Obor / Specializace</label>
                      <Input name="industry" defaultValue={settings.industry || ""} placeholder="Např. Frontend Vývojář" className="bg-white dark:bg-black" />
                    </div>
                    <div className="space-y-2">
                      <label className={labelClass}>Škola / Vzdělání</label>
                      <Input name="education" defaultValue={settings.education || ""} placeholder="ČVUT FIT" className="bg-white dark:bg-black" />
                    </div>
                    <div className="p-6 border border-dashed border-border rounded-xl bg-black/5 dark:bg-white/5 text-center mt-6">
                      <p className="text-sm text-muted-foreground mb-4">Nahrávání nového CV PDF přesunuto do existující Onboarding komponenty. Zde zatím nelze nahrát nové.</p>
                      <div className="text-xs font-mono bg-black/10 dark:bg-white/10 p-2 rounded truncate">Aktuální: {settings.cv_file_path || "Není nahráno"}</div>
                    </div>
                  </div>
                )}

                {activeTab === "ai" && (
                  <div className="space-y-6">
                    <div className="space-y-2">
                      <label className={labelClass}>Poskytovatel AI</label>
                      <select name="llm_provider" defaultValue={settings.llm_provider || "Google Gemini"} className={selectClass}>
                        <option value="Google Gemini">Google Gemini</option>
                        <option value="OpenAI">OpenAI</option>
                        <option value="Anthropic">Anthropic</option>
                        <option value="Ollama">Ollama (Lokální)</option>
                      </select>
                    </div>
                    <div className="space-y-2">
                      <label className={labelClass}>Model</label>
                      <Input name="llm_model" defaultValue={settings.llm_model || "gemini-1.5-flash"} className="bg-white dark:bg-black" />
                    </div>
                    <div className="space-y-2">
                      <label className={labelClass}>API Klíč</label>
                      <Input name="llm_api_key" type="password" defaultValue={settings.llm_api_key || ""} placeholder="sk-..." className="bg-white dark:bg-black font-mono text-sm" />
                    </div>
                    <div className="space-y-2">
                      <label className={labelClass}>Tón komunikace</label>
                      <select name="tone_of_voice" defaultValue={settings.tone_of_voice || "formal"} className={selectClass}>
                        <option value="formal">Korporátní formální (Dobrý den, vážení...)</option>
                        <option value="startup">Moderní startupový (Ahoj, zaujala mě...)</option>
                        <option value="creative">Kreativní a odvážný</option>
                      </select>
                    </div>
                    <div className="space-y-2">
                      <label className={labelClass}>Vlastní instrukce (Custom Prompt)</label>
                      <Textarea name="custom_prompt" defaultValue={settings.custom_prompt || ""} placeholder="Zde můžete připsat specifické požadavky na AI, např. 'Vždy zmiň můj projekt XYZ.'" className="h-32 bg-white dark:bg-black resize-none" />
                    </div>
                  </div>
                )}

                {activeTab === "smtp" && (
                  <div className="space-y-6">
                    <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <label className={labelClass}>E-mail pro přihlášení (Username)</label>
                        <Input name="smtp_email" defaultValue={settings.smtp_email || ""} placeholder="vas.email@gmail.com" className="bg-white dark:bg-black" />
                      </div>
                      <div className="space-y-2">
                        <label className={labelClass}>Heslo (App Password)</label>
                        <Input name="smtp_password" type="password" defaultValue={settings.smtp_password || ""} className="bg-white dark:bg-black font-mono text-sm" />
                        <div className="border-l-4 border-blue-500 bg-blue-50/50 dark:bg-blue-900/20 p-3 rounded-r-lg mt-2">
                          <p className="text-sm text-blue-900 dark:text-blue-200">
                            <strong>Důležité:</strong> Nezadávejte sem své běžné heslo k účtu (např. k Gmailu). Kvůli dvoufázovému ověření (2FA) je nutné ve vašem účtu vygenerovat speciální <strong>Heslo pro aplikace (App Password)</strong> určené přímo pro tento nástroj.
                          </p>
                        </div>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <label className={labelClass}>SMTP Port</label>
                      <Input name="smtp_port" type="number" defaultValue={settings.smtp_port || 587} className="bg-white dark:bg-black" />
                    </div>
                    <div className="pt-4">
                      <Button type="button" variant="secondary" onClick={handleTestSmtp} disabled={testSmtpMutation.isPending}>
                        {testSmtpMutation.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Mail className="w-4 h-4 mr-2" />}
                        Otestovat připojení
                      </Button>
                    </div>
                  </div>
                )}

                {activeTab === "system" && (
                  <div className="space-y-8">
                    <div className="space-y-4">
                      <h3 className="text-lg font-medium">Zpoždění Scraperu (Anti-ban)</h3>
                      <div className="grid grid-cols-2 gap-6">
                        <div className="space-y-2">
                          <label className={labelClass}>Minimum (sekundy)</label>
                          <Input name="scraper_delay_min" type="number" step="0.5" defaultValue={settings.scraper_delay_min || 2.0} className="bg-white dark:bg-black" />
                        </div>
                        <div className="space-y-2">
                          <label className={labelClass}>Maximum (sekundy)</label>
                          <Input name="scraper_delay_max" type="number" step="0.5" defaultValue={settings.scraper_delay_max || 5.0} className="bg-white dark:bg-black" />
                        </div>
                      </div>
                    </div>

                    <div className="pt-6 border-t border-border space-y-4">
                      <h3 className="text-lg font-medium">Export dat</h3>
                      <p className="text-sm text-muted-foreground">Stáhněte si kompletní historii žádostí ve formátu CSV.</p>
                      <Button type="button" variant="outline" onClick={handleExport}>
                        Exportovat do CSV
                      </Button>
                    </div>

                    <div className="pt-6 border-t border-red-200 dark:border-red-900/30 space-y-4">
                      <h3 className="text-lg font-medium text-red-600 dark:text-red-400 flex items-center gap-2">
                        <AlertTriangle className="w-5 h-5" />
                        Nebezpečná zóna (Danger Zone)
                      </h3>
                      <p className="text-sm text-muted-foreground">Tato akce trvale vymaže všechny sledované pozice a historii žádostí. Nastavení zůstane zachováno.</p>
                      <Button type="button" variant="destructive" onClick={handleWipe} disabled={wipeDbMutation.isPending}>
                        Smazat celou historii žádostí
                      </Button>
                    </div>
                  </div>
                )}
              </motion.div>
            </AnimatePresence>
          </div>
        </form>
      </div>
    </div>
  )
}
