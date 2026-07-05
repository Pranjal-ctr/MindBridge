import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Brain, ArrowLeft, Mail, Lock, User, School, Loader2, AlertCircle, Phone, KeyRound } from 'lucide-react';
import { useState } from 'react';
import { useAuth } from '../../lib/auth-context';
import { getDashboardRoute } from '../../lib/protected-route';
import type { AxiosError } from 'axios';
import type { ApiError } from '../../lib/types';

export function LoginSignup() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, signup } = useAuth();

  const [isSignup, setIsSignup] = useState(false);
  const [userType, setUserType] = useState<'student' | 'parent' | 'counselor' | 'school_admin'>('student');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [schoolCode, setSchoolCode] = useState('');
  const [phone, setPhone] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // School code is required for student, parent, school_admin — not counselor
  const showSchoolCode = userType !== 'counselor';
  // Invite code shown only for parent signup
  const showInviteCode = isSignup && userType === 'parent';

  // Get redirect path from location state (set by ProtectedRoute)
  const from = (location.state as { from?: string })?.from;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      let user;

      if (isSignup) {
        user = await signup({
          email,
          password,
          first_name: firstName,
          last_name: lastName,
          role: userType,
          phone,
          school_code: showSchoolCode ? schoolCode || null : null,
          invite_code: showInviteCode ? inviteCode || null : null,
        });
      } else {
        user = await login({ email, password });
      }

      // Navigate to the saved redirect path, or the user's dashboard
      const destination = from || getDashboardRoute(user.role);
      navigate(destination, { replace: true });
    } catch (err: unknown) {
      const axiosError = err as AxiosError<ApiError>;
      const detail = axiosError.response?.data?.detail;

      if (typeof detail === 'string') {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(detail.map((d) => d.msg).join(', '));
      } else if (axiosError.message) {
        setError(axiosError.code === 'ERR_NETWORK'
          ? 'Unable to connect to server. Please try again.'
          : axiosError.message
        );
      } else {
        setError('Something went wrong. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const toggleMode = () => {
    setIsSignup(!isSignup);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-emerald-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Back to Home */}
        <Link to="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition mb-8">
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Home</span>
        </Link>

        {/* Login Card */}
        <div className="bg-white rounded-2xl shadow-xl border border-border overflow-hidden">
          {/* Header */}
          <div className="bg-gradient-to-r from-primary to-secondary p-8 text-white">
            <div className="flex items-center gap-3 mb-4">
              <Brain className="w-10 h-10" />
              <span className="text-2xl font-bold">MindBridge</span>
            </div>
            <h1 className="text-2xl font-semibold mb-2">
              {isSignup ? 'Create Account' : 'Welcome Back'}
            </h1>
            <p className="text-blue-100">
              {isSignup ? 'Join our wellness community' : 'Sign in to continue to your dashboard'}
            </p>
          </div>

          {/* Form */}
          <div className="p-8">
            {/* Error Message */}
            {error && (
              <div className="mb-4 flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
                <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* User Type Selection */}
            <div className="mb-6">
              <label className="text-sm font-medium text-foreground mb-3 block">I am a...</label>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { type: 'student' as const, icon: User, label: 'Student' },
                  { type: 'parent' as const, icon: User, label: 'Parent' },
                  { type: 'counselor' as const, icon: User, label: 'Counselor' },
                  { type: 'school_admin' as const, icon: School, label: 'School Admin' }
                ].map((option) => (
                  <button
                    key={option.type}
                    type="button"
                    onClick={() => setUserType(option.type)}
                    className={`flex items-center gap-2 px-4 py-3 border-2 rounded-xl transition ${
                      userType === option.type
                        ? 'border-primary bg-blue-50 text-primary'
                        : 'border-border bg-card text-muted-foreground hover:border-primary/50'
                    }`}
                  >
                    <option.icon className="w-4 h-4" />
                    <span className="text-sm font-medium">{option.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {isSignup && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-medium text-foreground mb-2 block">First Name</label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                      <input
                        type="text"
                        value={firstName}
                        onChange={(e) => setFirstName(e.target.value)}
                        placeholder="First name"
                        className="w-full pl-11 pr-4 py-3 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-ring bg-input-background"
                        required
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-foreground mb-2 block">Last Name</label>
                    <input
                      type="text"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      placeholder="Last name"
                      className="w-full px-4 py-3 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-ring bg-input-background"
                      required
                    />
                  </div>
                </div>
              )}

              {isSignup && showSchoolCode && (
                <div>
                  <label className="text-sm font-medium text-foreground mb-2 block">School Code</label>
                  <div className="relative">
                    <School className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <input
                      type="text"
                      value={schoolCode}
                      onChange={(e) => setSchoolCode(e.target.value)}
                      placeholder="Enter school code (e.g. RHS2026)"
                      className="w-full pl-11 pr-4 py-3 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-ring bg-input-background"
                      required
                    />
                  </div>
                </div>
              )}

              {isSignup && (
                <div>
                  <label className="text-sm font-medium text-foreground mb-2 block">Phone Number</label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <input
                      type="tel"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="Enter your phone number"
                      className="w-full pl-11 pr-4 py-3 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-ring bg-input-background"
                      required
                    />
                  </div>
                </div>
              )}

              {showInviteCode && (
                <div>
                  <label className="text-sm font-medium text-foreground mb-2 block">Parent Invite Code</label>
                  <div className="relative">
                    <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <input
                      type="text"
                      value={inviteCode}
                      onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                      placeholder="Enter code from your child (e.g. MB-X7K9)"
                      className="w-full pl-11 pr-4 py-3 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-ring bg-input-background uppercase tracking-wider"
                    />
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Ask your child to generate an invite code from their dashboard. You can also link later.
                  </p>
                </div>
              )}

              <div>
                <label className="text-sm font-medium text-foreground mb-2 block">Email</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Enter your email"
                    className="w-full pl-11 pr-4 py-3 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-ring bg-input-background"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-foreground mb-2 block">Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={isSignup ? 'Min 8 characters' : 'Enter your password'}
                    className="w-full pl-11 pr-4 py-3 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-ring bg-input-background"
                    required
                    minLength={isSignup ? 8 : undefined}
                  />
                </div>
              </div>

              {!isSignup && (
                <div className="flex items-center justify-between text-sm">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" className="w-4 h-4 rounded border-border" />
                    <span className="text-muted-foreground">Remember me</span>
                  </label>
                  <a href="#" className="text-primary hover:underline">
                    Forgot password?
                  </a>
                </div>
              )}

              {isSignup && (
                <div className="flex items-start gap-2 text-sm">
                  <input type="checkbox" className="w-4 h-4 mt-1 rounded border-border" required />
                  <span className="text-muted-foreground">
                    I agree to the{' '}
                    <a href="#" className="text-primary hover:underline">Terms of Service</a>
                    {' '}and{' '}
                    <a href="#" className="text-primary hover:underline">Privacy Policy</a>
                  </span>
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-3 bg-primary text-primary-foreground rounded-xl font-medium hover:bg-primary/90 transition shadow-lg disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                {isLoading
                  ? (isSignup ? 'Creating Account...' : 'Signing In...')
                  : (isSignup ? 'Create Account' : 'Sign In')
                }
              </button>
            </form>

            {/* Toggle Sign Up / Sign In */}
            <div className="mt-6 text-center">
              <button
                onClick={toggleMode}
                className="text-sm text-muted-foreground"
              >
                {isSignup ? 'Already have an account? ' : "Don't have an account? "}
                <span className="text-primary font-medium hover:underline">
                  {isSignup ? 'Sign In' : 'Sign Up'}
                </span>
              </button>
            </div>

            {/* Divider */}
            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-border"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-muted-foreground">Or continue with</span>
              </div>
            </div>

            {/* Social Login */}
            <div className="grid grid-cols-2 gap-3">
              <button className="px-4 py-3 border border-border rounded-xl hover:bg-muted transition flex items-center justify-center gap-2">
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                <span className="text-sm font-medium">Google</span>
              </button>
              <button className="px-4 py-3 border border-border rounded-xl hover:bg-muted transition flex items-center justify-center gap-2">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09zM15.53 3.83c.843-1.012 1.4-2.427 1.245-3.83-1.207.052-2.662.805-3.532 1.818-.78.896-1.454 2.338-1.273 3.714 1.338.104 2.715-.688 3.559-1.701"/>
                </svg>
                <span className="text-sm font-medium">Apple</span>
              </button>
            </div>
          </div>

          {/* Privacy Notice */}
          {userType === 'student' && (
            <div className="bg-blue-50 border-t border-blue-200 p-4 text-center">
              <p className="text-xs text-blue-700">
                Your conversations are private and encrypted. Parents receive insights, not raw chats.
              </p>
            </div>
          )}
        </div>

        {/* Help Text */}
        <div className="mt-6 text-center text-sm text-muted-foreground">
          Need help?{' '}
          <a href="#" className="text-primary hover:underline">
            Contact Support
          </a>
        </div>
      </div>
    </div>
  );
}
