import { API_URL } from "@/lib/auth";

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
  });
  const body = await response.json().catch(() => null) as T | { detail?: string } | null;
  if (!response.ok) {
    const message = body && typeof body === "object" && "detail" in body && typeof body.detail === "string"
      ? body.detail
      : "The request could not be completed.";
    throw new ApiError(message, response.status);
  }
  return body as T;
}
