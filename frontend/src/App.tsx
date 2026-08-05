import { OnboardingWizard } from "./components/Onboarding/Wizard"
import { DashboardLayout } from "./components/Dashboard/Layout"
import { useSettings } from "./hooks/useSettings"

function App() {
  const { data: settings, isLoading, isError, isSuccess } = useSettings()

  if (isLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="flex flex-col items-center space-y-4">
          <div className="h-12 w-12 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"></div>
          <p className="text-gray-500 dark:text-gray-400">Načítání...</p>
        </div>
      </div>
    )
  }

  // If there's an error (e.g. 404) or no settings found, user needs onboarding
  if (isError || !settings) {
    return <OnboardingWizard onComplete={() => window.location.reload()} />
  }

  // If successful and settings exist, go to dashboard
  if (isSuccess && settings) {
    return <DashboardLayout />
  }

  return null
}

export default App
