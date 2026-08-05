import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { queryKeys } from '../api/queryKeys';
import { CreateApplicationPayload, CreateApplicationResponse } from '../api/types';

/**
 * Executes the POST request to trigger the backend worker pipeline.
 */
const submitApplication = async (payload: CreateApplicationPayload): Promise<CreateApplicationResponse> => {
  const { data } = await apiClient.post<CreateApplicationResponse>('/applications', payload);
  return data;
};

/**
 * Custom hook to handle submitting a new application.
 * On success, it returns the newly created Application ID which can be passed to useApplicationStatus.
 */
export const useSubmitApplication = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: submitApplication,
    onSuccess: () => {
      // Invalidate the generic applications list to fetch the newly created job
      // once the user navigates to their dashboard.
      queryClient.invalidateQueries({
        queryKey: queryKeys.applications.lists(),
      });
    },
  });
};
