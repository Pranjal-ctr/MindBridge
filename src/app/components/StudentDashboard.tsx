import { Link } from 'react-router-dom';
import { Brain, MessageSquare, TrendingUp, BookOpen, Lightbulb, Settings, Send, Mic, Smile, Meh, Frown, Menu, X, Plus, Loader2, Trash2, Users } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../../lib/auth-context';
import { useConversations, useMessages } from '../../hooks/useConversations';
import { useWellnessScore } from '../../hooks/useWellness';
import { StudentOnboarding } from './StudentOnboarding';
import api from '../../lib/api';
import type { MoodCheckin, OnboardingResponse } from '../../lib/types';

export function StudentDashboard() {
  const { user, logout } = useAuth();
  const { conversations, isLoading: convsLoading, createConversation, deleteConversation, refetch: refetchConversations } = useConversations();

  // First-login onboarding: show the wizard once until completed
  const [showOnboarding, setShowOnboarding] = useState(false);
  useEffect(() => {
    let cancelled = false;
    api
      .get<OnboardingResponse | null>('/onboarding/')
      .then((res) => { if (!cancelled && !res.data) setShowOnboarding(true); })
      .catch(() => {/* non-fatal: skip onboarding gate on error */});
    return () => { cancelled = true; };
  }, []);

  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const { messages, isLoading: msgsLoading, isSending, sendMessage } = useMessages(activeConversationId);
  const { score: wellness, checkInMood, refetch: refetchWellness } = useWellnessScore();

  const [messageInput, setMessageInput] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedMood, setSelectedMood] = useState<MoodCheckin | null>(null);
  const [isCheckingIn, setIsCheckingIn] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-select the first conversation on load
  useEffect(() => {
    if (conversations.length > 0 && !activeConversationId) {
      setActiveConversationId(conversations[0].conversation_id);
    }
  }, [conversations, activeConversationId]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const suggestedPrompts = [
    "I feel stressed before exams",
    "I feel lonely",
    "How can I improve my confidence?",
    "Help me make a study plan"
  ];

  const handleSendMessage = async () => {
    const text = messageInput.trim();
    if (!text || isSending) return;

    // If no active conversation, create one first
    let convId = activeConversationId;
    if (!convId) {
      try {
        const newConv = await createConversation(text.slice(0, 50));
        convId = newConv.conversation_id;
        setActiveConversationId(convId);
      } catch {
        return;
      }
    }

    setMessageInput('');

    try {
      await sendMessage(text);
      // Refetch conversations to pick up auto-generated titles
      refetchConversations();
      // The intelligence pipeline runs as a background task after the chat
      // response returns, so give it a moment before pulling the updated score.
      setTimeout(() => refetchWellness(), 8000);
    } catch {
      // Error is handled by the hook
    }
  };

  const handleMoodCheckin = async (mood: MoodCheckin) => {
    if (isCheckingIn) return;
    setSelectedMood(mood);
    setIsCheckingIn(true);
    try {
      await checkInMood(mood);
    } catch {
      // Non-fatal: the button still reflects the selection locally
    } finally {
      setIsCheckingIn(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleNewConversation = async () => {
    try {
      const newConv = await createConversation();
      setActiveConversationId(newConv.conversation_id);
      setSidebarOpen(false);
    } catch {
      // Error handled by hook
    }
  };

  const handleDeleteConversation = async (convId: string) => {
    await deleteConversation(convId);
    if (activeConversationId === convId) {
      setActiveConversationId(null);
    }
  };

  const activeConversation = conversations.find(
    (c) => c.conversation_id === activeConversationId
  );

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {showOnboarding && <StudentOnboarding onComplete={() => setShowOnboarding(false)} />}
      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0 fixed md:static inset-y-0 left-0 z-50 w-64 bg-sidebar border-r border-sidebar-border transition-transform duration-300 ease-in-out`}>
        <div className="flex flex-col h-full">
          <div className="p-4 border-b border-sidebar-border">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Brain className="w-6 h-6 text-primary" />
                <span className="font-semibold">MindBridge</span>
              </div>
              <button className="md:hidden" onClick={() => setSidebarOpen(false)}>
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="mt-3 px-3 py-2 bg-sidebar-accent rounded-lg">
              <div className="text-sm font-medium">
                {user ? `${user.first_name} ${user.last_name}` : 'Loading...'}
              </div>
              <div className="text-xs text-muted-foreground">Student</div>
            </div>
          </div>

          {/* New Conversation Button */}
          <div className="p-3">
            <button
              onClick={handleNewConversation}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition text-sm font-medium"
            >
              <Plus className="w-4 h-4" />
              New Chat
            </button>
          </div>

          {/* Conversation List */}
          <div className="flex-1 overflow-y-auto px-3 space-y-1">
            {convsLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
              </div>
            ) : conversations.length === 0 ? (
              <div className="text-center py-8 text-sm text-muted-foreground">
                No conversations yet. Start a new chat!
              </div>
            ) : (
              conversations.map((conv) => (
                <div
                  key={conv.conversation_id}
                  className={`group flex items-center justify-between rounded-lg transition cursor-pointer ${
                    activeConversationId === conv.conversation_id
                      ? 'bg-sidebar-primary text-sidebar-primary-foreground'
                      : 'text-sidebar-foreground hover:bg-sidebar-accent'
                  }`}
                >
                  <button
                    onClick={() => {
                      setActiveConversationId(conv.conversation_id);
                      setSidebarOpen(false);
                    }}
                    className="flex-1 flex items-center gap-3 px-3 py-2 text-left min-w-0"
                  >
                    <MessageSquare className="w-4 h-4 shrink-0" />
                    <span className="text-sm truncate">
                      {conv.title || 'New Conversation'}
                    </span>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteConversation(conv.conversation_id);
                    }}
                    className="p-1.5 mr-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-100 hover:text-red-600 transition"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))
            )}
          </div>

          {/* Sidebar Navigation */}
          <nav className="p-3 space-y-1 border-t border-sidebar-border">
            <Link to="/student/growth" className="flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition">
              <TrendingUp className="w-5 h-5" />
              <span className="text-sm">Growth Profile</span>
            </Link>
            <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition">
              <BookOpen className="w-5 h-5" />
              <span className="text-sm">Journal</span>
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition">
              <Lightbulb className="w-5 h-5" />
              <span className="text-sm">Insights</span>
            </a>
            <Link to="/student/family" className="flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition">
              <Users className="w-5 h-5" />
              <span className="text-sm">Family</span>
            </Link>
          </nav>

          <div className="p-4 border-t border-sidebar-border space-y-2">
            <Link to="/book-counselor" className="flex items-center justify-center gap-2 px-4 py-2 bg-accent text-accent-foreground rounded-lg hover:bg-accent/90 transition">
              <span className="text-sm font-medium">Book Counselor</span>
            </Link>
            <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent transition">
              <Settings className="w-5 h-5" />
              <span className="text-sm">Settings</span>
            </a>
            <button
              onClick={logout}
              className="w-full flex items-center justify-center px-3 py-2 rounded-lg text-muted-foreground hover:bg-sidebar-accent transition text-sm"
            >
              Sign Out
            </button>
          </div>
        </div>
      </div>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="h-16 border-b border-border bg-card flex items-center justify-between px-4 md:px-6">
          <div className="flex items-center gap-4">
            <button className="md:hidden" onClick={() => setSidebarOpen(true)}>
              <Menu className="w-6 h-6" />
            </button>
            <h1 className="text-lg font-semibold">
              {activeConversation?.title || 'AI Wellness Companion'}
            </h1>
          </div>
          <div className="text-sm text-muted-foreground">
            <span className="hidden sm:inline">Always here to listen • </span>Safe & Private
          </div>
        </header>

        {/* Wellness Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 md:p-6 border-b border-border">
          <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-4 border border-blue-200">
            <div className="text-sm text-blue-700 mb-1">Wellness Score</div>
            <div className="text-2xl font-bold text-blue-900">
              {wellness?.has_data ? `${Math.round(wellness.overall!)}/100` : '—'}
            </div>
            <div className="text-xs text-blue-600 mt-1">
              {wellness?.has_data
                ? wellness.trend === 'improving'
                  ? '↑ Improving'
                  : wellness.trend === 'declining'
                  ? '↓ Needs attention'
                  : 'Holding steady'
                : 'Chat or check in to get started'}
            </div>
          </div>

          <div className="bg-gradient-to-br from-emerald-50 to-emerald-100 rounded-xl p-4 border border-emerald-200">
            <div className="text-sm text-emerald-700 mb-1">Check-in Streak</div>
            <div className="text-2xl font-bold text-emerald-900">
              {wellness?.streak_days ?? 0} day{wellness?.streak_days === 1 ? '' : 's'}
            </div>
            <div className="text-xs text-emerald-600 mt-1">
              {(wellness?.streak_days ?? 0) > 0 ? 'Keep it up!' : 'Check in today to start a streak'}
            </div>
          </div>

          <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-4 border border-purple-200">
            <div className="text-sm text-purple-700 mb-1">Today's Mood</div>
            <div className="flex gap-2 mt-2">
              {[
                { icon: Smile, label: 'Happy' as MoodCheckin, color: 'text-emerald-600' },
                { icon: Meh, label: 'Okay' as MoodCheckin, color: 'text-amber-600' },
                { icon: Frown, label: 'Down' as MoodCheckin, color: 'text-red-600' }
              ].map(({ icon: Icon, label, color }) => {
                const value = label.toLowerCase() as MoodCheckin;
                return (
                  <button
                    key={label}
                    onClick={() => handleMoodCheckin(value)}
                    disabled={isCheckingIn}
                    className={`p-2 rounded-lg transition disabled:opacity-50 ${
                      selectedMood === value
                        ? 'bg-purple-200'
                        : 'bg-white hover:bg-purple-100'
                    }`}
                  >
                    <Icon className={`w-5 h-5 ${color}`} />
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
          {msgsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : messages.length === 0 ? (
            <>
              {/* Empty state — show suggested prompts */}
              <div className="flex justify-start">
                <div className="flex items-start gap-2">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center flex-shrink-0 mt-1">
                    <Brain className="w-4 h-4 text-white" />
                  </div>
                  <div className="max-w-[80%] md:max-w-[70%] rounded-2xl px-4 py-3 bg-muted text-foreground">
                    Hey! I'm <strong>Comrade</strong>, your trusted companion here on MindBridge. How are you feeling today?
                  </div>
                </div>
              </div>
              <div className="space-y-3">
                <div className="text-sm text-muted-foreground text-center">Try asking about:</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {suggestedPrompts.map((prompt, idx) => (
                    <button
                      key={idx}
                      onClick={() => setMessageInput(prompt)}
                      className="px-4 py-3 bg-gradient-to-r from-blue-50 to-indigo-50 hover:from-blue-100 hover:to-indigo-100 border border-blue-200 rounded-xl text-sm text-left transition"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            </>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.message_id}
                className={`flex ${msg.sender_type === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {msg.sender_type !== 'user' && (
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center flex-shrink-0 mt-1 mr-2">
                    <Brain className="w-4 h-4 text-white" />
                  </div>
                )}
                <div
                  className={`max-w-[80%] md:max-w-[70%] rounded-2xl px-4 py-3 whitespace-pre-wrap ${
                    msg.sender_type === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-foreground'
                  }`}
                >
                  {msg.message_text}
                </div>
              </div>
            ))
          )}

          {/* Comrade is thinking indicator */}
          {isSending && (
            <div className="flex justify-start">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center flex-shrink-0 mt-1 mr-2">
                <Brain className="w-4 h-4 text-white" />
              </div>
              <div className="max-w-[80%] md:max-w-[70%] rounded-2xl px-4 py-3 bg-muted text-muted-foreground flex items-center gap-3">
                <span className="text-sm font-medium">Comrade is thinking</span>
                <span className="flex gap-1">
                  <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                  <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                  <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                </span>
              </div>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 md:p-6 border-t border-border bg-card">
          <div className="flex gap-3">
            <input
              type="text"
              value={messageInput}
              onChange={(e) => setMessageInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Share what's on your mind... This is a safe space."
              className="flex-1 px-4 py-3 bg-input-background rounded-xl border border-border focus:outline-none focus:ring-2 focus:ring-ring"
              disabled={isSending}
            />
            <button className="p-3 bg-muted hover:bg-muted/80 rounded-xl transition">
              <Mic className="w-5 h-5" />
            </button>
            <button
              onClick={handleSendMessage}
              disabled={!messageInput.trim() || isSending}
              className="px-6 py-3 bg-primary text-primary-foreground rounded-xl hover:bg-primary/90 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
          <div className="mt-3 text-xs text-muted-foreground text-center">
            Your conversations are private and encrypted. Parents receive insights, not raw chats.
          </div>
        </div>
      </div>
    </div>
  );
}
