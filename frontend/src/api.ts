import axios from "axios";

const tokenKey = "omnieye.accessToken";
const roleKey = "omnieye.role";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api/v1",
  timeout: 20_000,
});

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem(tokenKey);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearSession();
      if (window.location.pathname !== "/login") window.location.assign("/login");
    }
    return Promise.reject(error);
  },
);

export function setSession(token: string, role: string): void {
  sessionStorage.setItem(tokenKey, token);
  sessionStorage.setItem(roleKey, role);
}

export function clearSession(): void {
  sessionStorage.removeItem(tokenKey);
  sessionStorage.removeItem(roleKey);
}

export function getToken(): string | null {
  return sessionStorage.getItem(tokenKey);
}

export function getRole(): string | null {
  return sessionStorage.getItem(roleKey);
}

export function hasSession(): boolean {
  return Boolean(getToken());
}

export interface Device {
  id: number;
  hostname: string;
  ip_address: string;
  vendor: string;
  model: string | null;
  os_type: string;
  status: string;
  is_active: boolean;
  group_id: number | null;
  last_backup_at: string | null;
}

export interface DeviceGroup {
  id: number;
  name: string;
}

export interface Port {
  id: number;
  device_id: number;
  name: string;
  description: string | null;
  status: string;
  admin_status: string;
  vlan: number | null;
  mac_address: string | null;
  speed: string | null;
  duplex: string | null;
  last_change: string | null;
  last_discovered_at: string | null;
}

export interface LivePortConfig {
  device_id: number;
  port_id: number;
  interface_name: string;
  config_text: string;
  retrieved_at: string;
}
