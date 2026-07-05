import { Link } from 'react-router-dom';
import { Brain, ArrowLeft, Star, Calendar, Video, MessageSquare, Clock, Check } from 'lucide-react';
import { useState } from 'react';

export function BookCounselor() {
  const [selectedCounselor, setSelectedCounselor] = useState<number | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [selectedTime, setSelectedTime] = useState<string>('');
  const [sessionType, setSessionType] = useState<'video' | 'chat'>('video');

  const counselors = [
    {
      id: 1,
      name: 'Dr. Jennifer Martinez',
      title: 'Licensed Clinical Psychologist',
      specialties: ['Anxiety', 'Depression', 'Academic Stress', 'Teen Wellness'],
      rating: 4.9,
      reviews: 127,
      experience: '12 years',
      nextAvailable: 'Today at 3:00 PM',
      bio: 'Specializes in adolescent mental health with a focus on academic stress and anxiety management. Warm, empathetic approach to helping students navigate challenging times.'
    },
    {
      id: 2,
      name: 'Dr. Marcus Chen',
      title: 'Licensed Counselor',
      specialties: ['Social Anxiety', 'Self-Esteem', 'Relationship Issues', 'LGBTQ+ Support'],
      rating: 4.8,
      reviews: 94,
      experience: '8 years',
      nextAvailable: 'Tomorrow at 10:00 AM',
      bio: 'Focuses on identity development and social relationships. Creates a safe, non-judgmental space for students to explore their feelings and build confidence.'
    },
    {
      id: 3,
      name: 'Sarah Thompson, LMFT',
      title: 'Licensed Marriage & Family Therapist',
      specialties: ['Family Conflict', 'Communication', 'Stress Management', 'Life Transitions'],
      rating: 5.0,
      reviews: 85,
      experience: '10 years',
      nextAvailable: 'Wednesday at 2:00 PM',
      bio: 'Specializes in family dynamics and helping students navigate home-school balance. Collaborative approach that often includes parent guidance sessions.'
    }
  ];

  const availableTimes = [
    '10:00 AM', '11:00 AM', '2:00 PM', '3:00 PM', '4:00 PM', '5:00 PM'
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
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
                <Brain className="w-6 h-6 text-primary" />
                <span className="font-semibold">MindBridge</span>
              </div>
            </div>
            <Link to="/" className="text-sm text-muted-foreground hover:text-foreground transition">
              Sign Out
            </Link>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Page Title */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-2">Book a Counselor Session</h1>
          <p className="text-muted-foreground">
            Connect with a licensed professional for personalized support
          </p>
        </div>

        {/* Session Type Selection */}
        <div className="mb-8">
          <div className="text-sm font-medium text-foreground mb-3">Session Type</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-2xl">
            <button
              onClick={() => setSessionType('video')}
              className={`flex items-center gap-4 p-4 border-2 rounded-xl transition ${
                sessionType === 'video'
                  ? 'border-primary bg-blue-50'
                  : 'border-border bg-card hover:border-primary/50'
              }`}
            >
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                sessionType === 'video' ? 'bg-primary' : 'bg-muted'
              }`}>
                <Video className={`w-6 h-6 ${sessionType === 'video' ? 'text-white' : 'text-muted-foreground'}`} />
              </div>
              <div className="text-left">
                <div className="font-medium">Video Session</div>
                <div className="text-sm text-muted-foreground">Face-to-face online meeting</div>
              </div>
              {sessionType === 'video' && <Check className="w-5 h-5 text-primary ml-auto" />}
            </button>

            <button
              onClick={() => setSessionType('chat')}
              className={`flex items-center gap-4 p-4 border-2 rounded-xl transition ${
                sessionType === 'chat'
                  ? 'border-primary bg-blue-50'
                  : 'border-border bg-card hover:border-primary/50'
              }`}
            >
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                sessionType === 'chat' ? 'bg-primary' : 'bg-muted'
              }`}>
                <MessageSquare className={`w-6 h-6 ${sessionType === 'chat' ? 'text-white' : 'text-muted-foreground'}`} />
              </div>
              <div className="text-left">
                <div className="font-medium">Chat Session</div>
                <div className="text-sm text-muted-foreground">Text-based conversation</div>
              </div>
              {sessionType === 'chat' && <Check className="w-5 h-5 text-primary ml-auto" />}
            </button>
          </div>
        </div>

        {/* Counselor Selection */}
        <div className="mb-8">
          <div className="text-sm font-medium text-foreground mb-4">Select a Counselor</div>
          <div className="grid grid-cols-1 gap-6">
            {counselors.map((counselor) => (
              <div
                key={counselor.id}
                className={`bg-card border-2 rounded-xl p-6 transition cursor-pointer ${
                  selectedCounselor === counselor.id
                    ? 'border-primary shadow-lg'
                    : 'border-border hover:border-primary/50 shadow-sm'
                }`}
                onClick={() => setSelectedCounselor(counselor.id)}
              >
                <div className="flex flex-col md:flex-row gap-6">
                  <div className="w-24 h-24 bg-gradient-to-br from-primary to-secondary rounded-xl flex items-center justify-center text-white text-2xl font-semibold flex-shrink-0">
                    {counselor.name.split(' ').map(n => n[0]).join('')}
                  </div>

                  <div className="flex-1 space-y-4">
                    <div>
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <h3 className="text-xl font-semibold text-foreground">{counselor.name}</h3>
                          <p className="text-sm text-muted-foreground">{counselor.title}</p>
                        </div>
                        <div className="flex items-center gap-1 px-3 py-1 bg-amber-50 rounded-lg">
                          <Star className="w-4 h-4 text-amber-500 fill-amber-500" />
                          <span className="font-medium text-sm">{counselor.rating}</span>
                          <span className="text-xs text-muted-foreground">({counselor.reviews})</span>
                        </div>
                      </div>
                      <p className="text-sm text-foreground leading-relaxed">{counselor.bio}</p>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      {counselor.specialties.map((specialty, idx) => (
                        <span key={idx} className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm">
                          {specialty}
                        </span>
                      ))}
                    </div>

                    <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                      <div className="flex items-center gap-2">
                        <Clock className="w-4 h-4" />
                        <span>{counselor.experience} experience</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4" />
                        <span>Next: {counselor.nextAvailable}</span>
                      </div>
                    </div>
                  </div>

                  {selectedCounselor === counselor.id && (
                    <div className="flex items-center">
                      <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center">
                        <Check className="w-5 h-5 text-white" />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Date & Time Selection */}
        {selectedCounselor && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div>
              <label className="text-sm font-medium text-foreground mb-3 block">Select Date</label>
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                min={new Date().toISOString().split('T')[0]}
                className="w-full px-4 py-3 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-ring bg-input-background"
              />
            </div>

            <div>
              <label className="text-sm font-medium text-foreground mb-3 block">Select Time</label>
              <div className="grid grid-cols-3 gap-2">
                {availableTimes.map((time) => (
                  <button
                    key={time}
                    onClick={() => setSelectedTime(time)}
                    className={`px-4 py-3 border rounded-lg text-sm transition ${
                      selectedTime === time
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'border-border bg-card hover:border-primary/50'
                    }`}
                  >
                    {time}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Booking Summary */}
        {selectedCounselor && selectedDate && selectedTime && (
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-6 mb-8">
            <h3 className="font-semibold text-foreground mb-4">Booking Summary</h3>
            <div className="space-y-2 text-sm mb-6">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Counselor:</span>
                <span className="font-medium">{counselors.find(c => c.id === selectedCounselor)?.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Session Type:</span>
                <span className="font-medium capitalize">{sessionType} Session</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Date:</span>
                <span className="font-medium">{new Date(selectedDate).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Time:</span>
                <span className="font-medium">{selectedTime}</span>
              </div>
              <div className="flex justify-between pt-2 border-t border-blue-200">
                <span className="text-muted-foreground">Duration:</span>
                <span className="font-medium">45 minutes</span>
              </div>
            </div>

            <button className="w-full px-6 py-4 bg-primary text-primary-foreground rounded-xl font-medium hover:bg-primary/90 transition shadow-lg">
              Confirm Booking
            </button>
          </div>
        )}

        {/* Info Card */}
        <div className="bg-card border border-border rounded-xl p-6">
          <h3 className="font-semibold text-foreground mb-4">What to Expect</h3>
          <div className="space-y-3 text-sm text-muted-foreground">
            <div className="flex items-start gap-3">
              <Check className="w-5 h-5 text-accent flex-shrink-0 mt-0.5" />
              <span>Sessions are completely confidential and private</span>
            </div>
            <div className="flex items-start gap-3">
              <Check className="w-5 h-5 text-accent flex-shrink-0 mt-0.5" />
              <span>You'll receive a reminder email 24 hours before your session</span>
            </div>
            <div className="flex items-start gap-3">
              <Check className="w-5 h-5 text-accent flex-shrink-0 mt-0.5" />
              <span>Video sessions include a secure, HIPAA-compliant meeting room</span>
            </div>
            <div className="flex items-start gap-3">
              <Check className="w-5 h-5 text-accent flex-shrink-0 mt-0.5" />
              <span>You can reschedule or cancel up to 24 hours before your appointment</span>
            </div>
            <div className="flex items-start gap-3">
              <Check className="w-5 h-5 text-accent flex-shrink-0 mt-0.5" />
              <span>Your counselor will have access to AI-generated summaries to provide better support</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
