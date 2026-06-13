// frontend/src/context/AuthContext.tsx
// Auth context — provides user state and login/logout to the entire app

import React, { createContext, useContext, useState, useCallback, ReactNode } from "react";
import apiClient, { setAccessToken } from "../api/client";

// Types
export interface User {
  id: string;
  email: string;
  role: "student" | "professor";
  name: string;
}

interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string, role: "student" | "professor") => Promise<void>;
  logout: () => Promise<void>;
}

// Context — undefined default forces usage within AuthProvider
const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

// Provider — wraps the app and broadcasts auth state
export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const isAuthenticated = user !== null;

  // login — POST credentials, store token and user
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

  // logout — clear token, user, and server cookie
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

  // Broadcast auth state to all child components
  const value: AuthContextType = {
    user,
    isAuthenticated,
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