import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { queryKeys } from '../api/queryKeys';
import { ApplicationStatus, JobApplication } from '../api/types';

/**
 * Fetches the application details from the backend.
 */
const fetchApplicationStatus = async (applicationId: string | number): Promise<JobApplication> => {
  const { data } = await apiClient.get<JobApplication>(`/applications/${applicationId}`);
  return data;
};

/**
 * Custom hook to fetch and intelligently poll the application status.
 * Leverages React Query v5 dynamic refetchInterval.
 */
export const useApplicationStatus = (applicationId: string | number | null) => {
  return useQuery({
    // Use the Query Key Factory to guarantee consistency
    queryKey: applicationId ? queryKeys.applications.detail(applicationId) : queryKeys.applications.details(),
    
    queryFn: () => {
      if (!applicationId) throw new Error('applicationId is required');
      return fetchApplicationStatus(applicationId);
    },
    
    // Only run the query if we have a valid ID
    enabled: !!applicationId,
    
    // Smart Polling Mechanism
    refetchInterval: (query) => {
      const data = query.state.data as JobApplication | undefined;
      
      // If we don't have data yet but the query is enabled, keep polling
      if (!data) return 2000;
      
      // List of non-terminal states where the backend is still processing
      const activeStatuses = [
        ApplicationStatus.PENDING,
        ApplicationStatus.SCRAPING,
        ApplicationStatus.GENERATING,
        ApplicationStatus.SENDING,
      ];
      
      // Poll every 2 seconds if active, else return false to STOP polling immediately
      return activeStatuses.includes(data.status as ApplicationStatus) ? 2000 : false;
    },
  });
};
