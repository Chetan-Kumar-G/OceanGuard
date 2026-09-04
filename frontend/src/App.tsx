import { Navigate, Route, Routes } from "react-router-dom";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import AppealPage from "./pages/AppealPage";
import AppealsReviewPage from "./pages/AppealsReviewPage";
import ProtectedRoute from "./auth/ProtectedRoute";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/appeal" element={<AppealPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      {/* NOT "/appeals" - that path is proxied straight to the backend's
          GET /appeals API (see vite.config.ts), so a full-page navigation
          there (typed URL, refresh, this tool's `navigate`) would hit the
          JSON API instead of this page. */}
      <Route
        path="/review"
        element={
          <ProtectedRoute>
            <AppealsReviewPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
