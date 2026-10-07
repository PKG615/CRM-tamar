import { createContext, useContext, useState, useCallback, useEffect } from "react";
import { api, getToken, setToken, clearToken, auth as authApi } from "../api/client";

const AuthContext = createContext(null);

const WRITERS = ["ADMIN", "SALES_MANAGER", "SALES_EXECUTIVE"];
const MANAGERS = ["ADMIN", "SALES_MANAGER"];

export function AuthProvider({ children }) {
  const [isAuthed, setIsAuthed] = useState(!!getToken());
  const [me, setMe] = useState(null);

  // Mirrors the server's role rules for showing/hiding controls only; the API
  // enforces them regardless (a hidden button is a convenience, not security).
  const role = me?.role;
  const perms = {
    canWrite: WRITERS.includes(role),      // everything except VIEWER
    canManage: MANAGERS.includes(role),    // settings, assignment, team list
    isAdmin: role === "ADMIN",             // create/edit users
  };

  const loadMe = useCallback(async () => {
    try {
      setMe(await api.get("/users/me"));
    } catch {
      setMe(null);
    }
  }, []);

  useEffect(() => {
    if (isAuthed) loadMe();
    else setMe(null);
  }, [isAuthed, loadMe]);

  const login = useCallback(async (slug, email, password) => {
    const res = await authApi.login(slug, email, password);
    setToken(res.access_token);
    setIsAuthed(true);
  }, []);

  const register = useCallback(async (orgName, adminName, adminEmail, adminPassword) => {
    const res = await authApi.register(orgName, adminName, adminEmail, adminPassword);
    setToken(res.access_token);
    setIsAuthed(true);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setIsAuthed(false);
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthed, me, ...perms, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
