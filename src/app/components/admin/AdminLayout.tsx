/**
 * Platform Admin shell — sidebar navigation + header + content outlet.
 * Widget-based: each section is a page under src/app/components/admin/pages/,
 * so future modules (Billing, Feature Flags, …) slot in as new nav items.
 */

import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Cpu,
  FlaskConical,
  HeartHandshake,
  LayoutDashboard,
  LogOut,
  School,
  ScrollText,
  Settings,
  ShieldAlert,
  Users,
} from 'lucide-react';
import { useAuth } from '../../../lib/auth-context';
import { KioLogo } from '../KioLogo';
import { NotificationBell } from '../NotificationBell';
import { Button } from '../ui/button';
import { Separator } from '../ui/separator';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from '../ui/sidebar';
import { Toaster } from '../ui/sonner';

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  /** Exact-match route (index page). */
  end?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/admin', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/admin/schools', label: 'Schools', icon: School },
  { to: '/admin/users', label: 'Users', icon: Users },
  { to: '/admin/counselors', label: 'Counselors', icon: HeartHandshake },
  { to: '/admin/risk', label: 'Risk Center', icon: ShieldAlert },
  { to: '/admin/ai', label: 'AI Control', icon: Cpu },
  { to: '/admin/audit', label: 'Audit Logs', icon: ScrollText },
  { to: '/admin/settings', label: 'Settings', icon: Settings },
];

const TOOL_ITEMS: NavItem[] = [
  { to: '/admin/playground', label: 'AI Playground', icon: FlaskConical },
];

function currentSectionLabel(pathname: string): string {
  const all = [...NAV_ITEMS, ...TOOL_ITEMS];
  // Longest matching prefix wins so /admin/schools/:id maps to "Schools".
  const match = all
    .filter((item) => (item.end ? pathname === item.to : pathname.startsWith(item.to)))
    .sort((a, b) => b.to.length - a.to.length)[0];
  return match?.label ?? 'Dashboard';
}

export function AdminLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <SidebarProvider>
      <Sidebar collapsible="icon">
        <SidebarHeader>
          <div className="flex h-10 items-center px-2 group-data-[collapsible=icon]:justify-center">
            <KioLogo className="h-6 w-auto group-data-[collapsible=icon]:hidden" />
            <span className="hidden text-xs font-semibold text-sidebar-foreground group-data-[collapsible=icon]:block">
              K
            </span>
          </div>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Platform</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {NAV_ITEMS.map((item) => (
                  <SidebarMenuItem key={item.to}>
                    <NavLink to={item.to} end={item.end}>
                      {({ isActive }) => (
                        <SidebarMenuButton isActive={isActive} tooltip={item.label}>
                          <item.icon />
                          <span>{item.label}</span>
                        </SidebarMenuButton>
                      )}
                    </NavLink>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
          <SidebarGroup>
            <SidebarGroupLabel>Tools</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {TOOL_ITEMS.map((item) => (
                  <SidebarMenuItem key={item.to}>
                    <NavLink to={item.to}>
                      {({ isActive }) => (
                        <SidebarMenuButton isActive={isActive} tooltip={item.label}>
                          <item.icon />
                          <span>{item.label}</span>
                        </SidebarMenuButton>
                      )}
                    </NavLink>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter>
          <div className="flex items-center gap-2 px-2 py-1.5 group-data-[collapsible=icon]:justify-center">
            <div className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
              <p className="truncate text-xs font-medium text-sidebar-foreground">
                {user ? `${user.first_name} ${user.last_name}` : 'Platform Admin'}
              </p>
              <p className="truncate text-xs text-sidebar-foreground/60">{user?.email}</p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0 text-sidebar-foreground/70 hover:text-sidebar-foreground"
              onClick={handleLogout}
              title="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset>
        <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background/95 px-4 backdrop-blur">
          <SidebarTrigger />
          <Separator orientation="vertical" className="h-5" />
          <span className="text-sm font-medium">{currentSectionLabel(location.pathname)}</span>
          <div className="ml-auto">
            <NotificationBell />
          </div>
        </header>
        <main className="flex-1 space-y-6 p-4 md:p-6">
          <Outlet />
        </main>
      </SidebarInset>
      <Toaster position="top-right" richColors closeButton />
    </SidebarProvider>
  );
}
