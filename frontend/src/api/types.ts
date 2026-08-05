export enum ApplicationStatus {
  PENDING = 'PENDING',
  SCRAPING = 'SCRAPING',
  GENERATING = 'GENERATING',
  GENERATED = 'GENERATED',
  SENDING = 'SENDING',
  SENT = 'SENT',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
}

export interface JobApplication {
  id: number;
  user_id: number;
  job_id: number;
  status: ApplicationStatus;
  generated_subject: string | null;
  generated_body: string | null;
  error_logs: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateApplicationPayload {
  userId: number;
  jobUrl: string;
}

export interface CreateApplicationResponse {
  applicationId: number;
  status: ApplicationStatus;
  message: string;
}
