/**
 * The small label above each landing-page section heading.
 *
 * Deliberately not a pill/chip: a coloured pill reads as a status badge, which
 * is UI furniture, and made "The reality" look like a tag on a ticket. This is
 * an editorial eyebrow instead — letterspaced small caps between two short
 * rules that fade out. It carries no interaction, so it is a <span>, not a
 * button-shaped thing.
 *
 * The text is solid navy rather than a gradient: at this size a gradient
 * running into the teal end of the brand ramp drops well under the 4.5:1 that
 * normal-size text needs. The colour lives in the two rules instead.
 */

export function SectionLabel({
  children,
  align = 'center',
  className = '',
}: {
  children: string;
  align?: 'center' | 'left';
  className?: string;
}) {
  return (
    <span
      className={`flex items-center gap-3 ${align === 'center' ? 'justify-center' : 'justify-start'} ${className}`}
    >
      {align === 'center' && (
        <span
          aria-hidden
          className="h-px w-8 bg-gradient-to-r from-transparent to-secondary/45 sm:w-12"
        />
      )}
      <span className="text-[0.8125rem] font-semibold uppercase tracking-[0.22em] text-primary">
        {children}
      </span>
      <span
        aria-hidden
        className="h-px w-8 bg-gradient-to-l from-transparent to-accent/55 sm:w-12"
      />
    </span>
  );
}
