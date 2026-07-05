import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from '../lib/auth-context';
import { ProtectedRoute } from '../lib/protected-route';
import { LandingPage } from './components/LandingPage';
import { StudentDashboard } from './components/StudentDashboard';
import { ParentDashboard } from './components/ParentDashboard';
import { CounselorDashboard } from './components/CounselorDashboard';
import { SchoolAdminDashboard } from './components/SchoolAdminDashboard';
import { BookCounselor } from './components/BookCounselor';
import { LoginSignup } from './components/LoginSignup';
import { StudentInviteCode } from './components/StudentInviteCode';
import { StudentGrowthProfile } from './components/StudentGrowthProfile';
import { AdminPlayground } from './components/AdminPlayground';
import { PlatformAdminDashboard } from './components/PlatformAdminDashboard';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginSignup />} />

          {/* Protected routes — require authentication */}
          <Route
            path="/student"
            element={
              <ProtectedRoute roles={['student']}>
                <StudentDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/parent"
            element={
              <ProtectedRoute roles={['parent']}>
                <ParentDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/counselor"
            element={
              <ProtectedRoute roles={['counselor']}>
                <CounselorDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/school"
            element={
              <ProtectedRoute roles={['school_admin']}>
                <SchoolAdminDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/book-counselor"
            element={
              <ProtectedRoute roles={['student']}>
                <BookCounselor />
              </ProtectedRoute>
            }
          />
          <Route
            path="/student/family"
            element={
              <ProtectedRoute roles={['student']}>
                <StudentInviteCode />
              </ProtectedRoute>
            }
          />
          <Route
            path="/student/growth"
            element={
              <ProtectedRoute roles={['student']}>
                <StudentGrowthProfile />
              </ProtectedRoute>
            }
          />

          <Route
            path="/admin"
            element={
              <ProtectedRoute roles={['admin']}>
                <PlatformAdminDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/playground"
            element={
              <ProtectedRoute roles={['admin']}>
                <AdminPlayground />
              </ProtectedRoute>
            }
          />

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}