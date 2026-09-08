/**
 * Counselor detail — profile, directory listing, and account state.
 *
 * There is no GET /admin/counselors/{id}; the list endpoint returns the whole
 * platform roster (it is small by construction) and this page selects from it.
 * Worth knowing if the roster ever grows enough to need pagination — at that
 * point this needs a real detail endpoint rather than a client-side find.
 */

import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, HeartHandshake, Loader2 } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import {
  apiErrorDetail,
  listCounselors,
  updateCounselor,
} from '../../../../lib/admin-api';
import type { CounselorAdmin } from '../../../../lib/admin-types';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import { Switch } from '../../ui/switch';
import { Textarea } from '../../ui/textarea';
import { ConfirmActionDialog } from '../widgets/ConfirmActionDialog';
import { EmptyState } from '../widgets/EmptyState';
import { PageHeader } from '../widgets/PageHeader';
import { StatusBadge } from '../widgets/StatusBadge';

/** Comma-separated input <-> string[] on the API. */
function parseList(value: string): string[] {
  return value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

export function CounselorDetailPage() {
  const { counselorId } = useParams<{ counselorId: string }>();

  const [counselor, setCounselor] = useState<CounselorAdmin | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [qualification, setQualification] = useState('');
  const [bio, setBio] = useState('');
  const [experience, setExperience] = useState('');
  const [specializations, setSpecializations] = useState('');
  const [languages, setLanguages] = useState('');

  const [deactivateOpen, setDeactivateOpen] = useState(false);

  const hydrate = useCallback((row: CounselorAdmin) => {
    setCounselor(row);
    setQualification(row.qualification ?? '');
    setBio(row.bio ?? '');
    setExperience(row.experience_years?.toString() ?? '');
    setSpecializations(row.specializations.join(', '));
    setLanguages(row.languages.join(', '));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listCounselors();
      const found = data.counselors.find((c) => c.counselor_id === counselorId);
      if (found) hydrate(found);
      else setCounselor(null);
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Could not load counselor.'));
    } finally {
      setLoading(false);
    }
  }, [counselorId, hydrate]);

  useEffect(() => {
    load();
  }, [load]);

  const patch = async (
    payload: Parameters<typeof updateCounselor>[1],
    successMessage: string,
  ) => {
    if (!counselorId) return;
    setSaving(true);
    try {
      hydrate(await updateCounselor(counselorId, payload));
      toast.success(successMessage);
    } catch (err) {
      toast.error(apiErrorDetail(err, 'Could not save changes.'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        <Loader2 className="mr-3 h-5 w-5 animate-spin" />
        Loading counselor…
      </div>
    );
  }

  if (!counselor) {
    return (
      <>
        <PageHeader title="Counselor" />
        <EmptyState
          icon={HeartHandshake}
          title="Counselor not found"
          description="This counselor may have been removed."
          action={
            <Button asChild variant="outline">
              <Link to="/admin/counselors">Back to counselors</Link>
            </Button>
          }
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={counselor.name}
        description={counselor.email}
        actions={
          <Button asChild variant="outline">
            <Link to="/admin/counselors">
              <ArrowLeft className="h-4 w-4" />
              Counselors
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Profile */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Profile</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="qualification">Qualification</Label>
                <Input
                  id="qualification"
                  value={qualification}
                  onChange={(e) => setQualification(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="experience">Experience (years)</Label>
                <Input
                  id="experience"
                  type="number"
                  min={0}
                  value={experience}
                  onChange={(e) => setExperience(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="specializations">Specializations</Label>
              <Input
                id="specializations"
                value={specializations}
                onChange={(e) => setSpecializations(e.target.value)}
                placeholder="Anxiety, Academic stress, Family conflict"
              />
              <p className="text-xs text-muted-foreground">Comma separated.</p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="languages">Languages</Label>
              <Input
                id="languages"
                value={languages}
                onChange={(e) => setLanguages(e.target.value)}
                placeholder="English, Hindi, Marathi"
              />
              <p className="text-xs text-muted-foreground">Comma separated.</p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="bio">Bio</Label>
              <Textarea
                id="bio"
                rows={4}
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                placeholder="Shown to students and parents in the booking directory."
              />
            </div>

            <Button
              disabled={saving}
              onClick={() =>
                patch(
                  {
                    qualification: qualification.trim(),
                    bio: bio.trim(),
                    specializations: parseList(specializations),
                    languages: parseList(languages),
                    ...(experience ? { experience_years: Number(experience) } : {}),
                  },
                  'Profile saved.',
                )
              }
            >
              {saving ? 'Saving…' : 'Save profile'}
            </Button>
          </CardContent>
        </Card>

        {/* Status controls */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <Label htmlFor="verified">Directory listing</Label>
                  <StatusBadge
                    status={counselor.is_verified ? 'verified' : 'unverified'}
                  />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Verified counselors are bookable by any student or parent on the
                  platform.
                </p>
              </div>
              <Switch
                id="verified"
                checked={counselor.is_verified}
                disabled={saving}
                onCheckedChange={(checked) =>
                  patch(
                    { is_verified: checked },
                    checked
                      ? 'Verified and listed in the directory.'
                      : 'Verification withdrawn.',
                  )
                }
              />
            </div>

            <div className="flex items-start justify-between gap-4">
              <div>
                <Label htmlFor="available">Accepting bookings</Label>
                <p className="mt-1 text-xs text-muted-foreground">
                  Temporarily hide availability without withdrawing verification.
                </p>
              </div>
              <Switch
                id="available"
                checked={counselor.is_available}
                disabled={saving || !counselor.is_verified}
                onCheckedChange={(checked) =>
                  patch(
                    { is_available: checked },
                    checked ? 'Now accepting bookings.' : 'Bookings paused.',
                  )
                }
              />
            </div>

            <div className="border-t pt-4">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">Account</span>
                <StatusBadge status={counselor.is_active ? 'active' : 'inactive'} />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Deactivating blocks sign-in entirely.
              </p>
              <Button
                variant={counselor.is_active ? 'destructive' : 'default'}
                size="sm"
                className="mt-3"
                disabled={saving}
                onClick={() => setDeactivateOpen(true)}
              >
                {counselor.is_active ? 'Deactivate account' : 'Reactivate account'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <ConfirmActionDialog
        open={deactivateOpen}
        onOpenChange={setDeactivateOpen}
        title={counselor.is_active ? 'Deactivate this counselor?' : 'Reactivate this counselor?'}
        description={
          counselor.is_active
            ? `${counselor.name} will be unable to sign in. Scheduled sessions are not cancelled automatically — reassign them first.`
            : `${counselor.name} will be able to sign in again.`
        }
        confirmLabel={counselor.is_active ? 'Deactivate' : 'Reactivate'}
        destructive={counselor.is_active}
        onConfirm={() =>
          patch(
            { is_active: !counselor.is_active },
            counselor.is_active ? 'Account deactivated.' : 'Account reactivated.',
          )
        }
      />
    </>
  );
}
