import axios from "axios";
import { getAuthToken } from "@/lib/auth";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "";

const API = axios.create({
  baseURL,
});

API.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    (config.headers as any)["Authorization"] = `Bearer ${token}`;
  }
  return config;
});

export interface AuthRequest {
  username: string;
  password: string;
}

export interface AuthResponse {
  token: string;
  username: string;
}

export interface ShortenRequest {
  url: string;
  custom_alias?: string;
  expiry?: string;
}

export interface ShortenResponse {
  short_url: string;
}

export interface StatsResponse {
  short_code: string;
  original_url: string;
  clicks: number;
  expiry: string | null;
}

export interface UrlItem {
  short_code: string;
  original_url: string;
  clicks: number;
  expiry: string | null;
  short_url: string | null;
}

export interface UrlsListResponse {
  items: UrlItem[];
  limit: number;
  skip: number;
}

export const shortenUrl = async (data: ShortenRequest) => {
  const response = await API.post("/api/shorten", data);
  return response.data;
};

export const registerUser = async (data: AuthRequest) => {
  const response = await API.post<AuthResponse>("/api/register", data);
  return response.data;
};

export const loginUser = async (data: AuthRequest) => {
  const response = await API.post<AuthResponse>("/api/login", data);
  return response.data;
};

export const getStats = async (shortCode: string) => {
  const response = await API.get(`/api/stats/${shortCode}`);
  return response.data;
};

export const listUrls = async (params?: { limit?: number; skip?: number }) => {
  const response = await API.get<UrlsListResponse>("/api/urls", { params });
  return response.data;
};