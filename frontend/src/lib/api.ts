// Thin fetch wrappers over the Component 5 FastAPI backend. Kept framework-agnostic
// (no Next.js-specific fetch caching) since every call here is a live, user-triggered
// mutation or lookup -- there's nothing worth caching.

export type Role = "doctor" | "nurse" | "billing_executive" | "technician" | "admin";

export interface LoginResponse {
  token: string;
  role: Role;
}

export interface Source {
  source_document: string;
  section_title: string;
  collection: string;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
  retrieval_type: "hybrid_rag" | "sql_rag";
  role: Role;
}

export interface CollectionsResponse {
  role: Role;
  collections: string[];
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string" ? body.detail : `Request failed with status ${res.status}`
    );
  }
  return res.json() as Promise<T>;
}

export function login(username: string, password: string): Promise<LoginResponse> {
  return fetch(`${API_URL}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  }).then((res) => handle<LoginResponse>(res));
}

export function chat(question: string, role: Role): Promise<ChatResponse> {
  return fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, role }),
  }).then((res) => handle<ChatResponse>(res));
}

export function getCollections(role: Role): Promise<CollectionsResponse> {
  return fetch(`${API_URL}/collections/${role}`).then((res) => handle<CollectionsResponse>(res));
}
