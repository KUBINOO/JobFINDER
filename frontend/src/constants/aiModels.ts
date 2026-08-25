export interface AIModelOption {
  id: string;
  name: string;
  category: string;
  badge?: string;
  description?: string;
}

export interface AIProviderConfig {
  name: string;
  label: string;
  defaultModel: string;
  apiKeyPlaceholder: string;
  apiKeyHelpUrl?: string;
  apiKeyHelpLabel?: string;
  apiKeyNote?: string;
  isLocal?: boolean;
}

export const AI_PROVIDERS: AIProviderConfig[] = [
  {
    name: "Google Gemini",
    label: "Google Gemini (Doporučeno - zdarma)",
    defaultModel: "gemini-3.7-flash",
    apiKeyPlaceholder: "Váš API klíč z Google AI Studio",
    apiKeyHelpUrl: "https://aistudio.google.com/app/apikey",
    apiKeyHelpLabel: "Získat Gemini API klíč zdarma na Google AI Studio",
    apiKeyNote: "Zadejte platný API klíč z Google AI Studio (aistudio.google.com). Nezadávejte Google Cloud Project ID ('gen-lang-client...').",
  },
  {
    name: "OpenAI",
    label: "OpenAI (ChatGPT & GPT-5.6)",
    defaultModel: "gpt-5.6",
    apiKeyPlaceholder: "sk-proj-...",
    apiKeyHelpUrl: "https://platform.openai.com/api-keys",
    apiKeyHelpLabel: "Získat OpenAI API klíč na platform.openai.com",
    apiKeyNote: "Zadejte platný OpenAI API klíč (obvykle začíná na 'sk-').",
  },
  {
    name: "Anthropic",
    label: "Anthropic (Claude 5 / 4.5)",
    defaultModel: "claude-fable-5",
    apiKeyPlaceholder: "sk-ant-...",
    apiKeyHelpUrl: "https://console.anthropic.com/settings/keys",
    apiKeyHelpLabel: "Získat Anthropic API klíč na console.anthropic.com",
    apiKeyNote: "Zadejte platný Anthropic API klíč (začíná na 'sk-ant-').",
  },
  {
    name: "DeepSeek",
    label: "DeepSeek (V4 & R1)",
    defaultModel: "deepseek-v4-pro",
    apiKeyPlaceholder: "sk-...",
    apiKeyHelpUrl: "https://platform.deepseek.com/api_keys",
    apiKeyHelpLabel: "Získat DeepSeek API klíč na platform.deepseek.com",
    apiKeyNote: "Zadejte svůj API klíč z DeepSeek Platform.",
  },
  {
    name: "Kimi / Moonshot AI",
    label: "Kimi / Moonshot AI (K3 & K2.7)",
    defaultModel: "kimi-k3",
    apiKeyPlaceholder: "sk-...",
    apiKeyHelpUrl: "https://platform.moonshot.cn/console/api-keys",
    apiKeyHelpLabel: "Získat API klíč na platform.moonshot.cn / moonshot.ai",
    apiKeyNote: "Zadejte svůj Moonshot / Kimi API klíč.",
  },
  {
    name: "Ollama",
    label: "Ollama (Lokální LLM)",
    defaultModel: "llama3",
    apiKeyPlaceholder: "Není potřeba",
    isLocal: true,
  },
];

