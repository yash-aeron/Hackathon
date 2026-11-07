import type {
  HealthResponse,
  KitRequest,
  KitResponse,
  ListingsQuery,
  ListingsResponse,
  MatchRequest,
  MatchResponse,
  ParseProfileInput,
  ProfileParseResponse,
  SampleResumeResponse,
  VerifyRequest,
  VerifyResponse,
} from "./types";

/**
 * Base URL of the Scoutly API. Defaults to the local FastAPI/uvicorn server so
 * `npm run dev` works with zero configuration; override with
 * `NEXT_PUBLIC_API_URL` (see `.env.local.example`).
 */
export const API_BASE_URL: string = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}

interface RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  signal?: AbortSignal;
  timeoutMs?: number;
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const data: unknown = await response.json();
    if (data && typeof data === "object" && "detail" in data) {
      const detail = (data as { detail: unknown }).detail;
      if (typeof detail === "string" && detail.trim().length > 0) {
        return detail.trim();
      }
    }
  } catch {
    // Body was not JSON — fall through to status-based copy.
  }
  if (response.status === 404) {
    return "The API couldn't find that record. It may have been removed from the feed.";
  }
  if (response.status === 422) {
    return "The API rejected some of the fields we sent. Check your profile and try again.";
  }
  if (response.status >= 500) {
    return "The Scoutly API hit an internal error. Try again in a moment.";
  }
  return `The API rejected the request (HTTP ${response.status}).`;
}

async function withTimeout<T>(
  run: (signal: AbortSignal) => Promise<T>,
  externalSignal: AbortSignal | undefined,
  timeoutMs: number,
): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  const forwardAbort = () => controller.abort();
  if (externalSignal) {
    if (externalSignal.aborted) controller.abort();
    else externalSignal.addEventListener("abort", forwardAbort, { once: true });
  }

  try {
    return await run(controller.signal);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (timedOut) {
      throw new ApiError(
        0,
        `The Scoutly API took too long to respond. Is the backend running at ${API_BASE_URL}?`,
      );
    }
    if (controller.signal.aborted) {
      throw new ApiError(0, "Request cancelled.");
    }
    throw new ApiError(
      0,
      `Can't reach the Scoutly API at ${API_BASE_URL}. Start the backend, then retry.`,
    );
  } finally {
    clearTimeout(timer);
    externalSignal?.removeEventListener("abort", forwardAbort);
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal, timeoutMs = 30_000 } = options;

  return withTimeout(
    async (innerSignal) => {
      const headers: Record<string, string> = { Accept: "application/json" };
      let payload: BodyInit | undefined;
      if (body instanceof FormData) {
        payload = body;
      } else if (body !== undefined) {
        headers["Content-Type"] = "application/json";
        payload = JSON.stringify(body);
      }

      const response = await fetch(`${API_BASE_URL}${path}`, {
        method,
        headers,
        body: payload,
        signal: innerSignal,
      });

      if (!response.ok) {
        throw new ApiError(response.status, await readErrorDetail(response));
      }
      return (await response.json()) as T;
    },
    signal,
    timeoutMs,
  );
}

async function requestBlob(
  path: string,
  timeoutMs = 30_000,
  signal?: AbortSignal,
): Promise<Blob> {
  return withTimeout(
    async (innerSignal) => {
      const response = await fetch(`${API_BASE_URL}${path}`, {
        headers: { Accept: "text/calendar" },
        signal: innerSignal,
      });
      if (!response.ok) {
        throw new ApiError(response.status, await readErrorDetail(response));
      }
      return response.blob();
    },
    signal,
    timeoutMs,
  );
}

function listingsQuery(query: ListingsQuery): string {
  const params = new URLSearchParams();
  if (query.types && query.types.length > 0) {
    params.set("types", query.types.join(","));
  }
  if (query.mode) {
    params.set("mode", query.mode);
  }
  if (query.limit) {
    params.set("limit", String(query.limit));
  }
  const serialised = params.toString();
  return serialised ? `?${serialised}` : "";
}

function parseProfile(input: ParseProfileInput, signal?: AbortSignal) {
  if (input.kind === "text") {
    return request<ProfileParseResponse>("/api/profile/parse", {
      method: "POST",
      body: { text: input.text },
      signal,
      timeoutMs: 60_000,
    });
  }
  const form = new FormData();
  form.append("file", input.file);
  return request<ProfileParseResponse>("/api/profile/parse", {
    method: "POST",
    body: form,
    signal,
    timeoutMs: 60_000,
  });
}

/**
 * The single typed client the whole app uses. Nothing else may call `fetch`
 * against the API — keeping it here means one place for error normalisation,
 * timeouts, and the contract types.
 */
export const api = {
  health(signal?: AbortSignal): Promise<HealthResponse> {
    return request<HealthResponse>("/api/health", { signal, timeoutMs: 8_000 });
  },

  listings(
    query: ListingsQuery = {},
    signal?: AbortSignal,
  ): Promise<ListingsResponse> {
    return request<ListingsResponse>(`/api/listings${listingsQuery(query)}`, {
      signal,
    });
  },

  sampleResume(signal?: AbortSignal): Promise<SampleResumeResponse> {
    return request<SampleResumeResponse>("/api/sample-resume", {
      signal,
      timeoutMs: 15_000,
    });
  },

  parseProfile,

  match(payload: MatchRequest, signal?: AbortSignal): Promise<MatchResponse> {
    return request<MatchResponse>("/api/match", {
      method: "POST",
      body: payload,
      signal,
      timeoutMs: 60_000,
    });
  },

  verify(
    payload: VerifyRequest,
    signal?: AbortSignal,
  ): Promise<VerifyResponse> {
    return request<VerifyResponse>("/api/verify", {
      method: "POST",
      body: payload,
      signal,
      timeoutMs: 45_000,
    });
  },

  generateKit(payload: KitRequest, signal?: AbortSignal): Promise<KitResponse> {
    return request<KitResponse>("/api/kit", {
      method: "POST",
      body: payload,
      signal,
      timeoutMs: 90_000,
    });
  },

  calendarIcs(
    listingIds: number[],
    signal?: AbortSignal,
  ): Promise<Blob> {
    const ids = listingIds.join(",");
    return requestBlob(`/api/calendar.ics?listing_ids=${encodeURIComponent(ids)}`, 30_000, signal);
  },
};
