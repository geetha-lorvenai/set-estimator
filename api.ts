import type { Estimate, EstimateList } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public hints: string[] = [],
  ) {
    super(message);
  }
}

function describe(detail: unknown): { message: string; hints: string[] } {
  if (typeof detail === "string") return { message: detail, hints: [] };
  if (Array.isArray(detail)) {
    const msg = detail.map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : String(d))).join("; ");
    return { message: msg, hints: [] };
  }
  if (detail && typeof detail === "object" && "message" in detail) {
    const d = detail as { message: string; warnings?: string[] };
    return { message: d.message, hints: d.warnings ?? [] };
  }
  return { message: "Unexpected response from the server.", hints: [] };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, cache: "no-store" });
  } catch {
    throw new ApiError(`Can't reach the estimator API at ${API_URL}. Check that the backend is running.`, 0);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const { message, hints } = describe(body?.detail);
    throw new ApiError(message, response.status, hints);
  }
  return body as T;
}

export const createEstimate = (text: string) =>
  request<Estimate>("/estimates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

export const getEstimate = (id: string) => request<Estimate>(`/estimates/${encodeURIComponent(id)}`);

export const listEstimates = (limit = 50, offset = 0) =>
  request<EstimateList>(`/estimates?limit=${limit}&offset=${offset}`);
