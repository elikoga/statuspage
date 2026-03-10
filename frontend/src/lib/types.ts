export interface DayStatus {
  date: string;
  status: string;
}

export interface Service {
  id: string;
  name: string;
  description?: string | null;
  url?: string | null;
  site_url?: string | null;
  status: string;
  group?: string | null;
  is_public: boolean;
  check_enabled: boolean;
  on_demand: boolean;
  check_type: string;
  check_command?: string | null;
  failure_threshold: number;
  last_checked_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Incident {
  id: string;
  title: string;
  body: string;
  status: string;
  created_at: string;
  updated_at: string;
}
