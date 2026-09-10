/**
 * Kio Auth Context
 * Provides authentication state management across the entire app.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import api, { getRefreshToken, clearTokens, getAccessToken, setTokens } from './api';
import type {
  AuthResponse,
  GoogleAuthResponse,
  GoogleCompleteRequest,
  LoginRequest,
  SignupRequest,
  UserResponse,
} from './types';

// ── Context Types ─────────────────────────────────────────────────────

interface AuthState {
  user: UserResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (credentials: LoginRequest) => Promise<UserResponse>;
  signup: (payload: SignupRequest) => Promise<UserResponse>;
  /** Exchange a Google ID token. Returns either the logged-in user or a registration prompt. */
  loginWithGoogle: (idToken: string) => Promise<GoogleAuthResponse>;
  /** Finish a Google signup with mobile + institution code. */
  completeGoogleSignup: (payload: GoogleCompleteRequest) => Promise<UserResponse>;
  /** Re-fetch /auth/me. Used after out-of-band changes such as email verification. */
  refreshUser: () => Promise<UserResponse | null>;
  /** Revokes the refresh session server-side, then clears local credentials. */
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// ── Provider ──────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount, check for existing token and fetch user profile
  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      setIsLoading(false);
      return;
    }

    api
      .get<UserResponse>('/auth/me')
      .then((res) => {
        setUser(res.data);
      })
      .catch(() => {
        // Token is invalid or expired, clear it
        clearTokens();
        setUser(null);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  const login = useCallback(async (credentials: LoginRequest): Promise<UserResponse> => {
    const { data } = await api.post<AuthResponse>('/auth/login', credentials);
    setTokens(data.tokens.access_token, data.tokens.refresh_token);
    setUser(data.user);
    return data.user;
  }, []);

  const signup = useCallback(async (payload: SignupRequest): Promise<UserResponse> => {
    const { data } = await api.post<AuthResponse>('/auth/signup', payload);
    setTokens(data.tokens.access_token, data.tokens.refresh_token);
    setUser(data.user);
    return data.user;
  }, []);

  const loginWithGoogle = useCallback(async (idToken: string): Promise<GoogleAuthResponse> => {
    const { data } = await api.post<GoogleAuthResponse>('/auth/google', { id_token: idToken });
    if (data.status === 'authenticated' && data.tokens && data.user) {
      setTokens(data.tokens.access_token, data.tokens.refresh_token);
      setUser(data.user);
    }
    return data;
  }, []);

  const completeGoogleSignup = useCallback(
    async (payload: GoogleCompleteRequest): Promise<UserResponse> => {
      const { data } = await api.post<AuthResponse>('/auth/google/complete', payload);
      setTokens(data.tokens.access_token, data.tokens.refresh_token);
      setUser(data.user);
      return data.user;
    },
    []
  );

  const refreshUser = useCallback(async (): Promise<UserResponse | null> => {
    if (!getAccessToken()) return null;
    try {
      const { data } = await api.get<UserResponse>('/auth/me');
      setUser(data);
      return data;
    } catch {
      // Leave the current session untouched — a failed refresh isn't a logout.
      return null;
    }
  }, []);

  const logout = useCallback(async () => {
    // Tell the server first so the refresh session is actually revoked.
    // Clearing localStorage alone only removes this browser's copy: before
    // refresh sessions existed, a token captured from a shared school machine
    // kept minting new sessions for days after the student "logged out".
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      try {
        await api.post('/auth/logout', { refresh_token: refreshToken });
      } catch {
        // Best effort. A network failure must not trap someone in a session
        // they have asked to leave, and the local credentials still go.
      }
    }
    clearTokens();
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      signup,
      loginWithGoogle,
      completeGoogleSignup,
      refreshUser,
      logout,
    }),
    [user, isLoading, login, signup, loginWithGoogle, completeGoogleSignup, refreshUser, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ── Hook ──────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
