import axios from "axios";
import type { DailyGraph, Layer, Market } from "../types/graph";

const api = axios.create({ baseURL: "/api" });

export const graphApi = {
  getGraph: (date: string, market: Market = "US") =>
    api.get<DailyGraph>(`/graphs/${date}`, { params: { market } }),
  getDates: () => api.get<string[]>("/graphs/dates"),
  getNodeLayers: (nodeId: string) =>
    api.get<Layer[]>(`/nodes/${nodeId}/layers`),
};
