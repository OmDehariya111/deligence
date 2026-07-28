export interface User {
  id: number;
  email: string;
  full_name?: string;
  is_admin?: boolean;
  tier?: string;
  credits?: number;
}

// Keep browser calls same-origin in production. Nginx routes /api to FastAPI, while
// next.config.ts rewrites the same path to the local backend during development.
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

// For server-side fetching, we need to manually pass the cookie.
// But for client-side fetching, credentials: 'include' handles it.
