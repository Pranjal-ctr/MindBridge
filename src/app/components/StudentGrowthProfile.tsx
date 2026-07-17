/**
 * Kio Student Growth Profile
 * Displays AI-extracted memories organized by category.
 * Students can view, pin, and delete their memories.
 */

import { Link } from 'react-router-dom';
import {
  Brain, ArrowLeft, Target, BookOpen, Heart, Users, Sparkles, Star,
  Trash2, Pin, PinOff, Loader2, AlertCircle, GraduationCap,
} from 'lucide-react';
import { useAuth } from '../../lib/auth-context';
import { useMemories } from '../../hooks/useMemory';
import type { MemoryType } from '../../lib/types';

const MEMORY_TYPE_CONFIG: Record<MemoryType, {
  label: string;
  icon: typeof Target;
  gradient: string;
  bgLight: string;
  textColor: string;
}> = {
  goal: {
    label: 'Goals & Aspirations',
    icon: Target,
    gradient: 'from-amber-500 to-orange-600',
    bgLight: 'bg-amber-50 border-amber-200',
    textColor: 'text-amber-700',
  },
  academic: {
    label: 'Academic',
    icon: GraduationCap,
    gradient: 'from-blue-500 to-cyan-600',
    bgLight: 'bg-blue-50 border-blue-200',
    textColor: 'text-blue-700',
  },
  emotion: {
    label: 'Emotional Wellbeing',
    icon: Heart,
    gradient: 'from-rose-500 to-pink-600',
    bgLight: 'bg-rose-50 border-rose-200',
    textColor: 'text-rose-700',
  },
  relationship: {
    label: 'Relationships',
    icon: Users,
    gradient: 'from-violet-500 to-purple-600',
    bgLight: 'bg-violet-50 border-violet-200',
    textColor: 'text-violet-700',
  },
  preference: {
    label: 'Preferences & Habits',
    icon: Star,
    gradient: 'from-emerald-500 to-teal-600',
    bgLight: 'bg-emerald-50 border-emerald-200',
    textColor: 'text-emerald-700',
  },
  fact: {
    label: 'About You',
    icon: Sparkles,
    gradient: 'from-slate-500 to-gray-600',
    bgLight: 'bg-slate-50 border-slate-200',
    textColor: 'text-slate-700',
  },
};

const TYPE_ORDER: MemoryType[] = ['goal', 'academic', 'emotion', 'relationship', 'preference', 'fact'];

export function StudentGrowthProfile() {
  const { user } = useAuth();
  const { groupedMemories, memories, isLoading, error, deleteMemory, togglePin } = useMemories();

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 text-white">
        <div className="max-w-5xl mx-auto px-4 py-8">
          <div className="flex items-center gap-3 mb-4">
            <Link
              to="/student"
              className="flex items-center gap-1 text-white/80 hover:text-white transition text-sm"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Chat
            </Link>
          </div>
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <Brain className="w-7 h-7" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">My Growth Profile</h1>
              <p className="text-white/80 text-sm mt-1">
                What Comrade knows about you — from your conversations
              </p>
            </div>
          </div>
          <div className="mt-6 flex gap-4 text-sm">
            <div className="bg-white/15 backdrop-blur-sm rounded-xl px-4 py-2">
              <span className="font-semibold">{memories.length}</span> memories
            </div>
            <div className="bg-white/15 backdrop-blur-sm rounded-xl px-4 py-2">
              <span className="font-semibold">{memories.filter(m => m.is_pinned).length}</span> pinned
            </div>
            <div className="bg-white/15 backdrop-blur-sm rounded-xl px-4 py-2">
              <span className="font-semibold">{Object.keys(groupedMemories).length}</span> categories
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-5xl mx-auto px-4 py-8">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <AlertCircle className="w-10 h-10 mb-3" />
            <p>{error}</p>
          </div>
        ) : memories.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="w-20 h-20 rounded-full bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center mb-6">
              <Brain className="w-10 h-10 text-indigo-400" />
            </div>
            <h2 className="text-xl font-semibold mb-2">No memories yet</h2>
            <p className="text-muted-foreground max-w-md">
              As you chat with Comrade, important things about you — your goals,
              challenges, and interests — will appear here automatically.
            </p>
            <Link
              to="/student"
              className="mt-6 px-6 py-3 bg-primary text-primary-foreground rounded-xl hover:bg-primary/90 transition"
            >
              Start a conversation
            </Link>
          </div>
        ) : (
          <div className="space-y-8">
            {TYPE_ORDER.map((type) => {
              const items = groupedMemories[type];
              if (!items || items.length === 0) return null;
              const config = MEMORY_TYPE_CONFIG[type];
              const Icon = config.icon;

              return (
                <div key={type}>
                  <div className="flex items-center gap-3 mb-4">
                    <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${config.gradient} flex items-center justify-center`}>
                      <Icon className="w-4 h-4 text-white" />
                    </div>
                    <h2 className="text-lg font-semibold">{config.label}</h2>
                    <span className="text-sm text-muted-foreground">({items.length})</span>
                  </div>
                  <div className="grid gap-3">
                    {items.map((mem) => (
                      <div
                        key={mem.memory_id}
                        className={`flex items-start gap-3 p-4 rounded-xl border ${config.bgLight} transition hover:shadow-sm`}
                      >
                        <div className="flex-1 min-w-0">
                          <p className={`text-sm font-medium ${config.textColor}`}>
                            {mem.content}
                          </p>
                          <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                            <span>
                              {new Date(mem.created_at).toLocaleDateString('en-US', {
                                month: 'short',
                                day: 'numeric',
                                year: 'numeric',
                              })}
                            </span>
                            {mem.importance_score !== null && (
                              <span className="bg-white/80 px-2 py-0.5 rounded-full">
                                Importance: {Math.round(mem.importance_score * 100)}%
                              </span>
                            )}
                            {mem.is_pinned && (
                              <span className="bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
                                Pinned
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-1 flex-shrink-0">
                          <button
                            onClick={() => togglePin(mem.memory_id, mem.is_pinned)}
                            className={`p-2 rounded-lg transition ${
                              mem.is_pinned
                                ? 'bg-amber-200 text-amber-700 hover:bg-amber-300'
                                : 'bg-white/80 text-muted-foreground hover:bg-white hover:text-foreground'
                            }`}
                            title={mem.is_pinned ? 'Unpin memory' : 'Pin memory'}
                          >
                            {mem.is_pinned ? <PinOff className="w-4 h-4" /> : <Pin className="w-4 h-4" />}
                          </button>
                          <button
                            onClick={() => deleteMemory(mem.memory_id)}
                            className="p-2 rounded-lg bg-white/80 text-muted-foreground hover:bg-red-100 hover:text-red-600 transition"
                            title="Delete memory"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
