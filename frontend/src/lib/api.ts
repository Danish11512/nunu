import type {
  APIResponse,
  ScannerStatus,
  StartScannerRequest,
  StartResult,
  StopResult,
  EventsQueryParams,
  EventSummary,
  EventDetail,
  OrderbookSnapshot,
  CandidateResponse,
  ApproveCandidateRequest,
  ApproveCandidateResult,
  RejectCandidateRequest,
  TradeRecord,
  UpdateConfigRequest,
  ScannerConfigResponse,
  SwitchModeRequest,
  SwitchModeResult,
} from "./types";
import { API_BASE } from "./constants";

class ScannerAPI {
  private base: string;

  constructor(base: string = API_BASE) {
    this.base = base;
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    params?: Record<string, string | number | boolean | undefined | null>,
  ): Promise<APIResponse<T>> {
    let url = `${this.base}${path}`;

    if (params) {
      const searchParams = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null) {
          searchParams.set(key, String(value));
        }
      }
      const qs = searchParams.toString();
      if (qs) url += `?${qs}`;
    }

    const headers: Record<string, string> = {};
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    const json: APIResponse<T> = await response.json();

    if (!response.ok) {
      const errMsg = json.error?.message || `HTTP ${response.status}`;
      throw new Error(errMsg);
    }

    return json;
  }

  // ── Scanner Status & Control ─────────────────────────────────

  async getStatus(): Promise<APIResponse<ScannerStatus>> {
    return this.request<ScannerStatus>("GET", "/scanner/status");
  }

  async startScanner(req?: StartScannerRequest): Promise<APIResponse<StartResult>> {
    return this.request<StartResult>("POST", "/scanner/start", req);
  }

  async stopScanner(): Promise<APIResponse<StopResult>> {
    return this.request<StopResult>("POST", "/scanner/stop");
  }

  // ── Events ───────────────────────────────────────────────────

  async getEvents(params?: EventsQueryParams): Promise<APIResponse<EventSummary[]>> {
    return this.request<EventSummary[]>("GET", "/events", undefined, params as Record<string, string | number | boolean | undefined>);
  }

  async getEvent(ticker: string): Promise<APIResponse<EventDetail>> {
    return this.request<EventDetail>("GET", `/events/${encodeURIComponent(ticker)}`);
  }

  async getOrderbook(
    eventTicker: string,
    marketTicker: string,
    maxLevels?: number,
  ): Promise<APIResponse<OrderbookSnapshot>> {
    return this.request<OrderbookSnapshot>(
      "GET",
      `/events/${encodeURIComponent(eventTicker)}/orderbook`,
      undefined,
      { market_ticker: marketTicker, max_levels: maxLevels },
    );
  }

  // ── Candidates ───────────────────────────────────────────────

  async getCandidates(
    status?: string,
    eventTicker?: string,
  ): Promise<APIResponse<CandidateResponse[]>> {
    return this.request<CandidateResponse[]>(
      "GET",
      "/candidates",
      undefined,
      { status, event_ticker: eventTicker },
    );
  }

  async approveCandidate(
    eventTicker: string,
    req?: ApproveCandidateRequest,
  ): Promise<APIResponse<ApproveCandidateResult>> {
    return this.request<ApproveCandidateResult>(
      "POST",
      `/candidates/${encodeURIComponent(eventTicker)}/approve`,
      req,
    );
  }

  async rejectCandidate(
    eventTicker: string,
    req?: RejectCandidateRequest,
  ): Promise<APIResponse<null>> {
    return this.request<null>(
      "POST",
      `/candidates/${encodeURIComponent(eventTicker)}/reject`,
      req,
    );
  }

  // ── Trades ───────────────────────────────────────────────────

  async getTrades(
    mode?: string,
    limit?: number,
    offset?: number,
  ): Promise<APIResponse<TradeRecord[]>> {
    return this.request<TradeRecord[]>(
      "GET",
      "/trades",
      undefined,
      { mode, limit, offset },
    );
  }

  // ── Config ───────────────────────────────────────────────────

  async getConfig(): Promise<APIResponse<ScannerConfigResponse>> {
    return this.request<ScannerConfigResponse>("GET", "/config");
  }

  async updateConfig(req: UpdateConfigRequest): Promise<APIResponse<ScannerConfigResponse>> {
    return this.request<ScannerConfigResponse>("PUT", "/config", req);
  }

  // ── Mode ─────────────────────────────────────────────────────

  async switchMode(req: SwitchModeRequest): Promise<APIResponse<SwitchModeResult>> {
    return this.request<SwitchModeResult>("POST", "/mode", req);
  }
}

export { ScannerAPI };
export type { APIResponse } from "./types";
