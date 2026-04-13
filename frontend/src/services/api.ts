import axios from "axios";
import type { DailyGraph, Layer, Market } from "../types/graph";
import type { ThinkingNode, ThinkingSession } from "../types/thinking";
import { toast } from "../lib/toast";

const api = axios.create({ baseURL: "/api" });

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.detail ||
      error.response?.data?.error ||
      error.message;
    toast.error(message);
    return Promise.reject(error);
  },
);

export interface PoolItem {
  id: string;
  type: string;
  title?: string;
  ticker?: string;
  source?: string;
  url?: string;
  summary: string;
  direction: string;
  confidence: number;
  sectors?: string[];
  price?: number;
  high_52w?: number;
  discount_pct?: number;
  pe_ratio?: number | null;
  pb_ratio?: number;
  div_yield?: number;
  sector?: string;
}

export interface PoolsResponse {
  news: PoolItem[];
  value: PoolItem[];
}

export const graphApi = {
  getGraph: (date: string, market: Market = "US") =>
    api.get<DailyGraph>(`/graphs/${date}`, { params: { market } }),
  getDates: () => api.get<string[]>("/graphs/dates"),
  getNodeLayers: (nodeId: string) =>
    api.get<Layer[]>(`/nodes/${nodeId}/layers`),
  getPools: (date: string, market: Market = "US") =>
    api.get<PoolsResponse>(`/pools/${date}`, { params: { market } }),
  getLivePools: (date: string, market: Market = "US", topics: string = "") =>
    api.get<PoolsResponse>(`/pools/live/${date}`, {
      params: { market, topics },
    }),
  startThinking: (
    date: string,
    market: Market = "US",
    maxDepth: number = 3,
    selectedNewsIds?: string[],
  ) =>
    api.post<{ session_id: string; status: string }>("/thinking", {
      date,
      market,
      max_depth: maxDepth,
      selected_news_ids: selectedNewsIds,
    }),
  getSession: (sessionId: string) =>
    api.get<ThinkingSession>(`/thinking/${sessionId}`),
  thinkStep: (sessionId: string) =>
    api.post<{ status: string; current_layer: number }>(
      `/thinking/${sessionId}/step`,
    ),
  toggleNode: (sessionId: string, nodeId: string, selected: boolean) =>
    api.patch<{ dirty_count: number; status: string }>(
      `/thinking/${sessionId}/node/${nodeId}`,
      { selected },
    ),
  matchValues: (sessionId: string) =>
    api.post<{ opportunities: ThinkingNode[] }>(`/thinking/${sessionId}/match`),
  autoThink: (date: string, market: Market = "US", maxDepth: number = 3) =>
    api.post<{ session_id: string; status: string }>("/thinking/auto", {
      date,
      market,
      max_depth: maxDepth,
    }),
};
