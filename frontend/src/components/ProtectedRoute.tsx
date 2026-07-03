// frontend/src/components/ProtectedRoute.tsx
import React from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

interface ProtectedRouteProps {
  allowedRole?: "student" | "professor";
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ allowedRole }) => {
  const { isAuthenticated, user, loading } = useAuth();

  // While the session is being restored from the refresh cookie, don't redirect
  // yet — otherwise a page refresh briefly bounces the user to /login.
  if (loading) {
    return null;
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Redirect to own dashboard if wrong role
  if (allowedRole && user?.role !== allowedRole) {
    if (user?.role === "student") {
      return <Navigate to="/student/dashboard" replace />;
    }
    return <Navigate to="/professor/dashboard" replace />;
  }

  return <Outlet />;
};

export default ProtectedRoute;