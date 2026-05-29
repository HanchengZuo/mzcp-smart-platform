const API_BASE = import.meta.env.VITE_API_BASE || "/api";

let token = localStorage.getItem("mzcp_token") || "";

export function setToken(value) {
  token = value || "";
  if (token) {
    localStorage.setItem("mzcp_token", token);
  } else {
    localStorage.removeItem("mzcp_token");
  }
}

export function getToken() {
  return token;
}

export function apiUrl(path) {
  return `${API_BASE}${path}`;
}

export async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(apiUrl(path), {
    ...options,
    headers,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const message =
      typeof payload === "object" && payload.message
        ? payload.message
        : "请求失败";
    throw new Error(message);
  }
  return payload;
}
