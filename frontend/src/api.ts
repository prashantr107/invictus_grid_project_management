const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1").replace(/\/$/, "");

let accessToken: string | null = null;
let refreshInFlight: Promise<void> | null = null;

export interface WorkspaceUser {
  id: string;
  email: string;
  full_name: string;
  role: "ADMIN" | "MANAGER" | "MEMBER";
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
}

export type ProjectStatus = "PLANNED" | "ACTIVE" | "COMPLETED" | "ARCHIVED";

export interface WorkspaceProject {
  id: string;
  key: string;
  name: string;
  description: string | null;
  status: ProjectStatus;
  due_date: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  manager_count: number;
  member_count: number;
}

export interface ProjectPage {
  items: WorkspaceProject[];
  total: number;
  offset: number;
  limit: number;
}

export interface ProjectMember {
  user_id: string;
  full_name: string;
  email: string;
  account_role: WorkspaceUser["role"];
  project_role: "MANAGER" | "MEMBER";
  is_active: boolean;
}

export interface ProjectMembership {
  project_id: string;
  managers: ProjectMember[];
  members: ProjectMember[];
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: WorkspaceUser;
}

interface MessageResponse { message: string; }

export interface UserPage {
  items: WorkspaceUser[];
  total: number;
  offset: number;
  limit: number;
}

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = "ApiError";
  }
}

export function clearAccessToken(): void { accessToken = null; }

async function sendRequest(path: string, init: RequestInit, authenticated: boolean): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (authenticated && accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  try {
    return await fetch(`${apiBaseUrl}${path}`, { ...init, headers, credentials: "include" });
  } catch {
    throw new ApiError("The workspace API could not be reached. Check your connection and try again.", 0);
  }
}

function refreshAccessToken(): Promise<void> {
  if (!refreshInFlight) {
    refreshInFlight = request<TokenResponse>("/auth/refresh", { method: "POST" })
      .then((payload) => { accessToken = payload.access_token; })
      .finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

async function request<T>(path: string, init: RequestInit = {}, authenticated = false): Promise<T> {
  let response = await sendRequest(path, init, authenticated);
  if (authenticated && response.status === 401) {
    try {
      await refreshAccessToken();
      response = await sendRequest(path, init, true);
    } catch (refreshError) {
      clearAccessToken();
      if (refreshError instanceof ApiError && refreshError.status === 0) throw refreshError;
      throw new ApiError("Your session has expired. Sign in again.", 401);
    }
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

export async function listUsers(offset: number, limit: number, search: string): Promise<UserPage> {
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  if (search.trim()) params.set("search", search.trim());
  return request<UserPage>(`/users?${params.toString()}`, { method: "GET" }, true);
}

export interface NewUser {
  full_name: string;
  email: string;
  role: WorkspaceUser["role"];
  initial_password: string;
}

export async function createUser(newUser: NewUser): Promise<WorkspaceUser> {
  return request<WorkspaceUser>("/users", { method: "POST", body: JSON.stringify(newUser) }, true);
}

export async function setUserActive(userId: string, isActive: boolean): Promise<WorkspaceUser> {
  return request<WorkspaceUser>(`/users/${userId}/status`, {
    method: "PATCH", body: JSON.stringify({ is_active: isActive }),
  }, true);
}

export async function setUserRole(userId: string, role: WorkspaceUser["role"]): Promise<WorkspaceUser> {
  return request<WorkspaceUser>(`/users/${userId}/role`, {
    method: "PATCH", body: JSON.stringify({ role }),
  }, true);
}

export async function listProjects(offset: number, limit: number, search: string): Promise<ProjectPage> {
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  if (search.trim()) params.set("search", search.trim());
  return request<ProjectPage>(`/projects?${params.toString()}`, { method: "GET" }, true);
}

export async function listAllUsers(): Promise<WorkspaceUser[]> {
  const firstPage = await listUsers(0, 100, "");
  const pages = await Promise.all(
    Array.from({ length: Math.ceil((firstPage.total - firstPage.items.length) / 100) }, (_, index) =>
      listUsers((index + 1) * 100, 100, "")),
  );
  return [...firstPage.items, ...pages.flatMap((page) => page.items)];
}

export interface NewProject {
  key: string;
  name: string;
  description: string | null;
  status: ProjectStatus;
  due_date: string | null;
  manager_ids: string[];
  member_ids: string[];
}

export async function createProject(project: NewProject): Promise<WorkspaceProject> {
  return request<WorkspaceProject>("/projects", { method: "POST", body: JSON.stringify(project) }, true);
}

export async function getProjectMembers(projectId: string): Promise<ProjectMembership> {
  return request<ProjectMembership>(`/projects/${projectId}/members`, { method: "GET" }, true);
}

export async function replaceProjectMembers(
  projectId: string,
  managerIds: string[],
  memberIds: string[],
): Promise<ProjectMembership> {
  return request<ProjectMembership>(`/projects/${projectId}/members`, {
    method: "PUT", body: JSON.stringify({ manager_ids: managerIds, member_ids: memberIds }),
  }, true);
}

export async function signOut(): Promise<void> {
  try {
    await request<MessageResponse>("/auth/logout", { method: "POST" });
  } finally {
    clearAccessToken();
  }
}
