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
import { VerifyEmail } from './components/VerifyEmail';
import { ForgotPassword } from './components/ForgotPassword';
import { ResetPassword } from './components/ResetPassword';
import { GuardianConsent } from './components/GuardianConsent';
import { TermsOfService } from './components/legal/TermsOfService';
import { PrivacyPolicy } from './components/legal/PrivacyPolicy';
import { StudentInviteCode } from './components/StudentInviteCode';
import { StudentGrowthProfile } from './components/StudentGrowthProfile';
import { StudentActivities } from './components/StudentActivities';
import { StudentProfile } from './components/StudentProfile';
import { AdminPlayground } from './components/AdminPlayground';
import { AdminLayout } from './components/admin/AdminLayout';
import { DashboardPage } from './components/admin/pages/DashboardPage';
import { SchoolsPage } from './components/admin/pages/SchoolsPage';
import { SchoolDetailPage } from './components/admin/pages/SchoolDetailPage';
import { UsersPage } from './components/admin/pages/UsersPage';
import { CounselorsPage } from './components/admin/pages/CounselorsPage';
import { CounselorDetailPage } from './components/admin/pages/CounselorDetailPage';
import { RiskCenterPage } from './components/admin/pages/RiskCenterPage';
import { RiskDetailPage } from './components/admin/pages/RiskDetailPage';
import { AIControlPage } from './components/admin/pages/AIControlPage';
import { AuditLogsPage } from './components/admin/pages/AuditLogsPage';
import { SettingsPage } from './components/admin/pages/SettingsPage';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginSignup />} />

          {/* Policies — public, because signup links to them before an
              account exists and a guardian reads them with no account at all. */}
          <Route path="/terms" element={<TermsOfService />} />
          <Route path="/privacy" element={<PrivacyPolicy />} />

          {/* Emailed one-time links — reachable signed in or out */}
          <Route path="/verify-email" element={<VerifyEmail />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          {/* Guardian approval: the visitor is a parent with no Kio account,
              authorised by the signed token in the link. */}
          <Route path="/guardian-consent" element={<GuardianConsent />} />

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
              <ProtectedRoute roles={['student', 'parent']}>
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
            path="/student/activities"
            element={
              <ProtectedRoute roles={['student']}>
                <StudentActivities />
              </ProtectedRoute>
            }
          />
          <Route
            path="/student/profile"
            element={
              <ProtectedRoute roles={['student']}>
                <StudentProfile />
              </ProtectedRoute>
            }
          />

          {/* Platform Admin — sidebar shell with nested module pages */}
          <Route
            path="/admin"
            element={
              <ProtectedRoute roles={['admin']}>
                <AdminLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="schools" element={<SchoolsPage />} />
            <Route path="schools/:tenantId" element={<SchoolDetailPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="counselors" element={<CounselorsPage />} />
            <Route path="counselors/:counselorId" element={<CounselorDetailPage />} />
            <Route path="risk" element={<RiskCenterPage />} />
            <Route path="risk/:riskId" element={<RiskDetailPage />} />
            <Route path="ai" element={<AIControlPage />} />
            <Route path="playground" element={<AdminPlayground />} />
            <Route path="audit" element={<AuditLogsPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}