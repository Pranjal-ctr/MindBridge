/**
 * "Kio is not just a chatbot" — the product story as a loop a student actually
 * lives in: Check in → Talk → Reflect → Act → Grow.
 *
 * Each step names a surface that exists in the app today (the check-in modal,
 * Comrade, the journal, weekly activities, the growth profile) rather than a
 * capability we would like to have. The human-support band underneath is the
 * old "How It Works" content, kept — it was accurate — and re-pointed at what
 * each role actually receives, including the small-cohort suppression that
 * keeps school analytics from naming anyone.
 *
 * Keeps the `#how-it-works` id so the existing header navigation still lands
 * here.
 */

import { MessageCircle, PenLine, School, Smile, Sparkles, TrendingUp, Users } from 'lucide-react';
import { KioMascot } from '../KioMascot';
import { Reveal } from './Reveal';
import { SectionLabel } from './SectionLabel';

const STEPS = [
  {
    verb: 'Check in',
    surface: 'Daily check-in',
    body: 'A mood and a reason, in the time it takes to put a bag down.',
    icon: Smile,
    tint: 'from-violet-500 to-violet-600',
  },
  {
    verb: 'Talk',
    surface: 'Comrade',
    body: 'A private companion for the things that are hard to say out loud.',
    icon: null, // Kio itself stands in for this step.
    tint: 'from-indigo-500 to-indigo-600',
  },
  {
    verb: 'Reflect',
    surface: 'Journal',
    body: 'A quiet page to write it down — kept private to the student.',
    icon: PenLine,
    tint: 'from-sky-500 to-sky-600',
  },
  {
    verb: 'Act',
    surface: 'Activities',
    body: 'Small weekly steps, chosen from how the week has actually gone.',
    icon: Sparkles,
    tint: 'from-teal-500 to-teal-600',
  },
  {
    verb: 'Grow',
    surface: 'Growth',
    body: 'Patterns over time, so progress is something you can see.',
    icon: TrendingUp,
    tint: 'from-emerald-500 to-emerald-600',
  },
];

const HUMANS = [
  {
    icon: Users,
    title: 'Parents',
    body: 'Receive wellbeing insights and practical recommendations — never the raw conversations.',
  },
  {
    icon: MessageCircle,
    title: 'Counselors',
    body: 'Get an AI-written summary, and can be booked directly by a student or a parent.',
  },
  {
    icon: School,
    title: 'Schools',
    body: 'See anonymised, aggregated patterns. Small groups are withheld rather than named.',
  },
];

export function ProductStorySection() {
  return (
    <section
      id="how-it-works"
      aria-labelledby="product-story-heading"
      className="relative overflow-hidden bg-gradient-to-b from-[#F7F6FE] via-white to-white scroll-mt-20 py-16 md:py-20"
    >
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <Reveal className="mx-auto max-w-3xl text-center">
          <SectionLabel>How Kio works</SectionLabel>
          <h2
            id="product-story-heading"
            className="mt-6 text-[2.25rem] font-bold leading-[1.15] text-foreground sm:text-4xl md:text-5xl"
          >
            Kio is not just a chatbot.
          </h2>
          <p className="mx-auto mt-5 max-w-2xl text-xl leading-relaxed text-muted-foreground">
            It is a small daily loop — five habits that, together, make a student&apos;s own
            wellbeing something they can see and shape.
          </p>
        </Reveal>

        {/* The loop */}
        <ol className="relative mt-10 grid gap-4 sm:grid-cols-2 lg:mt-14 lg:grid-cols-5 lg:gap-5">
          {/* Connecting thread, desktop only. */}
          <div
            aria-hidden
            className="pointer-events-none absolute left-0 right-0 top-[2.75rem] hidden h-px bg-gradient-to-r from-violet-200 via-sky-200 to-emerald-200 lg:block"
          />

          {STEPS.map(({ verb, surface, body, icon: Icon, tint }, index) => (
            <Reveal as="li" key={verb} delay={index * 90} className="relative">
              <div className="group h-full rounded-2xl border border-border/70 bg-white p-5 shadow-sm transition duration-300 hover:-translate-y-1 hover:shadow-xl">
                <div className="flex items-center gap-3">
                  {Icon ? (
                    <span
                      className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br ${tint} shadow-lg shadow-black/5`}
                    >
                      <Icon className="h-6 w-6 text-white" aria-hidden />
                    </span>
                  ) : (
                    <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-100 to-indigo-100">
                      <KioMascot size={40} withParticles={false} />
                    </span>
                  )}
                  <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                </div>
                <h3 className="mt-4 text-xl font-semibold text-foreground">{verb}</h3>
                <p className="mt-1 text-[0.9375rem] font-medium text-secondary">{surface}</p>
                <p className="mt-3 text-[0.9375rem] leading-relaxed text-muted-foreground">{body}</p>
              </div>
            </Reveal>
          ))}
        </ol>

        {/* Human support */}
        <Reveal className="mt-12 lg:mt-14">
          <div className="overflow-hidden rounded-3xl border border-border/70 bg-white/70 shadow-sm backdrop-blur-sm">
            <div className="border-b border-border/70 bg-gradient-to-r from-[#F4F3FE] to-[#EFFBF9] px-6 py-6 text-center sm:px-10">
              <h3 className="text-2xl font-bold leading-snug text-foreground sm:text-3xl">
                And there is always a human at the end of it.
              </h3>
              <p className="mx-auto mt-2 max-w-2xl text-[1.0625rem] leading-relaxed text-muted-foreground">
                Kio is the space a student reaches for first. What it notices becomes something the
                people around them can act on — without reading a word the student wanted to keep
                private.
              </p>
            </div>
            <ul className="grid gap-px bg-border/70 sm:grid-cols-3">
              {HUMANS.map(({ icon: Icon, title, body }, index) => (
                <Reveal as="li" key={title} delay={index * 90} className="bg-white p-6 sm:p-7">
                  <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#EEF1FB] text-primary">
                    <Icon className="h-5 w-5" aria-hidden />
                  </span>
                  <h4 className="mt-4 text-[1.0625rem] font-semibold text-foreground">{title}</h4>
                  <p className="mt-2 text-[0.9375rem] leading-relaxed text-muted-foreground">{body}</p>
                </Reveal>
              ))}
            </ul>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
