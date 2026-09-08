/**
 * Student profile — /student/profile
 *
 * Age and gender live on student_profiles, not the user row, but PUT /users/me
 * accepts them together so the whole profile saves in one call. Age matters
 * because it shapes how Comrade pitches its responses and how wellness signals
 * are read, so an empty age is surfaced as a prompt rather than left blank.
 */

import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Check, Loader2, Mail, Phone, User as UserIcon } from 'lucide-react';
import { KioLogo } from './KioLogo';
import { Disclaimer } from './Disclaimer';
import api from '../../lib/api';
import { authErrorMessage } from '../../lib/auth-api';
import { useAuth } from '../../lib/auth-context';
import type { UserProfileResponse } from '../../lib/types';

const GENDER_OPTIONS = ['Female', 'Male', 'Non-binary', 'Prefer not to say'];

export function StudentProfile() {
  const { refreshUser } = useAuth();

  const [profile, setProfile] = useState<UserProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [phone, setPhone] = useState('');
  const [age, setAge] = useState('');
  const [gender, setGender] = useState('');

  const load = useCallback(async () => {
    try {
      const { data } = await api.get<UserProfileResponse>('/users/me');
      setProfile(data);
      setFirstName(data.first_name);
      setLastName(data.last_name);
      setPhone(data.phone ?? '');
      setAge(data.student_profile?.age != null ? String(data.student_profile.age) : '');
      setGender(data.student_profile?.gender ?? '');
    } catch {
      setError('Could not load your profile.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaved(false);

    const parsedAge = age.trim() === '' ? null : Number(age);
    if (parsedAge !== null && (!Number.isInteger(parsedAge) || parsedAge < 5 || parsedAge > 25)) {
      setError('Enter an age between 5 and 25.');
      return;
    }

    setSaving(true);
    try {
      const { data } = await api.put<UserProfileResponse>('/users/me', {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        phone: phone.trim() || null,
        age: parsedAge,
        gender: gender || null,
      });
      setProfile(data);
      setSaved(true);
      await refreshUser();
    } catch (err) {
      setError(authErrorMessage(err, 'Could not save your profile. Please try again.'));
    } finally {
      setSaving(false);
    }
  };

  const missingAge = profile != null && profile.student_profile?.age == null;

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 bg-card border-b border-border">
        <div className="max-w-3xl mx-auto px-4 h-16 flex items-center gap-4">
          <Link
            to="/student"
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition"
          >
            <ArrowLeft className="w-5 h-5" />
            <span className="hidden sm:inline">Back to Dashboard</span>
          </Link>
          <div className="hidden sm:block w-px h-6 bg-border" />
          <KioLogo className="h-7 w-auto" />
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-foreground mb-1">My Profile</h1>
        <p className="text-muted-foreground mb-6">
          Keep this up to date — Comrade uses it to tailor how it talks with you.
        </p>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <form onSubmit={save} className="bg-card border border-border rounded-2xl p-6 space-y-5">
            {missingAge && !saved && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-900">
                Your age isn't set yet. Adding it helps Comrade respond in a way that fits you.
              </div>
            )}

            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium mb-2 block">First name</label>
                <div className="relative">
                  <UserIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                  <input
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    className="w-full pl-11 pr-4 py-3 border border-border rounded-xl bg-input-background focus:outline-none focus:ring-2 focus:ring-ring"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">Last name</label>
                <input
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  className="w-full px-4 py-3 border border-border rounded-xl bg-input-background focus:outline-none focus:ring-2 focus:ring-ring"
                  required
                />
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Age</label>
                <input
                  type="number"
                  min={5}
                  max={25}
                  value={age}
                  onChange={(e) => setAge(e.target.value)}
                  placeholder="e.g. 16"
                  className="w-full px-4 py-3 border border-border rounded-xl bg-input-background focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">Gender</label>
                <select
                  value={gender}
                  onChange={(e) => setGender(e.target.value)}
                  className="w-full px-4 py-3 border border-border rounded-xl bg-input-background focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="">Prefer not to answer</option>
                  {GENDER_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">Mobile number</label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+91 98765 43210"
                  className="w-full pl-11 pr-4 py-3 border border-border rounded-xl bg-input-background focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <input
                  value={profile?.email ?? ''}
                  disabled
                  className="w-full pl-11 pr-4 py-3 border border-border rounded-xl bg-muted text-muted-foreground"
                />
              </div>
              <p className="mt-1.5 text-xs text-muted-foreground">
                Your email is your sign-in identity and can't be changed here.
              </p>
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}
            {saved && (
              <p className="flex items-center gap-2 text-sm text-emerald-600">
                <Check className="w-4 h-4" /> Profile saved.
              </p>
            )}

            <button
              type="submit"
              disabled={saving}
              className="w-full py-3 rounded-xl bg-primary text-primary-foreground font-medium hover:opacity-90 transition disabled:opacity-60 flex items-center justify-center gap-2"
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              Save changes
            </button>
          </form>
        )}

        <Disclaimer variant="short" className="mt-6" />
      </div>
    </div>
  );
}
