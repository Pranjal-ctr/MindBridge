/**
 * "The Shift" — students are already turning to AI.
 *
 * The reference artwork had the six question bubbles baked into the image.
 * They are rendered here as real text instead: an image of a sentence cannot
 * be read by a screen reader, selected, translated, or reflowed on a phone.
 * The exported asset is the figure and Kio only; everything around it is HTML.
 *
 * The composition follows the reference — bubbles scattered around the student
 * at uneven heights and widths, each with a tail pointing back at her, rather
 * than two tidy columns. On large screens that is absolute positioning inside a
 * fixed-ratio stage; below `lg` the same bubbles reflow into a plain grid,
 * because scattering them on a 375px screen is how you get overlap and
 * horizontal scroll.
 */

import { BookOpen, Briefcase, CloudRain, Handshake, HeartCrack, Users } from 'lucide-react';
import { Reveal } from './Reveal';
import { SectionLabel } from './SectionLabel';

interface Question {
  icon: typeof BookOpen;
  text: string;
  /** Bubble fill + icon colour. Solid, so the tail can match exactly. */
  surface: string;
  icon_color: string;
  /**
   * Absolute placement on the desktop stage. The left column is anchored by
   * its *right* edge and the right column by its *left* edge -- the edge
   * facing the student. The bubbles shrink-wrap their text, so anchoring the
   * outer edge instead would leave a different gap beside her for every
   * question, and the ring would fall apart.
   *
   * The three rows sit progressively further out: nothing is beside her at
   * the top, only her hair at the middle, and her arms and crossed legs at
   * the bottom. Following that outline is what reads as surrounded rather
   * than as two columns.
   */
  pos: string;
  side: 'left' | 'right';
}

const QUESTIONS: Question[] = [
  {
    icon: BookOpen,
    text: "I'm so stressed about exams.",
    surface: 'bg-violet-50',
    icon_color: 'text-violet-600',
    pos: 'lg:right-[54%] lg:top-0 lg:w-auto lg:max-w-[21rem]',
    side: 'left',
  },
  {
    icon: CloudRain,
    text: 'Why do I always feel anxious?',
    surface: 'bg-teal-50',
    icon_color: 'text-teal-600',
    pos: 'lg:right-[64%] lg:top-[28%] lg:w-auto lg:max-w-[19.5rem]',
    side: 'left',
  },
  {
    icon: HeartCrack,
    text: 'I feel lonely.',
    surface: 'bg-amber-50',
    icon_color: 'text-amber-600',
    pos: 'lg:right-[67%] lg:top-[60%] lg:w-auto lg:max-w-[15rem]',
    side: 'left',
  },
  {
    icon: Users,
    text: "My parents don't understand me.",
    surface: 'bg-emerald-50',
    icon_color: 'text-emerald-600',
    pos: 'lg:left-[54%] lg:top-[2%] lg:w-auto lg:max-w-[20.5rem]',
    side: 'right',
  },
  {
    icon: Handshake,
    text: 'How do I deal with friendship problems?',
    surface: 'bg-orange-50',
    icon_color: 'text-orange-600',
    pos: 'lg:left-[57%] lg:top-[30%] lg:w-auto lg:max-w-[21rem]',
    side: 'right',
  },
  {
    icon: Briefcase,
    text: 'Which career path is right for me?',
    surface: 'bg-sky-50',
    icon_color: 'text-sky-600',
    pos: 'lg:left-[66%] lg:top-[62%] lg:w-auto lg:max-w-[18.5rem]',
    side: 'right',
  },
];

