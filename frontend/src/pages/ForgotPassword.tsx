import React, { useState, FormEvent } from "react";
import { Link } from "react-router-dom";
import apiClient from "../api/client";

const ForgotPasswordPage: React.FC = () => {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      await apiClient.post("/auth/forgot-password", { email });
      setSubmitted(true);
    } catch {
      setError("Unable to reach the server. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

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
          <h2 className="text-lg font-semibold text-ink mb-2">
            Forgot password
          </h2>

          {submitted ? (
            <div className="space-y-4">
              <div className="px-4 py-3 rounded-md bg-accent-green-soft border-l-2 border-accent-green text-ink text-sm">
                If that email is registered, a reset link has been sent. Check
                your inbox.
              </div>
              <p className="text-center text-sm text-mute">
                <Link to="/login" className="text-link-teal font-medium">
                  Back to Sign in
                </Link>
              </p>
            </div>
          ) : (
            <>
              <p className="text-sm text-mute mb-6">
                Enter your registered email and we'll send you a link to reset
                your password.
              </p>

              {error && (
                <div className="mb-4 px-4 py-3 rounded-md bg-accent-red-soft border-l-2 border-accent-red text-ink text-sm">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label
                    htmlFor="email"
                    className="block text-sm font-medium text-body mb-1.5"
                  >
                    Email address
                  </label>
                  <input
                    id="email"
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@ucd.ie"
                    className="w-full px-3 py-2 bg-surface-card border border-hairline rounded-md text-ink placeholder-ash text-sm focus:outline-none focus:border-accent-blue focus:ring-2 focus:ring-accent-blue/30 transition"
                  />
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full py-2.5 px-4 bg-primary disabled:bg-surface-soft disabled:text-ash text-ink text-sm font-bold rounded-md transition-colors"
                >
                  {isLoading ? "Sending…" : "Send reset link"}
                </button>
              </form>

              <p className="mt-6 text-center text-sm text-mute">
                Remembered it?{" "}
                <Link to="/login" className="text-link-teal font-medium">
                  Sign in
                </Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ForgotPasswordPage;
