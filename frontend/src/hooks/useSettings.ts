import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api/client';

export interface UserSettings {
  id: number;
  full_name: string | null;
  phone_number: string | null;
  age: number | null;
  education: string | null;
  industry: string | null;
  cv_file_path: string | null;
  linkedin_url: string | null;
  llm_provider: string;
  llm_model: string;
  llm_api_key: string | null;
  ollama_host: string | null;
  tone_of_voice?: string | null;
  custom_prompt?: string | null;
  smtp_host?: string | null;
  smtp_email: string;
  smtp_password: string;
  smtp_port: number;
  scraper_delay_min?: number | null;
  scraper_delay_max?: number | null;
}

const fetchSettings = async (): Promise<UserSettings> => {
  try {
    const response = await apiClient.get('/settings');
    return response.data;
  } catch (error: any) {
    if (error.response && error.response.status === 404) {
      throw new Error('Nastavení nenalezeno');
    }
    throw new Error('Chyba při načítání nastavení');
  }
};

export const useSettings = () => {
  return useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
    retry: false, // Don't retry on 404 (new user)
    refetchOnWindowFocus: false, // Prevent onboarding wizard reset on alt-tab
  });
};
