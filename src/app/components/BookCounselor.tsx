import { Link } from 'react-router-dom';
import { ArrowLeft, Star, Calendar, Check, Loader2, Globe, GraduationCap, Award, Clock } from 'lucide-react';
import { KioLogo } from './KioLogo';
import { useState, useEffect, useCallback } from 'react';
import api from '../../lib/api';
import type {
  AvailabilitySlot,
  CounselorDirectoryItem,
  CounselorDirectoryResponse,
  BookResponse,
} from '../../lib/types';

export function BookCounselor() {
  const [counselors, setCounselors] = useState<CounselorDirectoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCounselor, setSelectedCounselor] = useState<string | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<AvailabilitySlot | null>(null);
  const [booking, setBooking] = useState(false);
  const [confirmation, setConfirmation] = useState<BookResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const { data } = await api.get<CounselorDirectoryResponse>('/counselors/directory');
      setCounselors(data.counselors);
    } catch {
      setError('Could not load counselors. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const selected = counselors.find((c) => c.counselor_id === selectedCounselor);

  const confirmBooking = async () => {
    if (!selectedSlot) return;
    setBooking(true);
    setError(null);
    try {
      const { data } = await api.post<BookResponse>('/counselors/book', { slot_id: selectedSlot.slot_id });
      setConfirmation(data);
      await load();
      setSelectedSlot(null);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Booking failed. Please pick another slot.');
    } finally {
      setBooking(false);
    }
  };

  const fmtSlot = (s: AvailabilitySlot) =>
    new Date(s.start_at).toLocaleString('en-US', {
      weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    });

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-50 bg-white border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Link to="/student" className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition">
                <ArrowLeft className="w-5 h-5" />
                <span className="hidden sm:inline">Back to Dashboard</span>
              </Link>
              <div className="hidden sm:block w-px h-6 bg-border"></div>
              <div className="flex items-center gap-2">
                <KioLogo className="h-7 w-auto" />
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-2">Book a Counselor Session</h1>
          <p className="text-muted-foreground">
            Connect with any licensed Kio counselor — available to every student, from every school.
          </p>
        </div>

        {confirmation && (
          <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-xl flex items-start gap-3">
            <Check className="w-5 h-5 text-emerald-600 mt-0.5 shrink-0" />
            <div className="text-sm text-emerald-800">
              <p className="font-semibold">Session booked with {confirmation.counselor_name}</p>
              <p>{new Date(confirmation.scheduled_at).toLocaleString('en-US', {
                weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit',
              })}</p>
            </div>
          </div>
        )}

        {error && (
          <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">{error}</div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
          </div>
        ) : counselors.length === 0 ? (
          <div className="text-center py-20 text-muted-foreground">
            <Calendar className="w-12 h-12 mx-auto mb-4 opacity-30" />
            <p className="font-medium">No counselors are available right now</p>
            <p className="text-sm mt-1">Please check back soon.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6">
            {counselors.map((counselor) => (
              <div
                key={counselor.counselor_id}
                className={`bg-card border-2 rounded-xl p-6 transition ${
                  selectedCounselor === counselor.counselor_id ? 'border-primary shadow-lg' : 'border-border shadow-sm'
                }`}
              >
                <div className="flex flex-col md:flex-row gap-6">
                  {counselor.photo ? (
                    <img src={counselor.photo} alt={counselor.name}
                      className="w-24 h-24 rounded-xl object-cover flex-shrink-0" />
                  ) : (
                    <div className="w-24 h-24 bg-gradient-to-br from-primary to-secondary rounded-xl flex items-center justify-center text-white text-2xl font-semibold flex-shrink-0">
                      {counselor.name.split(' ').map((n) => n[0]).join('').slice(0, 2)}
                    </div>
                  )}

                  <div className="flex-1 space-y-4">
                    <div>
                      <div className="flex items-start justify-between mb-2 gap-3">
                        <div>
                          <h3 className="text-xl font-semibold text-foreground">{counselor.name}</h3>
                          {counselor.qualification && (
                            <p className="text-sm text-muted-foreground flex items-center gap-1">
                              <GraduationCap className="w-4 h-4" /> {counselor.qualification}
                            </p>
                          )}
                        </div>
                        {counselor.rating != null && (
                          <div className="flex items-center gap-1 px-3 py-1 bg-amber-50 rounded-lg shrink-0">
                            <Star className="w-4 h-4 text-amber-500 fill-amber-500" />
                            <span className="font-medium text-sm">{counselor.rating.toFixed(1)}</span>
                          </div>
                        )}
                      </div>
                      {counselor.bio && <p className="text-sm text-foreground leading-relaxed">{counselor.bio}</p>}
                    </div>

                    <div className="flex flex-wrap gap-2">
                      {counselor.specializations.map((s, i) => (
                        <span key={i} className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm">{s}</span>
                      ))}
                    </div>

                    <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                      {counselor.experience_years != null && (
                        <div className="flex items-center gap-2"><Award className="w-4 h-4" />{counselor.experience_years} years experience</div>
                      )}
                      {counselor.languages.length > 0 && (
                        <div className="flex items-center gap-2"><Globe className="w-4 h-4" />{counselor.languages.join(', ')}</div>
                      )}
                    </div>

                    {/* Slots */}
                    <div>
                      <div className="text-sm font-medium mb-2 flex items-center gap-1">
                        <Clock className="w-4 h-4 text-muted-foreground" /> Available times
                      </div>
                      {counselor.next_slots.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No open slots right now.</p>
                      ) : (
                        <div className="flex flex-wrap gap-2">
                          {counselor.next_slots.map((slot) => {
                            const active = selectedSlot?.slot_id === slot.slot_id;
                            return (
                              <button
                                key={slot.slot_id}
                                onClick={() => { setSelectedCounselor(counselor.counselor_id); setSelectedSlot(slot); }}
                                className={`px-3 py-2 rounded-lg text-sm border transition ${
                                  active ? 'border-primary bg-primary text-primary-foreground' : 'border-border hover:border-primary/50'
                                }`}
                              >
                                {fmtSlot(slot)}
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    {selectedCounselor === counselor.counselor_id && selectedSlot && (
                      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-center justify-between gap-4">
                        <div className="text-sm">
                          <span className="text-muted-foreground">Booking: </span>
                          <span className="font-medium">{fmtSlot(selectedSlot)}</span>
                        </div>
                        <button
                          onClick={confirmBooking}
                          disabled={booking}
                          className="flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-xl font-medium hover:bg-primary/90 transition disabled:opacity-50"
                        >
                          {booking ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                          Confirm Booking
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
