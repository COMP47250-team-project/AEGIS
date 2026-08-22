import React, { useState, FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import apiClient from "../api/client";

const ResetPasswordPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const validate = (): string | null => {
    if (newPassword.length < 8)
      return "Password must be at least 8 characters.";
    if (newPassword !== confirmPassword) return "Passwords do not match.";
    return null;
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }
    setIsLoading(true);
    try {
      await apiClient.post("/auth/reset-password", {
        token,
        new_password: newPassword,
      });
      navigate("/login", {
        state: { successMessage: "Password updated. Please sign in." },
        replace: true,
      });
    } catch (err: unknown) {
      if (
        err &&
        typeof err === "object" &&
        "response" in err &&
        err.response &&
        typeof err.response === "object" &&
        "data" in err.response
      ) {
        const data = (err.response as { data?: { detail?: string } }).data;
        setError(
          data?.detail ??
            "Unable to reset password. Please request a new link.",
        );
      } else {
        setError("Unable to reach the server. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen bg-canvas flex items-center justify-center px-4">
        <div className="w-full max-w-md bg-surface-card border border-hairline rounded-md p-10 text-center space-y-4">
          <p className="text-ink text-sm">
            This reset link is missing or malformed.
          </p>
          <Link
            to="/forgot-password"
            className="text-link-teal font-medium text-sm"
          >
            Request a new one
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-canvas flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-lg bg-surface-dark mb-4">
            <svg
              className="w-7 h-7 text-on-dark"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-ink tracking-tight">AEGIS</h1>
          <p className="text-mute text-sm mt-1">
            Adaptive Exam Guardian and Integrity System
          </p>
        </div>

        <div className="bg-surface-card border border-hairline rounded-md p-10">
          <h2 className="text-lg font-semibold text-ink mb-6">
            Set a new password
          </h2>

          {error && (
            <div className="mb-4 px-4 py-3 rounded-md bg-accent-red-soft border-l-2 border-accent-red text-ink text-sm">
              {error}{" "}
              {error.includes("invalid or has expired") && (
                <Link
                  to="/forgot-password"
                  className="underline text-link-teal"
                >
                  Request a new link
                </Link>
              )}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label
                htmlFor="new-password"
                className="block text-sm font-medium text-body mb-1.5"
              >
                New password
              </label>
              <input
                id="new-password"
                type="password"
                autoComplete="new-password"
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Min. 8 characters"
                className="w-full px-3 py-2 bg-surface-card border border-hairline rounded-md text-ink placeholder-ash text-sm focus:outline-none focus:border-accent-blue focus:ring-2 focus:ring-accent-blue/30 transition"
              />
            </div>

            <div>
              <label
                htmlFor="confirm-password"
                className="block text-sm font-medium text-body mb-1.5"
              >
                Confirm new password
              </label>
              <input
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full px-3 py-2 bg-surface-card border border-hairline rounded-md text-ink placeholder-ash text-sm focus:outline-none focus:border-accent-blue focus:ring-2 focus:ring-accent-blue/30 transition"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 px-4 bg-primary disabled:bg-surface-soft disabled:text-ash text-ink text-sm font-bold rounded-md transition-colors"
            >
              {isLoading ? "Updating…" : "Update password"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-mute">
            <Link to="/login" className="text-link-teal font-medium">
              Back to Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default ResetPasswordPage;
