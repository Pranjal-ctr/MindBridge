/**
 * Non-diagnostic disclaimer shown across the product. Single source of truth
 * for the wording so it stays consistent everywhere (login, student, parent,
 * counselor, school). `full` for prominent placements, `short` for footers.
 */

import { Info } from 'lucide-react';

export const DISCLAIMER_TEXT =
  'Kio is an AI wellbeing support platform. It assists students, parents, counselors, and schools by ' +
  'identifying wellbeing patterns and potential areas of concern. It does not provide medical or ' +
  'psychological diagnoses and should not replace qualified professional care.';

export const DISCLAIMER_SHORT =
  'Kio provides AI wellbeing support — not a medical or psychological diagnosis — and does not replace professional care.';

export function Disclaimer({
  variant = 'full',
  className = '',
}: {
  variant?: 'full' | 'short';
  className?: string;
}) {
  const text = variant === 'short' ? DISCLAIMER_SHORT : DISCLAIMER_TEXT;
  return (
    <div className={`flex items-start gap-2 text-xs text-muted-foreground ${className}`}>
      <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
      <span>{text}</span>
    </div>
  );
}
