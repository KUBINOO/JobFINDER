import { useState, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { StepIndicator } from "./StepIndicator"
import { Button } from "../ui/button"
import { Input } from "../ui/input"
import { Card, CardContent } from "../ui/card"
import { UploadCloud, ChevronRight, ChevronLeft } from "lucide-react"
import { apiClient } from "../../api/client"

import { useQueryClient } from "@tanstack/react-query"
import { AI_PROVIDERS, AI_MODELS, getDefaultModelForProvider } from "../../constants/aiModels"

// Konstanty s kroky wizardu v češtině
const STEPS = ["Základní údaje", "Dokumenty", "Motor aplikace"]

export function OnboardingWizard({ onComplete }: { onComplete: () => void }) {
  const queryClient = useQueryClient()
  const [step, setStep] = useState(0)
  const [direction, setDirection] = useState(1)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const [formData, setFormData] = useState({
    name: "",
    age: "",
    education: "",
    industry: "",
    linkedin_url: "",
    provider: "Google Gemini",
    model: "gemini-3.7-flash",
    api_key: "",
    ollama_host: "",
    smtp_email: "",
    smtp_password: "",
    smtp_port: "587",
  })
  
  const [cvFile, setCvFile] = useState<File | null>(null)

  const handleComplete = async () => {
    setIsSubmitting(true)
    try {
      if (cvFile) {
        const fileData = new FormData()
        fileData.append("file", cvFile)
        await apiClient.post("/upload-cv", fileData, {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        })
      }

      const payload = {
        full_name: formData.name.trim() || null,
        age: formData.age ? parseInt(formData.age, 10) : null,
        education: formData.education.trim() || null,
        industry: formData.industry.trim() || null,
        linkedin_url: formData.linkedin_url.trim() || null,
        llm_provider: formData.provider,
        llm_model: formData.model,
        llm_api_key: formData.api_key.trim() || null,
        ollama_host: formData.ollama_host.trim() || null,
        smtp_email: formData.smtp_email.trim() || "",
        smtp_password: formData.smtp_password.trim() || "",
        smtp_port: formData.smtp_port ? parseInt(formData.smtp_port, 10) : 587,
      };
      
      console.log("Sending payload to /api/settings:", payload);
      const response = await apiClient.put("/settings", payload);
      console.log("Response from /api/settings:", response.data);

      queryClient.setQueryData(["settings"], response.data);
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
      onComplete();
    } catch (err: any) {
      console.error("Error saving settings:", err.response?.data || err.message || err);
      const detail = err.response?.data?.detail;
      const errorMsg = Array.isArray(detail) ? JSON.stringify(detail) : (detail || err.message || "Neznámá chyba");
      alert("Došlo k chybě při ukládání nastavení: " + errorMsg);
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDevSkip = async () => {
    setIsSubmitting(true)
    try {
      const response = await apiClient.put("/settings", {
        full_name: "Jan Novák",
        age: 30,
        education: "Vysoká škola",
        industry: "IT / Software",
        linkedin_url: "https://linkedin.com/in/devtest",
        llm_provider: "Google Gemini",
        llm_model: "gemini-3.7-flash",
        llm_api_key: null,
        ollama_host: null,
        smtp_email: "dev@test.local",
        smtp_password: "devpassword123",
        smtp_port: 587,
      })
      queryClient.setQueryData(["settings"], response.data);
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
      onComplete()
    } catch (err: any) {
      console.error(err)
      const detail = err.response?.data?.detail;
      alert("Došlo k chybě při ukládání DEV testovacích dat: " + (detail || err.message || ""));
    } finally {
      setIsSubmitting(false)
    }
  }


  // Přechod na další krok
  const nextStep = () => {
    if (step < STEPS.length - 1) {
      setDirection(1)
      setStep((prev) => prev + 1)
    } else {
      handleComplete()
    }
  }

  // Návrat na předchozí krok
  const prevStep = () => {
    if (step > 0) {
      setDirection(-1)
      setStep((prev) => prev - 1)
    }
  }

  // Varianty pro plynulé animace framer-motion (Apple-like spring)
  const variants = {
    enter: (direction: number) => ({
      x: direction > 0 ? 50 : -50,
      opacity: 0,
      scale: 0.95,
    }),
    center: {
      zIndex: 1,
      x: 0,
      opacity: 1,
      scale: 1,
    },
    exit: (direction: number) => ({
      zIndex: 0,
      x: direction < 0 ? 50 : -50,
      opacity: 0,
      scale: 0.95,
    }),
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen w-full px-6 py-12 relative overflow-hidden">
      <StepIndicator steps={STEPS} currentStep={step} />

      <Card className="w-full max-w-xl mx-auto shadow-2xl bg-white/60 dark:bg-black/40 border-white/40 dark:border-white/10 backdrop-blur-2xl">
        <CardContent className="p-8 min-h-[400px] flex flex-col relative overflow-hidden">
          <AnimatePresence custom={direction} mode="wait">
            <motion.div
              key={step}
              custom={direction}
              variants={variants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{
                x: { type: "spring", stiffness: 300, damping: 30 },
                opacity: { duration: 0.2 },
                scale: { duration: 0.2 },
              }}
              className="flex-1 flex flex-col"
            >
              {step === 0 && <Step1Bio formData={formData} setFormData={setFormData} />}
              {step === 1 && <Step2Docs formData={formData} setFormData={setFormData} cvFile={cvFile} setCvFile={setCvFile} />}
              {step === 2 && <Step3API formData={formData} setFormData={setFormData} />}
            </motion.div>
          </AnimatePresence>

          <div className="mt-8 flex items-center justify-between pt-4 border-t border-black/5 dark:border-white/5">
            <Button
              variant="ghost"
              onClick={prevStep}
              disabled={step === 0 || isSubmitting}
              className="opacity-70 hover:opacity-100"
            >
              <ChevronLeft className="w-4 h-4 mr-2" />
              Zpět
            </Button>
            <Button onClick={nextStep} variant="default" disabled={isSubmitting} className="min-w-[120px] rounded-xl shadow-lg shadow-primary/20">
              {isSubmitting ? "Ukládání..." : (step === STEPS.length - 1 ? "Začít" : "Pokračovat")}
              {!isSubmitting && step !== STEPS.length - 1 && <ChevronRight className="w-4 h-4 ml-2" />}
            </Button>
          </div>
        </CardContent>
      </Card>
      
      {import.meta.env.DEV && (
        <div className="mt-8">
          <Button 
            variant="outline" 
            onClick={handleDevSkip} 
            disabled={isSubmitting}
            className="border-dashed border-primary/50 text-primary/70 hover:text-primary transition-colors"
          >
            DEV: Přeskočit a naplnit testovacími daty
          </Button>
        </div>
      )}
    </div>
  )
}

function Step1Bio({ formData, setFormData }: any) {
  return (
    <div className="flex flex-col h-full space-y-6">
      <div className="space-y-1 text-center mb-4">
        <h2 className="text-3xl font-semibold tracking-tight">Řekněte nám o sobě</h2>
        <p className="text-muted-foreground text-sm">Tyto údaje použijeme k přizpůsobení vašich žádostí.</p>
      </div>
      <div className="space-y-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Celé jméno</label>
          <Input 
            placeholder="Jan Novák" 
            value={formData.name}
            onChange={(e) => setFormData({...formData, name: e.target.value})}
            className="h-12 text-lg bg-white/40 dark:bg-black/20" 
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Věk (Volitelné)</label>
            <Input 
              type="number" 
              placeholder="28" 
              value={formData.age}
              onChange={(e) => setFormData({...formData, age: e.target.value})}
              className="bg-white/40 dark:bg-black/20" 
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Nejvyšší dosažené vzdělání</label>
            <Input 
              placeholder="Ing. Informatika" 
              value={formData.education}
              onChange={(e) => setFormData({...formData, education: e.target.value})}
              className="bg-white/40 dark:bg-black/20" 
            />
          </div>
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Obor / Zaměření</label>
          <Input 
            placeholder="např. Frontend vývojář, Produktový design" 
            value={formData.industry}
            onChange={(e) => setFormData({...formData, industry: e.target.value})}
            className="bg-white/40 dark:bg-black/20" 
          />
        </div>
      </div>
    </div>
  )
}

function Step2Docs({ formData, setFormData, cvFile, setCvFile }: any) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setCvFile(e.target.files[0])
    }
  }

  return (
    <div className="flex flex-col h-full space-y-6">
      <div className="space-y-1 text-center mb-4">
        <h2 className="text-3xl font-semibold tracking-tight">Váš životopis</h2>
        <p className="text-muted-foreground text-sm">Nahrajte svůj základní životopis, ze kterého budeme generovat dopisy.</p>
      </div>
      
      <input 
        type="file" 
        accept="application/pdf" 
        className="hidden" 
        ref={fileInputRef} 
        onChange={handleFileChange}
      />
      
      <div 
        onClick={() => fileInputRef.current?.click()}
        className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-primary/20 rounded-2xl bg-white/20 dark:bg-black/10 hover:bg-white/40 dark:hover:bg-black/30 transition-colors cursor-pointer group p-10"
      >
        <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mb-8 group-hover:scale-110 transition-transform">
          <UploadCloud className="w-10 h-10 text-primary" />
        </div>
        <h3 className="font-medium text-xl mb-2">{cvFile ? cvFile.name : "Přetáhněte PDF sem"}</h3>
        <p className="text-base text-muted-foreground mt-2">
          {cvFile ? "Soubor vybrán. Klikněte pro změnu." : "nebo klikněte pro výběr souboru"}
        </p>
      </div>

      <div className="space-y-2 mt-4">
        <label className="text-sm font-medium">URL LinkedIn (Volitelné)</label>
        <Input 
          placeholder="https://linkedin.com/in/uzivatel" 
          value={formData.linkedin_url}
          onChange={(e) => setFormData({...formData, linkedin_url: e.target.value})}
          className="bg-white/40 dark:bg-black/20" 
        />
      </div>
    </div>
  )
}

