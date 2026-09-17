/**
 * "Why Kio" — the difference between talking to an assistant and being known
 * by one.
 *
 * Framed as a contrast, not an attack: general-purpose AI is genuinely useful,
 * it simply has no reason to remember a student or to know who at their school
 * could help. Every line on the Kio side maps to something the product
 * actually ships (onboarding-personalised prompts, memory, journal and growth,
 * the counselor booking path and the risk queue). Nothing here claims
 * diagnosis, treatment, prevention or a guarantee — and the shared
 * non-diagnostic disclaimer is reused rather than reworded.
 */

import { Check, Minus } from 'lucide-react';
import { Disclaimer } from '../Disclaimer';
import { KioLogo } from '../KioLogo';
import { Reveal } from './Reveal';
import { SectionLabel } from './SectionLabel';

const GENERAL_AI = [
  'A conversation',
  'General responses',
  'Limited context about the student',
  "Separate from the school's support system",
];

const KIO = [
  'Support personalised to the student',
  'Continuity and reflection over time',
  "Connected to the school's support ecosystem",
  'Can connect students to human support',
];

export function WhyKioSection() {
  return (
    <section
      id="why-kio"
      aria-labelledby="why-kio-heading"
      className="relative overflow-hidden bg-white scroll-mt-20 py-16 md:py-20"
    >
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -right-32 top-1/3 h-80 w-80 rounded-full bg-teal-100/40 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <Reveal className="mx-auto max-w-3xl text-center">
          <SectionLabel>Why Kio</SectionLabel>
          <h2
            id="why-kio-heading"
            className="mt-6 text-[2.25rem] font-bold leading-[1.15] text-foreground sm:text-4xl md:text-5xl"
          >
            Give those conversations a place to belong.
          </h2>
          <p className="mx-auto mt-5 max-w-2xl text-xl leading-relaxed text-muted-foreground">
            A general assistant answers the question in front of it. Kio remembers the student
            asking it — and knows who at their school can help.
          </p>
        </Reveal>

        <div className="relative mt-10 grid gap-6 md:grid-cols-2 md:gap-8 lg:mt-12">
          {/* General AI */}
          <Reveal from="left">
            <div className="h-full rounded-3xl border border-border bg-muted/40 p-6 sm:p-8">
              <h3 className="text-xl font-semibold text-muted-foreground">A general AI assistant</h3>
              <ul className="mt-5 space-y-3.5">
                {GENERAL_AI.map((item) => (
                  <li key={item} className="flex items-start gap-3">
                    <span className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-200/70">
                      <Minus className="h-3.5 w-3.5 text-slate-500" aria-hidden />
                    </span>
                    <span className="text-[1.0625rem] leading-relaxed text-muted-foreground">
                      {item}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>

          {/* Divider — decorative on desktop, hidden on stacked layouts. */}
          <div
            aria-hidden
            className="pointer-events-none absolute left-1/2 top-1/2 z-10 hidden -translate-x-1/2 -translate-y-1/2 md:block"
          >
            <span className="flex h-12 w-12 items-center justify-center rounded-full border border-border bg-white text-xs font-semibold uppercase tracking-wide text-muted-foreground shadow-md">
              vs
            </span>
          </div>

          {/* Kio */}
          <Reveal from="right">
            <div className="relative h-full overflow-hidden rounded-3xl bg-gradient-to-br from-[#232B6D] via-[#3A45A8] to-[#5A6BFF] p-6 text-white shadow-[0_24px_60px_-24px_rgba(35,43,109,0.65)] sm:p-8">
              <div
                aria-hidden
                className="pointer-events-none absolute -right-16 -top-16 h-52 w-52 rounded-full bg-[#31D7C2]/25 blur-3xl"
              />
              <div className="relative">
                <KioLogo className="h-7 w-auto" reverse />
                <ul className="mt-5 space-y-3.5">
                  {KIO.map((item) => (
                    <li key={item} className="flex items-start gap-3">
                      <span className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#31D7C2]/25">
                        <Check className="h-3.5 w-3.5 text-[#31D7C2]" aria-hidden />
                      </span>
                      <span className="text-[1.0625rem] font-medium leading-relaxed text-white/95">
                        {item}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </Reveal>
        </div>

        <Reveal className="mx-auto mt-8 max-w-2xl">
          <Disclaimer variant="short" className="justify-center text-center" />
        </Reveal>
      </div>
    </section>
  );
}
