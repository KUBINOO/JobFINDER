export enum ApplicationStatus {
  PENDING = 'PENDING',
  SCRAPING = 'SCRAPING',
  GENERATING = 'GENERATING',
  GENERATED = 'GENERATED',
  SENDING = 'SENDING',
  SENT = 'SENT',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
  INTERVIEW = 'INTERVIEW',
  REJECTED = 'REJECTED',
  OFFER = 'OFFER',
}

export type MarketType = 'cz' | 'global' | 'hybrid';
export type EmploymentTypeFilter = 'ALL' | 'PART_TIME' | 'CONTRACTOR';
export type TimezoneFilter = 'EMEA' | 'WORLDWIDE' | 'ANY';

export interface JobApplication {
  id: string;
  title: string;
  company: string;
  description: string;
  status: string;
  dateAdded: string;
  match_score?: number | null;
  match_reason?: string | null;
  pros?: string[];
  cons?: string[];
  missing_skills?: string[];
  part_time_viability?: string | null;
  source_portal?: string;
  employment_type?: string;
  remote_policy?: string;
  timezone_region?: string;
  generated_subject?: string | null;
  generated_body?: string | null;
  error_logs?: string | null;
  url?: string;
  source_url?: string;
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

export interface ExploreRequestPayload {
  count: number;
  query?: string;
  sources?: string[];
  locations?: string[];
  market?: MarketType;
  employment_type?: EmploymentTypeFilter;
  timezone?: TimezoneFilter;
}

