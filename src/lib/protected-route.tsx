/**
 * Kio Protected Route
 * Route guard that checks authentication and optional role requirements.
 */

import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './auth-context';

interface ProtectedRouteProps {
  children: React.ReactNode;
  /** If provided, user must have one of these roles to access */
  roles?: string[];
}

export function ProtectedRoute({ children, roles }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  // Show nothing while checking auth state on mount
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-muted-foreground text-sm">Loading...</p>
        </div>
      </div>
    );
  }

  // Not authenticated → redirect to login (save current path for redirect back)
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  // Role check: if roles specified and user's role doesn't match
  if (roles && user && !roles.includes(user.role)) {
    // Redirect to the user's own dashboard instead
    const dashboardRoute = getDashboardRoute(user.role);
    return <Navigate to={dashboardRoute} replace />;
  }

  return <>{children}</>;
}

/** Maps backend role strings to their frontend dashboard routes */
export function getDashboardRoute(role: string): string {
  const routes: Record<string, string> = {
    student: '/student',
    parent: '/parent',
    counselor: '/counselor',
    school_admin: '/school',
    admin: '/admin',
  };
  return routes[role] || '/student';
}
