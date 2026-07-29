export interface User {
  id: number;
  email: string;
  full_name?: string;
  is_admin?: boolean;
  tier?: string;
  credits?: number;
}

// In production, next.config.ts rewrites /api/v1/* to the backend.
// This keeps browser calls same-origin, avoiding CORS issues.
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "/api/v1";
