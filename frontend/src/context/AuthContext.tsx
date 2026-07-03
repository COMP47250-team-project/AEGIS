// frontend/src/context/AuthContext.tsx
// Auth context — provides user state and login/logout to the entire app
/* eslint-disable react-refresh/only-export-components -- context + hook co-located intentionally */

import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode } from "react";
import apiClient, { setAccessToken } from "../api/client";

// Types
export interface User {
  id: string;
  email: string;
  role: "student" | "professor";
  name: string | null;
}

interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  // True while the session is being restored from the refresh cookie on load.
  // Route guards should wait for this to be false before redirecting.
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string, role: "student" | "professor") => Promise<void>;
  logout: () => Promise<void>;
}

interface RefreshResponse {
  access_token: string;
  user?: User;
}

// Context — undefined default forces usage within AuthProvider
const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

// Provider — wraps the app and broadcasts auth state
export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const isAuthenticated = user !== null;

  // On mount, try to restore the session from the httpOnly refresh cookie.
  // A fresh access token + user come back if the cookie is still valid;
  // otherwise the user stays logged out. This is what makes a page refresh
  // keep the user signed in.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await apiClient.post<RefreshResponse>("/auth/refresh");
        if (!cancelled && data.user) {
          setAccessToken(data.access_token);
          setUser(data.user);
        }
      } catch {
        // No valid session — remain logged out.
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // login — POST credentials, store access token and user
  // (refresh token is set as an httpOnly cookie by the backend)
  const login = useCallback(async (email: string, password: string) => {
    const { data } = await apiClient.post<AuthResponse>("/auth/login", {
      email,
      password,
    });
    setAccessToken(data.access_token);
    setUser(data.user);
  }, []);

  // register — create account then auto login
  const register = useCallback(
    async (name: string, email: string, password: string, role: "student" | "professor") => {
      const { data } = await apiClient.post<AuthResponse>("/auth/register", {
        name,
        email,
        password,
        role,
      });
      setAccessToken(data.access_token);
      setUser(data.user);
    },
    []
  );

  // logout — clear access token + user, and revoke the refresh cookie server-side
  const logout = useCallback(async () => {
    try {
      await apiClient.post("/auth/logout");
    } catch {
      // clear client state even if server call fails
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }, []);

  const value: AuthContextType = {
    user,
    isAuthenticated,
    loading,
    login,
    register,
    logout,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

// Custom hook — shortcut for consuming AuthContext
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used inside an <AuthProvider>");
  }
  return context;
};

export default AuthContext;
