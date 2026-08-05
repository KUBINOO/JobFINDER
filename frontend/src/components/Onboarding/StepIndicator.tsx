import React from "react"
import { cn } from "../../lib/utils"
import { Check } from "lucide-react"
import { motion } from "framer-motion"

interface StepIndicatorProps {
  steps: string[]
  currentStep: number
}

export function StepIndicator({ steps, currentStep }: StepIndicatorProps) {
  return (
    <div className="flex items-center justify-center w-full max-w-md mx-auto mb-10">
      {steps.map((step, index) => {
        const isCompleted = index < currentStep
        const isCurrent = index === currentStep

        return (
          <React.Fragment key={step}>
            <div className="relative flex flex-col items-center">
              <motion.div
                initial={false}
                animate={{
                  backgroundColor: isCompleted || isCurrent ? "hsl(var(--primary))" : "transparent",
                  borderColor: isCompleted || isCurrent ? "hsl(var(--primary))" : "rgba(150, 150, 150, 0.3)",
                  color: isCompleted || isCurrent ? "hsl(var(--primary-foreground))" : "hsl(var(--muted-foreground))"
                }}
                className={cn(
                  "flex items-center justify-center w-10 h-10 rounded-full border-2 z-10 font-semibold transition-colors duration-300",
                  !isCompleted && !isCurrent && "backdrop-blur-md bg-white/30 dark:bg-black/30"
                )}
              >
                {isCompleted ? <Check className="w-5 h-5" /> : <span>{index + 1}</span>}
              </motion.div>
              <span
                className={cn(
                  "absolute top-12 text-xs font-medium whitespace-nowrap transition-colors duration-300",
                  isCurrent ? "text-foreground" : "text-muted-foreground"
                )}
              >
                {step}
              </span>
            </div>
            {index < steps.length - 1 && (
              <div className="flex-1 h-[2px] mx-2 bg-black/10 dark:bg-white/10 relative overflow-hidden">
                <motion.div
                  initial={false}
                  animate={{
                    width: isCompleted ? "100%" : "0%"
                  }}
                  transition={{ duration: 0.4, ease: "easeInOut" }}
                  className="absolute inset-0 bg-primary h-full"
                />
              </div>
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}
