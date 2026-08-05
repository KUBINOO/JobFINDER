import React, { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog"
import { Button } from "../ui/button"
import { Input } from "../ui/input"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import axios from "axios"
import { Search, RefreshCw } from "lucide-react"

const API_BASE = "http://localhost:8000/api"

export function AddJobModal({ children }: { children?: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  const [url, setUrl] = useState("")
  const queryClient = useQueryClient()

  const addJobMutation = useMutation({
    mutationFn: async (jobUrl: string) => {
      const res = await axios.post(`${API_BASE}/applications`, { url: jobUrl })
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] })
      setOpen(false)
      setUrl("")
      alert("Analýza spuštěna")
    }
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (url.trim()) {
      addJobMutation.mutate(url)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {children || (
          <Button className="w-full h-12 rounded-xl shadow-lg hover:shadow-xl transition-all flex items-center justify-center gap-2">
            <Search className="w-4 h-4" />
            <span>Zanalyzovat pozici</span>
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Nová žádost o práci</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-4">
          <Input 
            type="url"
            placeholder="Vložte odkaz na inzerát z jobs.cz, prace.cz..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="w-full h-12"
            autoFocus
          />
          <div className="flex justify-end pt-2">
            <Button 
              type="submit" 
              disabled={!url.trim() || addJobMutation.isPending}
              className="w-full sm:w-auto h-11"
            >
              {addJobMutation.isPending ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Spouštím...
                </>
              ) : (
                "Spustit analýzu"
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
