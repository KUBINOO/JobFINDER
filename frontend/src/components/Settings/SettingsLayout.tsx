import React, { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import axios from "axios"
import { User, Cpu, Mail, Database, Save, Loader2, AlertTriangle, UploadCloud, FileText, CheckCircle2, Sparkles, ExternalLink, HelpCircle, ArrowLeft } from "lucide-react"

import { Input } from "../ui/input"
import { Button } from "../ui/button"
import { Textarea } from "../ui/textarea"
import { AI_PROVIDERS, AI_MODELS, getDefaultModelForProvider } from "../../constants/aiModels"


const API_BASE = "http://localhost:8000/api"

interface SettingsLayoutProps {
  initialTab?: string;
  onBack?: () => void;
}

export function SettingsLayout({ initialTab = "profile", onBack }: SettingsLayoutProps) {
  const [activeTab, setActiveTab] = useState(initialTab)
  const queryClient = useQueryClient()

  useEffect(() => {
    if (initialTab) {
      setActiveTab(initialTab)
    }
  }, [initialTab])

  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: async () => {
      const res = await axios.get(`${API_BASE}/settings`)
      return res.data
    },
  })

  const [selectedProvider, setSelectedProvider] = useState<string>("Google Gemini")
  const [selectedModel, setSelectedModel] = useState<string>("gemini-3.7-flash")
  const [customModelMode, setCustomModelMode] = useState<boolean>(false)

  useEffect(() => {
    if (settings) {
      const prov = settings.llm_provider || "Google Gemini"
      setSelectedProvider(prov)
      let mod = settings.llm_model
      if (!mod || mod === "gemini-1.5-flash") {
        mod = getDefaultModelForProvider(prov)
      }
      setSelectedModel(mod)
      const isKnown = AI_MODELS[prov]?.some((m) => m.id === mod)
      if (!isKnown && mod) {
        setCustomModelMode(true)
      } else {
        setCustomModelMode(false)
      }
    }
  }, [settings])

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
      const detail = err.response?.data?.detail;
      const errorMsg = Array.isArray(detail) ? JSON.stringify(detail) : detail || err.message;
      alert("Chyba při ukládání nastavení: " + errorMsg)
    }
  })

  const testLlmMutation = useMutation({
    mutationFn: async (llmData: any) => {
      const res = await axios.post(`${API_BASE}/settings/test-llm`, llmData)
      return res.data
    },
    onSuccess: (data) => {
      alert("✅ Úspěch: " + data.message)
    },
    onError: (err: any) => {
      alert("❌ Chyba AI: " + (err.response?.data?.detail || err.message))
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

  const resetOnboardingMutation = useMutation({
    mutationFn: async () => {
      const res = await axios.delete(`${API_BASE}/settings/reset`)
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] })
      window.location.reload()
    },
    onError: (err: any) => {
      alert("Chyba při resetování nastavení: " + (err.response?.data?.detail || err.message))
    }
  })

  const uploadCvMutation = useMutation({
    mutationFn: async (file: File) => {
      const fileData = new FormData()
      fileData.append("file", file)
      const res = await axios.post(`${API_BASE}/upload-cv`, fileData, {
        headers: { "Content-Type": "multipart/form-data" }
      })
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] })
      alert("Životopis byl úspěšně nahrán a uložen!")
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      alert("Chyba při nahrávání CV: " + (detail || err.message))
    }
  })


  if (isLoading || !settings) {
    return <div className="flex-1 flex items-center justify-center">Načítání nastavení...</div>
  }

  const handleSave = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)
    const data: Record<string, any> = Object.fromEntries(formData.entries())

    if (data.smtp_port !== undefined) {
      data.smtp_port = data.smtp_port === "" ? null : parseInt(data.smtp_port as string, 10)
    }
    if (data.scraper_delay_min !== undefined) {
      data.scraper_delay_min = data.scraper_delay_min === "" ? null : parseFloat(data.scraper_delay_min as string)
    }
    if (data.scraper_delay_max !== undefined) {
      data.scraper_delay_max = data.scraper_delay_max === "" ? null : parseFloat(data.scraper_delay_max as string)
    }

    const finalSettings = { ...settings, ...data }
    updateMutation.mutate(finalSettings)
  }

  const handleTestLlm = (e: React.MouseEvent) => {
    e.preventDefault()
    const form = (e.currentTarget as HTMLElement).closest("form")
    if (!form) return
    const formData = new FormData(form)
    
    const provider = (formData.get("llm_provider") as string) || selectedProvider || "Google Gemini"
    let model = (formData.get("llm_model") as string) || selectedModel || getDefaultModelForProvider(provider)
    if (model === "gemini-1.5-flash") {
      model = "gemini-3.7-flash"
    }
    const api_key = (formData.get("llm_api_key") as string) ?? settings?.llm_api_key ?? ""
    const ollama_host = (formData.get("ollama_host") as string) || settings?.ollama_host || null

    if (provider !== "Ollama" && (!api_key || !api_key.trim())) {
      alert("Před testem prosím zadejte API klíč.")
      return
    }

    testLlmMutation.mutate({
      provider,
      model,
      api_key,
      ollama_host
    })
  }

  const handleTestSmtp = (e: React.MouseEvent) => {
    e.preventDefault()
    const form = (e.currentTarget as HTMLElement).closest("form")
    const formData = form ? new FormData(form) : null

    const host = ((formData?.get("smtp_host") as string) || settings?.smtp_host || "").trim() || "smtp.gmail.com"
    const port = formData?.get("smtp_port") ? parseInt(formData.get("smtp_port") as string, 10) : (settings?.smtp_port || 587)
    const username = ((formData?.get("smtp_email") as string) || settings?.smtp_email || "").trim()
    const password = ((formData?.get("smtp_password") as string) || settings?.smtp_password || "").trim()

    if (!username || !password) {
      alert("Před testem prosím vyplňte e-mail a heslo pro SMTP.")
      return
    }

    testSmtpMutation.mutate({
      host,
      port,
      username,
      password
    })
  }

  const handleWipe = () => {
    if (window.confirm("VAROVÁNÍ: Opravdu chcete smazat VŠECHNY uložené pozice a žádosti? Tato akce je nevratná!")) {
      wipeDbMutation.mutate()
    }
  }

  const handleResetOnboarding = () => {
    if (window.confirm("Opravdu chcete resetovat profil a nastavení a projít úvodním onboardingem znovu?")) {
      resetOnboardingMutation.mutate()
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
        {onBack && (
          <button
            onClick={onBack}
            className="flex items-center gap-2 text-xs font-medium text-muted-foreground hover:text-foreground mb-3 transition-colors group cursor-pointer"
          >
            <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
            <span>Zpět na přehled</span>
          </button>
        )}
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
                    <div className="p-4 rounded-xl border border-primary/20 bg-primary/5 text-sm text-muted-foreground flex items-start gap-3">
                      <HelpCircle className="w-5 h-5 text-primary shrink-0 mt-0.5" />
                      <p>
                        Informace z vašeho profilu a životopisu slouží AI jako podklad pro výpočet <strong>AI Hodnocení (Match score)</strong> a pro personalizaci motivačních e-mailů.
                      </p>
                    </div>

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
                    <div className="p-6 border-2 border-dashed border-primary/20 rounded-2xl bg-black/5 dark:bg-white/5 space-y-4 mt-6">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
                            <FileText className="w-5 h-5" />
                          </div>
                          <div>
                            <h4 className="text-sm font-semibold">Životopis (CV PDF)</h4>
                            <p className="text-xs text-muted-foreground">Aktuální soubor pro porovnání s inzeráty a generování dopisů</p>
                          </div>
                        </div>
                        <label className="cursor-pointer">
                          <input 
                            type="file" 
                            accept="application/pdf" 
                            className="hidden" 
                            onChange={(e) => {
                              if (e.target.files && e.target.files.length > 0) {
                                uploadCvMutation.mutate(e.target.files[0])
                              }
                            }}
                            disabled={uploadCvMutation.isPending}
                          />
                          <Button type="button" variant="outline" size="sm" className="gap-2 pointer-events-none" disabled={uploadCvMutation.isPending}>
                            {uploadCvMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
                            {uploadCvMutation.isPending ? "Nahrávání..." : "Nahrát nové PDF"}
                          </Button>
                        </label>
                      </div>
                      <div className="flex items-center gap-2 text-xs font-mono bg-black/10 dark:bg-white/10 p-2.5 rounded-lg truncate">
                        {settings.cv_file_path ? (
                          <>
                            <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
                            <span className="truncate">{settings.cv_file_path}</span>
                          </>
                        ) : (
                          <>
                            <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
                            <span className="text-amber-600 dark:text-amber-400 font-sans">Není nahráno žádné CV v PDF. Nahrajte svůj životopis pro přesné AI hodnocení.</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                )}


                {activeTab === "ai" && (() => {
                  const currentProviderConfig = AI_PROVIDERS.find((p) => p.name === selectedProvider) || AI_PROVIDERS[0]
                  const providerModels = AI_MODELS[selectedProvider] || []
                  const categories = Array.from(new Set(providerModels.map((m) => m.category)))
                  const activeModelObj = providerModels.find((m) => m.id === selectedModel)

                  return (
                    <div className="space-y-6">
                      {/* POSKYTOVATEL AI */}
                      <div className="space-y-2">
                        <label className={labelClass}>Poskytovatel AI</label>
                        <select 
                          name="llm_provider" 
                          value={selectedProvider} 
                          onChange={(e) => {
                            const newProv = e.target.value
                            setSelectedProvider(newProv)
                            const def = getDefaultModelForProvider(newProv)
                            setSelectedModel(def)
                            setCustomModelMode(false)
                          }} 
                          className={selectClass}
                        >
                          {AI_PROVIDERS.map((prov) => (
                            <option key={prov.name} value={prov.name}>
                              {prov.label}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* VÝBĚR MODELU */}
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <label className={labelClass}>Model ({selectedProvider})</label>
                          <button
                            type="button"
                            onClick={() => setCustomModelMode(!customModelMode)}
                            className="text-xs text-primary hover:underline font-medium"
                          >
                            {customModelMode ? "← Zpět na seznam předvoleb" : "⚙️ Zadat vlastní ID modelu"}
                          </button>
                        </div>

                        {customModelMode ? (
                          <div className="space-y-1">
                            <Input 
                              name="llm_model" 
                              value={selectedModel} 
                              onChange={(e) => setSelectedModel(e.target.value)}
                              placeholder="Např. gpt-5.6-sol nebo gemini-3.7-flash" 
                              className="bg-white dark:bg-black font-mono text-sm" 
                            />
                            <p className="text-[11px] text-muted-foreground">
                              Zadejte přesný identifikátor modelu podle oficiální dokumentace poskytovatele.
                            </p>
                          </div>
                        ) : (
                          <select 
                            name="llm_model" 
                            value={selectedModel} 
                            onChange={(e) => {
                              if (e.target.value === "__custom__") {
                                setCustomModelMode(true)
                              } else {
                                setSelectedModel(e.target.value)
                              }
                            }} 
                            className={selectClass}
                          >
                            {categories.map((cat) => (
                              <optgroup key={cat} label={cat}>
                                {providerModels
                                  .filter((m) => m.category === cat)
                                  .map((m) => (
                                    <option key={m.id} value={m.id}>
                                      {m.name} {m.badge ? `[${m.badge}]` : ""} ({m.id})
                                    </option>
                                  ))}
                              </optgroup>
                            ))}
                            <option value="__custom__">⚙️ Jiný vlastní model...</option>
                          </select>
                        )}

                        {activeModelObj && activeModelObj.description && !customModelMode && (
                          <div className="text-xs text-muted-foreground bg-black/5 dark:bg-white/5 px-3 py-2 rounded-lg flex items-center gap-2">
                            {activeModelObj.badge && (
                              <span className="font-semibold text-primary">{activeModelObj.badge}:</span>
                            )}
                            <span>{activeModelObj.description}</span>
                          </div>
                        )}
                      </div>

                      {/* OLLAMA HOST (POKUD OLLAMA) */}
                      {currentProviderConfig.isLocal ? (
                        <div className="space-y-2">
                          <label className={labelClass}>Ollama Host URL</label>
                          <Input 
                            name="ollama_host" 
                            defaultValue={settings?.ollama_host || "http://localhost:11434"} 
                            placeholder="http://localhost:11434" 
                            className="bg-white dark:bg-black font-mono text-sm" 
                          />
                          <p className="text-[11px] text-muted-foreground">
                            Ujistěte se, že Ollama běží lokálně na vašem počítači (<code>ollama serve</code>).
                          </p>
                        </div>
                      ) : (
                        /* API KLÍČ PRO CLOUD POSKYTOVATELE */
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <label className={labelClass}>API Klíč</label>
                            {currentProviderConfig.apiKeyHelpUrl && (
                              <a 
                                href={currentProviderConfig.apiKeyHelpUrl} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                className="text-xs text-primary hover:underline inline-flex items-center gap-1 font-medium"
                              >
                                <span>{currentProviderConfig.apiKeyHelpLabel || "Získat API klíč"}</span>
                                <ExternalLink className="w-3 h-3" />
                              </a>
                            )}
                          </div>
                          <Input 
                            name="llm_api_key" 
                            type="password" 
                            defaultValue={settings?.llm_api_key || ""} 
                            placeholder={currentProviderConfig.apiKeyPlaceholder} 
                            className="bg-white dark:bg-black font-mono text-sm" 
                          />
                          {currentProviderConfig.apiKeyNote && (
                            <div className="border-l-4 border-amber-500 bg-amber-50/50 dark:bg-amber-900/20 p-3 rounded-r-lg text-xs space-y-1">
                              <p className="font-semibold text-amber-900 dark:text-amber-200">
                                📌 Důležité pro {currentProviderConfig.name}:
                              </p>
                              <p className="text-amber-800 dark:text-amber-300">
                                {currentProviderConfig.apiKeyNote}
                              </p>
                            </div>
                          )}
                        </div>
                      )}

                      <div className="pt-2">
                        <Button 
                          type="button" 
                          variant="secondary" 
                          onClick={handleTestLlm} 
                          disabled={testLlmMutation.isPending}
                          className="gap-2"
                        >
                          {testLlmMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4 text-primary" />}
                          Otestovat AI připojení ({selectedProvider})
                        </Button>
                      </div>

                      <div className="space-y-2 pt-4 border-t border-border">
                        <label className={labelClass}>Tón komunikace</label>
                        <select name="tone_of_voice" defaultValue={settings?.tone_of_voice || "formal"} className={selectClass}>
                          <option value="formal">Korporátní formální (Dobrý den, vážení...)</option>
                          <option value="startup">Moderní startupový (Ahoj, zaujala mě...)</option>
                          <option value="creative">Kreativní a odvážný</option>
                        </select>
                      </div>
                      <div className="space-y-2">
                        <label className={labelClass}>Vlastní instrukce (Custom Prompt)</label>
                        <Textarea name="custom_prompt" defaultValue={settings?.custom_prompt || ""} placeholder="Zde můžete připsat specifické požadavky na AI, např. 'Vždy zmiň můj projekt XYZ.'" className="h-32 bg-white dark:bg-black resize-none" />
                      </div>
                    </div>
                  )
                })()}

                {activeTab === "smtp" && (
                  <div className="space-y-6">
                    <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <label className={labelClass}>SMTP Host / Server</label>
                        <Input name="smtp_host" defaultValue={settings?.smtp_host || ""} placeholder="smtp.gmail.com nebo smtp.seznam.cz" className="bg-white dark:bg-black" />
                      </div>
                      <div className="space-y-2">
                        <label className={labelClass}>SMTP Port</label>
                        <Input name="smtp_port" type="number" defaultValue={settings?.smtp_port || 587} className="bg-white dark:bg-black" />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <label className={labelClass}>E-mail pro přihlášení (Username / Adresa)</label>
                        <Input name="smtp_email" defaultValue={settings?.smtp_email || ""} placeholder="vas.email@gmail.com" className="bg-white dark:bg-black" />
                      </div>
                      <div className="space-y-2">
                        <label className={labelClass}>Heslo (App Password)</label>
                        <Input name="smtp_password" type="password" defaultValue={settings?.smtp_password || ""} className="bg-white dark:bg-black font-mono text-sm" />
                        <div className="border-l-4 border-blue-500 bg-blue-50/50 dark:bg-blue-900/20 p-3 rounded-r-lg mt-2">
                          <p className="text-sm text-blue-900 dark:text-blue-200">
                            <strong>Důležité:</strong> Nezadávejte sem své běžné heslo k účtu (např. k Gmailu). Kvůli dvoufázovému ověření (2FA) je nutné ve vašem účtu vygenerovat speciální <strong>Heslo pro aplikace (App Password)</strong> určené přímo pro tento nástroj.
                          </p>
                        </div>
                      </div>
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
                      <div className="space-y-2">
                        <p className="text-sm text-muted-foreground">Vymaže všechny sledované pozice a historii žádostí. Nastavení zůstane zachováno.</p>
                        <Button type="button" variant="destructive" onClick={handleWipe} disabled={wipeDbMutation.isPending}>
                          Smazat celou historii žádostí
                        </Button>
                      </div>

                      <div className="pt-4 border-t border-red-100 dark:border-red-900/20 space-y-2">
                        <p className="text-sm text-muted-foreground">Resetuje váš profil, životopis a nastavení a znovu spustí úvodního průvodce (Onboarding).</p>
                        <Button type="button" variant="outline" className="border-red-300 text-red-600 hover:bg-red-50 dark:border-red-800 dark:text-red-400" onClick={handleResetOnboarding} disabled={resetOnboardingMutation.isPending}>
                          Resetovat profil a projít onboardingem znovu
                        </Button>
                      </div>
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
