/**
 * Student Invite Code & Family Management Page
 * Students can generate invite codes for parents and manage linked parents.
 */

import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Brain,
  ArrowLeft,
  Copy,
  Check,
  RefreshCw,
  Clock,
  Users,
  Trash2,
  Loader2,
  AlertCircle,
  KeyRound,
  ShieldCheck,
  UserPlus,
} from 'lucide-react';
import api from '../../lib/api';
import type {
  InviteCodeResponse,
  InviteCodeCreateResponse,
  LinkedParentResponse,
} from '../../lib/types';

export function StudentInviteCode() {
  // Invite code state
  const [inviteCode, setInviteCode] = useState<InviteCodeResponse | null>(null);
  const [isLoadingCode, setIsLoadingCode] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [copied, setCopied] = useState(false);

  // Linked parents state
  const [parents, setParents] = useState<LinkedParentResponse[]>([]);
  const [isLoadingParents, setIsLoadingParents] = useState(true);
  const [isRevoking, setIsRevoking] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);

  // Fetch active invite code
  const fetchInviteCode = useCallback(async () => {
    try {
      setIsLoadingCode(true);
      const { data } = await api.get<InviteCodeResponse | null>('/linking/invite-code');
      setInviteCode(data);
    } catch {
      // No active code
      setInviteCode(null);
    } finally {
      setIsLoadingCode(false);
    }
  }, []);

  // Fetch linked parents
  const fetchParents = useCallback(async () => {
    try {
      setIsLoadingParents(true);
      const { data } = await api.get<{ parents: LinkedParentResponse[] }>('/linking/parents');
      setParents(data.parents);
    } catch {
      setParents([]);
    } finally {
      setIsLoadingParents(false);
    }
  }, []);

  useEffect(() => {
    fetchInviteCode();
    fetchParents();
  }, [fetchInviteCode, fetchParents]);

  // Generate new invite code
  const handleGenerateCode = async () => {
    try {
      setIsGenerating(true);
      setError(null);
      const { data } = await api.post<InviteCodeCreateResponse>('/linking/invite-code');
      // Refresh to get full response
      await fetchInviteCode();
      setCopied(false);
    } catch {
      setError('Failed to generate invite code');
    } finally {
      setIsGenerating(false);
    }
  };

  // Regenerate (revoke + generate)
  const handleRegenerateCode = async () => {
    try {
      setIsGenerating(true);
      setError(null);
      await api.delete<InviteCodeCreateResponse>('/linking/invite-code');
      await fetchInviteCode();
      setCopied(false);
    } catch {
      setError('Failed to regenerate invite code');
    } finally {
      setIsGenerating(false);
    }
  };

  // Copy code to clipboard
  const handleCopy = async () => {
    if (!inviteCode) return;
    await navigator.clipboard.writeText(inviteCode.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Revoke parent link
  const handleRevokeParent = async (linkId: string) => {
    try {
      setIsRevoking(linkId);
      await api.delete(`/linking/parents/${linkId}`);
      setParents((prev) => prev.filter((p) => p.link_id !== linkId));
    } catch {
      setError('Failed to revoke parent access');
    } finally {
      setIsRevoking(null);
    }
  };

  // Calculate time remaining
  const getTimeRemaining = (expiresAt: string): string => {
    const now = new Date();
    const expires = new Date(expiresAt);
    const diff = expires.getTime() - now.getTime();

    if (diff <= 0) return 'Expired';

    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    if (hours > 0) return `${hours}h ${minutes}m remaining`;
    return `${minutes}m remaining`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-emerald-50">
      {/* Header */}
      <header className="border-b border-border bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              to="/student"
              className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="hidden sm:inline">Back to Dashboard</span>
            </Link>
          </div>
          <div className="flex items-center gap-2">
            <Brain className="w-6 h-6 text-primary" />
            <span className="font-semibold">MindBridge</span>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Page Title */}
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-3">
            <Users className="w-7 h-7 text-primary" />
            Family Connections
          </h1>
          <p className="text-muted-foreground mt-1">
            Link your parents or guardians to share wellness insights. Your conversations stay private.
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Invite Code Section */}
        <div className="bg-white rounded-2xl shadow-sm border border-border overflow-hidden">
          <div className="p-6 border-b border-border bg-gradient-to-r from-primary/5 to-secondary/5">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                <KeyRound className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">Parent Invite Code</h2>
                <p className="text-sm text-muted-foreground">
                  Share this code with a parent or guardian to link accounts
                </p>
              </div>
            </div>
          </div>

          <div className="p-6">
            {isLoadingCode ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : inviteCode ? (
              <div className="space-y-4">
                {/* Code Display */}
                <div className="flex items-center justify-center gap-4">
                  <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-dashed border-primary/30 rounded-2xl px-8 py-5">
                    <div className="text-3xl font-mono font-bold tracking-[0.3em] text-primary text-center">
                      {inviteCode.code}
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center justify-center gap-3">
                  <button
                    onClick={handleCopy}
                    className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition text-sm font-medium"
                  >
                    {copied ? (
                      <>
                        <Check className="w-4 h-4" />
                        Copied!
                      </>
                    ) : (
                      <>
                        <Copy className="w-4 h-4" />
                        Copy Code
                      </>
                    )}
                  </button>
                  <button
                    onClick={handleRegenerateCode}
                    disabled={isGenerating}
                    className="flex items-center gap-2 px-4 py-2 border border-border rounded-lg hover:bg-muted transition text-sm font-medium disabled:opacity-50"
                  >
                    {isGenerating ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <RefreshCw className="w-4 h-4" />
                    )}
                    Regenerate
                  </button>
                </div>

                {/* Expiry */}
                <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                  <Clock className="w-4 h-4" />
                  <span>{getTimeRemaining(inviteCode.expires_at)}</span>
                </div>
              </div>
            ) : (
              /* No active code */
              <div className="text-center py-8 space-y-4">
                <div className="w-16 h-16 mx-auto rounded-2xl bg-blue-50 flex items-center justify-center">
                  <UserPlus className="w-8 h-8 text-blue-400" />
                </div>
                <div>
                  <p className="font-medium text-foreground">No active invite code</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    Generate a code to share with your parent or guardian
                  </p>
                </div>
                <button
                  onClick={handleGenerateCode}
                  disabled={isGenerating}
                  className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-xl hover:bg-primary/90 transition font-medium disabled:opacity-50"
                >
                  {isGenerating ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <KeyRound className="w-4 h-4" />
                  )}
                  Generate Invite Code
                </button>
              </div>
            )}
          </div>
        </div>

        {/* How It Works */}
        <div className="bg-blue-50/50 rounded-2xl border border-blue-100 p-6">
          <h3 className="font-semibold text-blue-900 mb-4">How Parent Linking Works</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              {
                step: '1',
                title: 'Generate Code',
                desc: 'Click the button above to get a unique invite code',
              },
              {
                step: '2',
                title: 'Share with Parent',
                desc: 'Share the code with your parent or guardian',
              },
              {
                step: '3',
                title: 'Parent Signs Up',
                desc: 'Parent enters the code during signup to link accounts',
              },
            ].map((item) => (
              <div key={item.step} className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center shrink-0 text-sm">
                  {item.step}
                </div>
                <div>
                  <div className="font-medium text-blue-900 text-sm">{item.title}</div>
                  <div className="text-xs text-blue-700">{item.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Privacy Notice */}
        <div className="bg-emerald-50/50 rounded-2xl border border-emerald-100 p-4 flex items-start gap-3">
          <ShieldCheck className="w-5 h-5 text-emerald-600 mt-0.5 shrink-0" />
          <div>
            <p className="font-medium text-emerald-900 text-sm">Your Privacy is Protected</p>
            <p className="text-xs text-emerald-700 mt-1">
              Parents receive wellness insights and recommendations, but <strong>never</strong> see your
              actual conversations. You can revoke access at any time.
            </p>
          </div>
        </div>

        {/* Linked Parents Section */}
        <div className="bg-white rounded-2xl shadow-sm border border-border overflow-hidden">
          <div className="p-6 border-b border-border">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Users className="w-5 h-5 text-primary" />
              Linked Parents & Guardians
            </h2>
          </div>

          <div className="p-6">
            {isLoadingParents ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : parents.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Users className="w-10 h-10 mx-auto mb-3 opacity-30" />
                <p className="font-medium">No linked parents yet</p>
                <p className="text-sm mt-1">
                  Generate an invite code above and share it with your parent
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {parents.map((parent) => (
                  <div
                    key={parent.link_id}
                    className="flex items-center justify-between p-4 bg-muted/30 rounded-xl border border-border"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                        <span className="text-primary font-semibold text-sm">
                          {parent.first_name[0]}{parent.last_name[0]}
                        </span>
                      </div>
                      <div>
                        <div className="font-medium">
                          {parent.first_name} {parent.last_name}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {parent.email} • {parent.relationship || 'Parent'}
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => handleRevokeParent(parent.link_id)}
                      disabled={isRevoking === parent.link_id}
                      className="flex items-center gap-2 px-3 py-1.5 text-sm text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition disabled:opacity-50"
                    >
                      {isRevoking === parent.link_id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="w-3.5 h-3.5" />
                      )}
                      Revoke
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