function Step3API({ formData, setFormData }: any) {
  const currentProviderConfig = AI_PROVIDERS.find((p) => p.name === formData.provider) || AI_PROVIDERS[0]
  const providerModels = AI_MODELS[formData.provider] || []
  const categories = Array.from(new Set(providerModels.map((m) => m.category)))
  const isOllama = currentProviderConfig.isLocal

  const handleProviderChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newProvider = e.target.value
    const defModel = getDefaultModelForProvider(newProvider)
    setFormData({
      ...formData,
      provider: newProvider,
      model: defModel
    })
  }

  return (
    <div className="flex flex-col h-full space-y-6">
      <div className="space-y-1 text-center mb-4">
        <h2 className="text-3xl font-semibold tracking-tight">Motor aplikace</h2>
        <p className="text-muted-foreground text-sm">Nakonfigurujte LLM a poštovní server pro automatizaci.</p>
      </div>
      
      <div className="space-y-5">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Poskytovatel AI</label>
              <select 
                value={formData.provider}
                onChange={handleProviderChange}
                className="flex h-11 w-full rounded-xl border border-input/50 bg-white/40 dark:bg-black/20 backdrop-blur-sm px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 transition-all appearance-none"
              >
                {AI_PROVIDERS.map((p) => (
                  <option key={p.name} value={p.name} className="bg-background text-foreground">{p.label}</option>
                ))}
              </select>
            </div>
            
            <div className="space-y-2">
              <label className="text-sm font-medium">Model</label>
              <select 
                value={formData.model}
                onChange={(e) => setFormData({...formData, model: e.target.value})}
                className="flex h-11 w-full rounded-xl border border-input/50 bg-white/40 dark:bg-black/20 backdrop-blur-sm px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 transition-all appearance-none"
              >
                {categories.map((cat) => (
                  <optgroup key={cat} label={cat} className="bg-background text-foreground font-semibold">
                    {providerModels
                      .filter((m) => m.category === cat)
                      .map((m) => (
                        <option key={m.id} value={m.id} className="bg-background text-foreground font-normal">
                          {m.name} {m.badge ? `[${m.badge}]` : ""} ({m.id})
                        </option>
                      ))}
                  </optgroup>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-2">
            {isOllama ? (
              <>
                <label className="text-sm font-medium">Ollama Host URL</label>
                <Input 
                  type="text" 
                  value={formData.ollama_host || "http://localhost:11434"} 
                  onChange={(e) => setFormData({...formData, ollama_host: e.target.value})}
                  placeholder="http://localhost:11434" 
                  className="h-11 bg-white/40 dark:bg-black/20" 
                />
              </>
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium">API Klíč ({formData.provider})</label>
                  {currentProviderConfig.apiKeyHelpUrl && (
                    <a 
                      href={currentProviderConfig.apiKeyHelpUrl} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="text-xs text-primary hover:underline"
                    >
                      {currentProviderConfig.apiKeyHelpLabel || "Získat klíč"}
                    </a>
                  )}
                </div>
                <Input 
                  type="password" 
                  value={formData.api_key}
                  onChange={(e) => setFormData({...formData, api_key: e.target.value})}
                  placeholder={currentProviderConfig.apiKeyPlaceholder} 
                  className="h-11 bg-white/40 dark:bg-black/20 font-mono text-sm" 
                />
                {currentProviderConfig.apiKeyNote && (
                  <p className="text-xs text-amber-600 dark:text-amber-400">
                    {currentProviderConfig.apiKeyNote}
                  </p>
                )}
              </>
            )}
          </div>
        </div>
        
        <div className="pt-4 border-t border-black/5 dark:border-white/5 space-y-4">
          <h4 className="text-sm font-semibold">Doručování e-mailů (SMTP)</h4>
          <div className="space-y-3">
            <div className="grid grid-cols-4 gap-4">
              <Input 
                placeholder="E-mailová adresa (např. user@gmail.com)" 
                type="email" 
                value={formData.smtp_email}
                onChange={(e) => setFormData({...formData, smtp_email: e.target.value})}
                className="col-span-3 h-11 bg-white/40 dark:bg-black/20" 
              />
              <select 
                value={formData.smtp_port}
                onChange={(e) => setFormData({...formData, smtp_port: e.target.value})}
                className="col-span-1 flex h-11 w-full rounded-xl border border-input/50 bg-white/40 dark:bg-black/20 backdrop-blur-sm px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 transition-all appearance-none"
              >
                <option value="587" className="bg-background text-foreground">587 (STARTTLS)</option>
                <option value="465" className="bg-background text-foreground">465 (SSL)</option>
              </select>
            </div>
            <div className="grid grid-cols-1 gap-2">
              <Input 
                placeholder="Heslo / App Password" 
                type="password" 
                value={formData.smtp_password}
                onChange={(e) => setFormData({...formData, smtp_password: e.target.value})}
                className="h-11 bg-white/40 dark:bg-black/20" 
              />
              <div className="border-l-4 border-blue-500 bg-blue-50/50 dark:bg-blue-900/20 p-3 rounded-r-lg mt-1">
                <p className="text-sm text-blue-900 dark:text-blue-200">
                  <strong>Důležité:</strong> Nezadávejte sem své běžné heslo k účtu (např. k Gmailu). Kvůli dvoufázovému ověření (2FA) je nutné ve vašem účtu vygenerovat speciální <strong>Heslo pro aplikace (App Password)</strong> určené přímo pro tento nástroj.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