export const AI_MODELS: Record<string, AIModelOption[]> = {
  "Google Gemini": [
    // Gemini 3.x
    { id: "gemini-3.7-flash", name: "Gemini 3.7 Flash", category: "Aktuální řada Gemini 3.x", badge: "⚡ Doporučeno", description: "Nejnovější high-performance Flash model" },
    { id: "gemini-3.6-flash", name: "Gemini 3.6 Flash", category: "Aktuální řada Gemini 3.x", description: "Rychlý multimodální model" },
    { id: "gemini-3.5-flash", name: "Gemini 3.5 Flash", category: "Aktuální řada Gemini 3.x", description: "Levnější general-purpose model" },
    { id: "gemini-3.5-flash-lite", name: "Gemini 3.5 Flash-Lite", category: "Aktuální řada Gemini 3.x", badge: "💰 Ultra levný", description: "Ultra cheap / high throughput" },
    { id: "gemini-3.1-flash-lite", name: "Gemini 3.1 Flash-Lite", category: "Aktuální řada Gemini 3.x", description: "Velmi levný, ale výkonný" },
    { id: "gemini-3.1-pro", name: "Gemini 3.1 Pro", category: "Aktuální řada Gemini 3.x", badge: "🧠 Reasoning", description: "Pokročilé reasoning schopnosti" },
    { id: "gemini-3-flash", name: "Gemini 3 Flash", category: "Aktuální řada Gemini 3.x", description: "Frontier-class Flash model" },
    
    // Specializované & Gemini 2.5
    { id: "gemini-2.5-pro", name: "Gemini 2.5 Pro", category: "Gemini 2.5 & Specializované", description: "Osvědčený reasoning model" },
    { id: "gemini-2.5-flash", name: "Gemini 2.5 Flash", category: "Gemini 2.5 & Specializované", description: "Předchozí generace Flash" },
    { id: "gemini-3.1-flash-live", name: "Gemini 3.1 Flash Live", category: "Gemini 2.5 & Specializované", description: "Realtime interakce" },
    { id: "gemini-3.1-flash-tts", name: "Gemini 3.1 Flash TTS", category: "Gemini 2.5 & Specializované", description: "Text-to-speech podpora" },
    { id: "gemini-3.5-live-translate", name: "Gemini 3.5 Live Translate", category: "Gemini 2.5 & Specializované", description: "Překlady v reálném čase" },
    { id: "gemini-omni-flash", name: "Gemini Omni Flash", category: "Gemini 2.5 & Specializované", description: "Všestranný multimodální model" },
  ],

  "OpenAI": [
    // Frontier / GPT-5.6
    { id: "gpt-5.6", name: "GPT-5.6 Sol", category: "Frontier / Hlavní řada GPT-5.6", badge: "🧠 Flagship", description: "Absolutní flagship, reasoning, coding, research" },
    { id: "gpt-5.6-terra", name: "GPT-5.6 Terra", category: "Frontier / Hlavní řada GPT-5.6", badge: "⚖️ Balanc", description: "Kompromis výkon/cena" },
    { id: "gpt-5.6-luna", name: "GPT-5.6 Luna", category: "Frontier / Hlavní řada GPT-5.6", badge: "⚡ Rychlý", description: "Levnější, vysoký throughput" },

    // Další GPT modely
    { id: "gpt-5.5", name: "GPT-5.5", category: "Další aktuální GPT modely" },
    { id: "gpt-5.5-pro", name: "GPT-5.5 Pro", category: "Další aktuální GPT modely" },
    { id: "gpt-5.4", name: "GPT-5.4", category: "Další aktuální GPT modely" },
    { id: "gpt-5.4-pro", name: "GPT-5.4 Pro", category: "Další aktuální GPT modely" },
    { id: "gpt-5.4-mini", name: "GPT-5.4 mini", category: "Další aktuální GPT modely" },
    { id: "gpt-5.4-nano", name: "GPT-5.4 nano", category: "Další aktuální GPT modely" },
    { id: "gpt-5.3-codex", name: "GPT-5.3-Codex", category: "Další aktuální GPT modely", badge: "💻 Coding" },
    { id: "gpt-5.2", name: "GPT-5.2", category: "Další aktuální GPT modely" },
    { id: "gpt-5.2-pro", name: "GPT-5.2 Pro", category: "Další aktuální GPT modely" },
    { id: "gpt-5.1", name: "GPT-5.1", category: "Další aktuální GPT modely" },
    { id: "gpt-5", name: "GPT-5", category: "Další aktuální GPT modely" },
    { id: "gpt-5-mini", name: "GPT-5 mini", category: "Další aktuální GPT modely" },
    { id: "gpt-5-nano", name: "GPT-5 nano", category: "Další aktuální GPT modely" },
    { id: "gpt-5-pro", name: "GPT-5 Pro", category: "Další aktuální GPT modely" },
    { id: "o3", name: "o3", category: "Další aktuální GPT modely", badge: "🧠 Reasoning" },
    { id: "o3-pro", name: "o3-pro", category: "Další aktuální GPT modely", badge: "🧠 Deep reasoning" },
    { id: "gpt-4.1", name: "GPT-4.1", category: "Další aktuální GPT modely" },
    { id: "gpt-4.1-mini", name: "GPT-4.1 mini", category: "Další aktuální GPT modely" },
    { id: "gpt-4o", name: "GPT-4o", category: "Další aktuální GPT modely" },
    { id: "gpt-4o-mini", name: "GPT-4o mini", category: "Další aktuální GPT modely" },

    // Specializované & Open-weight
    { id: "gpt-5.6-cyber", name: "GPT-5.6 Cyber", category: "Specializované & Open-weight", description: "Cybersecurity specializace" },
    { id: "gpt-oss-120b", name: "gpt-oss-120b", category: "Specializované & Open-weight", description: "Open-weight model 120B" },
    { id: "gpt-oss-20b", name: "gpt-oss-20b", category: "Specializované & Open-weight", description: "Open-weight model 20B" },
  ],

  "Anthropic": [
    // Claude 5 / 4.5
    { id: "claude-fable-5", name: "Claude Fable 5", category: "Nová řada Claude 5 / 4.5", badge: "🧠 Nejvyšší výkon", description: "1M context, adaptive reasoning, dlouhé agentické úlohy" },
    { id: "claude-opus-5", name: "Claude Opus 5", category: "Nová řada Claude 5 / 4.5", badge: "🧠 Reasoning", description: "1M context, 128K output, reasoning & enterprise coding" },
    { id: "claude-sonnet-5", name: "Claude Sonnet 5", category: "Nová řada Claude 5 / 4.5", badge: "⚖️ Nejlepší balanc", description: "1M context, 128K output, rychlý a vyvážený" },
    { id: "claude-haiku-4.5", name: "Claude Haiku 4.5", category: "Nová řada Claude 5 / 4.5", badge: "⚡ Rychlý & Levný", description: "200K context, 64K output, vysoká rychlost" },

    // Claude 3.x
    { id: "claude-3-7-sonnet", name: "Claude 3.7 Sonnet", category: "Claude 3.x", description: "Hybrid reasoning model" },
    { id: "claude-3-5-sonnet", name: "Claude 3.5 Sonnet", category: "Claude 3.x", description: "Spolehlivý model" },
    { id: "claude-3-5-haiku", name: "Claude 3.5 Haiku", category: "Claude 3.x", description: "Rychlý model" },
  ],

  "DeepSeek": [
    // DeepSeek V4
    { id: "deepseek-v4-pro", name: "DeepSeek-V4-Pro", category: "DeepSeek V4 Generace", badge: "🧠 Flagship", description: "1.6T total params, 49B active, 1M context" },
    { id: "deepseek-v4-flash", name: "DeepSeek-V4-Flash", category: "DeepSeek V4 Generace", badge: "⚡ Rychlý", description: "284B total, 13B active, 1M context" },
    { id: "deepseek-v4-flash-vision-exp", name: "DeepSeek-V4-Flash-Vision-Exp", category: "DeepSeek V4 Generace", badge: "👁️ Vize", description: "Experimentální multimodální model" },

    // Starší modely
    { id: "deepseek-v3", name: "DeepSeek-V3", category: "Předchozí verze", description: "V3 generace" },
    { id: "deepseek-r1", name: "DeepSeek-R1", category: "Předchozí verze", badge: "🧠 Reasoning", description: "Open reasoning model" },
    { id: "deepseek-coder", name: "DeepSeek-Coder", category: "Předchozí verze", description: "Coding specializace" },
  ],

  "Kimi / Moonshot AI": [
    // Kimi K3 / K2.7
    { id: "kimi-k3", name: "Kimi K3", category: "Aktuální Kimi K3 & K2.x", badge: "🧠 Flagship", description: "2.8T parameters, 1M context, reasoning & coding" },
    { id: "kimi-k2.7-code", name: "Kimi K2.7 Code", category: "Aktuální Kimi K3 & K2.x", badge: "💻 Coding", description: "256K context, optimalizováno pro kódování" },
    { id: "kimi-k2.7-code-highspeed", name: "Kimi K2.7 Code Highspeed", category: "Aktuální Kimi K3 & K2.x", badge: "⚡ Rychlý", description: "Rychlý coding engine" },
    { id: "kimi-k2.6", name: "Kimi K2.6", category: "Aktuální Kimi K3 & K2.x", description: "Multimodal + reasoning + agents" },

    // Starší modely
    { id: "kimi-k2.5", name: "Kimi K2.5", category: "Předchozí verze" },
    { id: "moonshot-v1-128k", name: "Moonshot V1 128K", category: "Předchozí verze" },
  ],

  "Ollama": [
    { id: "llama3", name: "Llama 3 (8B)", category: "Lokální modely (Ollama)" },
    { id: "llama3.1", name: "Llama 3.1 (8B / 70B)", category: "Lokální modely (Ollama)" },
    { id: "mistral", name: "Mistral (7B)", category: "Lokální modely (Ollama)" },
    { id: "deepseek-r1", name: "DeepSeek-R1 (Lokální)", category: "Lokální modely (Ollama)" },
    { id: "qwen2.5-coder", name: "Qwen 2.5 Coder", category: "Lokální modely (Ollama)" },
  ],
};

export function getDefaultModelForProvider(providerName: string): string {
  const provider = AI_PROVIDERS.find((p) => p.name === providerName);
  if (provider) return provider.defaultModel;
  return "gemini-3.7-flash";
}