function Bubble({ question, index }: { question: Question; index: number }) {
  const { icon: Icon, text, surface, icon_color, pos, side } = question;

  // The corner nearest the student is squared off and a tail sits under it, so
  // each bubble reads as coming from her rather than floating loose.
  const shape =
    side === 'left'
      ? 'rounded-[1.75rem_1.75rem_0.25rem_1.75rem]'
      : 'rounded-[1.75rem_1.75rem_1.75rem_0.25rem]';
  const tail = side === 'left' ? 'right-3 -bottom-1.5' : 'left-3 -bottom-1.5';

  return (
    <Reveal
      as="li"
      delay={index * 110}
      from={side}
      className={`relative lg:absolute ${pos}`}
    >
      <div
        className={`relative flex items-center gap-3 px-5 py-4 shadow-[0_14px_36px_-14px_rgba(35,43,109,0.3)] ring-1 ring-black/[0.04] transition duration-300 hover:-translate-y-1 hover:shadow-[0_20px_44px_-14px_rgba(35,43,109,0.38)] ${shape} ${surface}`}
      >
        <Icon className={`h-[1.35rem] w-[1.35rem] shrink-0 ${icon_color}`} aria-hidden />
        <span className="text-[1.0625rem] font-medium leading-snug text-foreground">{text}</span>
        <span
          aria-hidden
          className={`absolute hidden h-4 w-4 rotate-45 rounded-[3px] lg:block ${tail} ${surface}`}
        />
      </div>
    </Reveal>
  );
}

export function TheShiftSection() {
  return (
    <section
      id="the-shift"
      aria-labelledby="shift-heading"
      className="relative overflow-hidden bg-gradient-to-b from-white via-[#F8F7FE] to-white scroll-mt-20 py-16 md:py-20"
    >
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-24 h-[30rem] w-[30rem] -translate-x-1/2 rounded-full bg-violet-200/25 blur-3xl animate-kio-drift" />
      </div>

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <Reveal className="mx-auto max-w-3xl text-center">
          <SectionLabel>The shift</SectionLabel>
          <h2
            id="shift-heading"
            className="mt-6 text-[2.25rem] font-bold leading-[1.15] text-foreground sm:text-4xl md:text-5xl"
          >
            Students are already turning to AI.
          </h2>
          <p className="mx-auto mt-5 max-w-2xl text-xl leading-relaxed text-muted-foreground">
            Before schools notice, students are already asking AI the questions they find hard to
            say out loud.
          </p>
        </Reveal>

        {/* The stage. Absolute below `lg` is off; the list simply flows.
            Narrower than the section so the ring closes around her instead
            of stranding each bubble against the page edge. */}
        <div className="relative mx-auto mt-8 max-w-5xl lg:mt-10 lg:h-[34rem]">
          {/* Student + Kio, centred on the stage. */}
          <Reveal className="relative z-10 mb-8 flex justify-center lg:absolute lg:inset-x-0 lg:bottom-0 lg:mb-0">
            <div className="relative">
              {/* Halo behind the cut-out figure, in place of the background
                  the matte removed. */}
              <div
                aria-hidden
                className="pointer-events-none absolute -inset-x-8 bottom-4 top-12 rounded-[50%] bg-gradient-to-b from-violet-200/60 via-violet-100/45 to-teal-100/40 blur-3xl"
              />
              <img
                src="/landing/student-with-kio.webp"
                alt="An illustrated student sitting cross-legged with her phone, with Kio — a soft glowing companion — beside her."
                width={611}
                height={694}
                loading="lazy"
                decoding="async"
                className="relative w-[17rem] max-w-full sm:w-[20rem] lg:w-[20rem] xl:w-[23rem]"
              />
            </div>
          </Reveal>

          <ul className="grid gap-4 sm:grid-cols-2 lg:block">
            {QUESTIONS.map((question, index) => (
              <Bubble key={question.text} question={question} index={index} />
            ))}
          </ul>
        </div>

        <Reveal delay={80} className="mx-auto mt-10 max-w-3xl lg:mt-12">
          <p className="text-center text-xl font-medium leading-relaxed text-primary sm:text-2xl">
            The real question is whether those conversations can become part of a safer, more
            connected support system.
          </p>
        </Reveal>
      </div>
    </section>
  );
}
