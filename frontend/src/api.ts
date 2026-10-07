const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1").replace(/\/$/, "");

let accessToken: string | null = null;

export interface WorkspaceUser {
  id: string;
  email: string;
  full_name: string;
  role: "ADMIN" | "MANAGER" | "MEMBER";
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: WorkspaceUser;
}

interface MessageResponse { message: string; }

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = "ApiError";
  }
}

export function clearAccessToken(): void { accessToken = null; }

async function request<T>(path: string, init: RequestInit = {}, authenticated = false): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (authenticated && accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, { ...init, headers, credentials: "include" });
  } catch {
    throw new ApiError("The workspace API could not be reached. Check your connection and try again.", 0);
  }
  if (!response.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") message = body.detail;
      if (response.status === 401 && path !== "/auth/login") message = "Your session has expired. Sign in again.";
      if (response.status === 429) message = "Too many attempts. Wait a minute, then try again.";
    } catch {
      // Keep the generic message when the response is not JSON.
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function acceptToken(payload: TokenResponse): WorkspaceUser {
  accessToken = payload.access_token;
  return payload.user;
}

export async function restoreSession(): Promise<WorkspaceUser> {
  return acceptToken(await request<TokenResponse>("/auth/refresh", { method: "POST" }));
}

export async function signIn(email: string, password: string): Promise<WorkspaceUser> {
  const payload = await request<TokenResponse>("/auth/login", {
    method: "POST", body: JSON.stringify({ email, password }),
  });
  return acceptToken(payload);
}

export async function updatePassword(currentPassword: string, newPassword: string): Promise<string> {
  const payload = await request<MessageResponse>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  }, true);
  return payload.message;
}

export async function signOut(): Promise<void> {
  try {
    await request<MessageResponse>("/auth/logout", { method: "POST" });
  } finally {
    clearAccessToken();
  }
}
