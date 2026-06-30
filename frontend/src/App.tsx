// frontend/src/App.tsx
import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/Login";
import RegisterPage from "./pages/Register";
import StudentDashboard from "./pages/StudentDashboard";
import ProfessorConsole from "./pages/ProfessorConsole";
import ProfessorSession from "./pages/ProfessorSession";
import ExamCreate from "./pages/ExamCreate";
import ExamShell from "./pages/ExamShell";
import StudentResults from "./pages/StudentResults";

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Protected — students only */}
          <Route element={<ProtectedRoute allowedRole="student" />}>
            <Route path="/student/dashboard" element={<StudentDashboard />} />
            <Route path="/student/exams/:id/results" element={<StudentResults />} />
            {/* ExamShell: consent gate always checked server-side on mount */}
            <Route path="/exam/:id" element={<ExamShell />} />
          </Route>

          {/* Protected — professors only */}
          <Route element={<ProtectedRoute allowedRole="professor" />}>
            <Route path="/professor/dashboard" element={<ProfessorConsole />} />
            <Route path="/professor/exams/new" element={<ExamCreate />} />
            <Route path="/professor/session/:sessionId" element={<ProfessorSession />} />
          </Route>

          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;