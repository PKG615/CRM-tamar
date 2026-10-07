const TOKEN_KEY = "crm_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(path, { method = "GET", body, params } = {}) {
  let url = `/api${path}`;
  if (params) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
    ).toString();
    if (qs) url += `?${qs}`;
  }

  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  // Only treat 401 as "session expired" when we actually sent a token. A 401 on the
  // login call itself means wrong credentials and must reach the form as an error.
  if (res.status === 401 && token && !path.startsWith("/auth/")) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Session expired");
  }

  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed (${res.status})`);
  }

  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  get: (path, params) => request(path, { params }),
  post: (path, body) => request(path, { method: "POST", body }),
  put: (path, body) => request(path, { method: "PUT", body }),
};

export const auth = {
  login: (organization_slug, email, password) =>
    request("/auth/login", { method: "POST", body: { organization_slug, email, password } }),
  register: (organization_name, admin_name, admin_email, admin_password) =>
    request("/auth/register", {
      method: "POST",
      body: { organization_name, admin_name, admin_email, admin_password },
    }),
};
