/**
 * Query Key Factory Pattern
 * Provides a structured and type-safe way to define query keys across the application,
 * preventing typos and ensuring consistent cache invalidation.
 */
export const queryKeys = {
  applications: {
    all: ['applications'] as const,
    lists: () => [...queryKeys.applications.all, 'list'] as const,
    list: (filters: Record<string, any>) => [...queryKeys.applications.lists(), { filters }] as const,
    details: () => [...queryKeys.applications.all, 'detail'] as const,
    detail: (id: string | number) => [...queryKeys.applications.details(), id] as const,
  },
  // Add other domain entities here (users, jobs, etc.)
};
