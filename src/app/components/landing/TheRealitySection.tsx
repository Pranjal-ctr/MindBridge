/**
 * "The Reality" — the first beat of the landing-page story.
 *
 * The photograph is a real <img> (not a background) so it can crop
 * responsively; the framing, the glow and the organic shape are CSS. The
 * handwritten quote baked into the top-left of the reference asset was painted
 * out before the asset was exported — that line is copy, and copy belongs in
 * text where it can be read, translated and selected. What remains in the
 * frame ("Every Story Matters" on the board, "You Matter" on the pencil case)
 * is part of the scene, not an overlay.
 *
 * The five stakeholder lines are the section's substance, so they are real
 * text in a real list — never an image of a list.
 */

import { GraduationCap, HeartHandshake, Home, LifeBuoy, School } from 'lucide-react';
import { Reveal } from './Reveal';
import { SectionLabel } from './SectionLabel';

/**
 * Who sees what. Kept factual: the only claim made about Kio is the one the
 * product actually supports — noticing earlier — and never preventing,
 * guaranteeing or diagnosing.
 */
const PERSPECTIVES = [
  {
    icon: HeartHandshake,
    label: 'Students',
    body: 'Carry stress, anxiety, bullying and low confidence — often quietly, and often alone.',
    tint: 'bg-violet-50 text-violet-600 ring-violet-100',
  },
  {
    icon: GraduationCap,
    label: 'Teachers',
    body: "Care deeply, but can't watch every child, every day.",
    tint: 'bg-sky-50 text-sky-600 ring-sky-100',
  },
  {
    icon: Home,
    label: 'Parents',
    body: 'Often find out only when it is already too late.',
    tint: 'bg-amber-50 text-amber-600 ring-amber-100',
  },
  {
    icon: LifeBuoy,
    label: 'Counselors',
    body: 'Step in once a crisis has already begun.',
    tint: 'bg-rose-50 text-rose-600 ring-rose-100',
  },
  {
    icon: School,
    label: 'Schools',
    body: 'Often react to problems. Kio helps them notice earlier.',
    tint: 'bg-teal-50 text-teal-600 ring-teal-100',
  },
];

export function TheRealitySection() {
  return (
    <section
      id="reality"
      aria-labelledby="reality-heading"
      className="relative overflow-hidden bg-white scroll-mt-20 py-16 md:py-20"
    >
      {/* Decorative atmosphere. aria-hidden and pointer-events-none so it can
          never sit between a reader and the content. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-32 top-10 h-80 w-80 rounded-full bg-violet-200/30 blur-3xl animate-kio-drift" />
        <div className="absolute -right-24 bottom-0 h-96 w-96 rounded-full bg-teal-100/40 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <Reveal className="mx-auto max-w-3xl text-center">
          <SectionLabel>The reality</SectionLabel>
          <h2
            id="reality-heading"
            className="mt-6 text-[2.25rem] font-bold leading-[1.15] text-foreground sm:text-4xl md:text-5xl"
          >
            Every child has a story.
            <span className="block text-secondary">Not every story is visible.</span>
          </h2>
          <p className="mx-auto mt-5 max-w-2xl text-xl leading-relaxed text-muted-foreground">
            Behind every smile, there might be a silent struggle — and the most important things
            are often the easiest to miss.
          </p>
        </Reveal>

        <div className="mt-10 grid items-center gap-10 lg:mt-14 lg:grid-cols-2 lg:gap-14">
          {/* Photograph */}
          <Reveal from="left" className="relative">
            <div
              aria-hidden
              className="pointer-events-none absolute -inset-6 rounded-[3rem] bg-gradient-to-br from-violet-200/50 via-indigo-100/40 to-teal-100/40 blur-2xl"
            />
            <div className="relative overflow-hidden rounded-[2rem] shadow-[0_24px_60px_-20px_rgba(35,43,109,0.35)] ring-1 ring-black/5 md:rounded-[5rem_2rem_5rem_2rem]">
              <img
                src="/landing/reality-classroom.webp"
                alt="A school student resting her head on her folded arms at her desk, looking down, while her classmates work behind her."
                width={1400}
                height={933}
                loading="lazy"
                decoding="async"
                className="aspect-[4/3] w-full object-cover object-[60%_center]"
              />
              <div
                aria-hidden
                className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-[#232B6D]/45 to-transparent"
              />
              <p className="absolute bottom-6 left-6 right-6 font-handwritten text-3xl leading-snug text-white drop-shadow-sm sm:text-4xl">
                Every story matters.
              </p>
            </div>
          </Reveal>

          {/* Who sees what */}
          <Reveal from="right">
            <p className="mb-5 text-2xl font-semibold leading-snug text-foreground">
              Everyone sees a different part of it.
            </p>
            <ul className="space-y-2.5">
              {PERSPECTIVES.map(({ icon: Icon, label, body, tint }, index) => (
                <Reveal as="li" key={label} delay={index * 70}>
                  <div className="group flex items-start gap-4 rounded-2xl border border-border/70 bg-white/80 p-4 shadow-sm backdrop-blur-sm transition duration-300 hover:-translate-y-0.5 hover:border-transparent hover:shadow-lg sm:gap-5 sm:p-5">
                    <span
                      className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl ring-1 ${tint}`}
                    >
                      <Icon className="h-[1.35rem] w-[1.35rem]" aria-hidden />
                    </span>
                    <div className="min-w-0">
                      <h3 className="text-[1.0625rem] font-semibold text-foreground">{label}</h3>
                      <p className="mt-1 text-[0.9375rem] leading-relaxed text-muted-foreground">
                        {body}
                      </p>
                    </div>
                  </div>
                </Reveal>
              ))}
            </ul>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
