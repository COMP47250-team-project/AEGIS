// frontend/src/pages/ProfessorConsole.tsx
// Placeholder — full implementation in Sprint 3
import React from "react";
import { useAuth } from "../context/AuthContext";

const ProfessorConsole: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-indigo-600 mb-4">
          <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </div>
        <h1 className="text-2xl font-semibold text-slate-800 mb-2">Professor Console</h1>
        <p className="text-slate-500 text-sm mb-1">
          Welcome, <span className="text-slate-800 font-medium">{user?.name}</span>
        </p>
        <p className="text-slate-400 text-xs mb-8">
          Exam authoring and live cohort view coming soon — implemented in Sprint 3.
        </p>
        <button
          onClick={logout}
          className="px-4 py-2 bg-white hover:bg-slate-50 text-slate-600 text-sm rounded-lg transition-colors border border-slate-300"
        >
          Sign out
        </button>
      </div>
    </div>
  );
};

export default ProfessorConsole;