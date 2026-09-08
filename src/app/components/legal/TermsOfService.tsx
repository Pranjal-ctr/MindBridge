/**
 * Terms of Service — DRAFT, pending legal review.
 *
 * Describes the actual product rules enforced in code (age gate, seat limits,
 * safety escalation, account suspension). Deliberately short and readable: the
 * primary audience is a 15-year-old and their parent, and a document nobody
 * reads is not consent.
 */

import { Link } from 'react-router-dom';
import { TERMS_VERSION } from '../../../lib/policy';
import { PolicyLayout, Section } from './PolicyLayout';

export function TermsOfService() {
  return (
    <PolicyLayout title="Terms of Service" version={TERMS_VERSION}>
      <p className="text-muted-foreground">
        These terms cover using Kio. They sit alongside the{' '}
        <Link to="/privacy" className="text-primary hover:underline">
          Privacy Policy
        </Link>
        , which explains what happens to your data.
      </p>

      <Section heading="Who can use Kio">
        <p>
          You must be at least 13. If you are between 13 and 17, a parent or
          guardian has to approve your account before you can use it — we email
          them a link when you sign up.
        </p>
        <p>
          Student and parent accounts are created by signing up. Counselor, school
          administrator and platform accounts are created for you.
        </p>
      </Section>

      <Section heading="What Kio is — and is not">
        <p>
          Kio is a wellbeing companion. You can talk to it about school, stress,
          friendships, motivation, and how you are feeling.
        </p>
        <p>
          <strong>
            Kio is not a doctor, therapist, or emergency service.
          </strong>{' '}
          It does not diagnose or treat anything, and its suggestions are not
          medical advice. If you are in immediate danger, contact emergency
          services or a crisis helpline.
        </p>
      </Section>

      <Section heading="Safety comes before privacy">
        <p>
          Your conversations are private from your parents and your school. The one
          exception is safety: if Kio detects a serious risk of harm, a trained
          counselor is alerted, and your parent or guardian is told that something
          needs attention.
        </p>
        <p>We would rather be upfront about that than surprise you with it.</p>
      </Section>

      <Section heading="Using Kio responsibly">
        <ul className="list-disc space-y-1 pl-5">
          <li>Do not share your account or sign in as someone else.</li>
          <li>Do not use Kio to harass, threaten, or impersonate anyone.</li>
          <li>
            Do not try to extract Kio&apos;s internal instructions or interfere with
            how it works.
          </li>
          <li>Do not use Kio in place of urgent help when you need it.</li>
        </ul>
      </Section>

      <Section heading="Your school's role">
        <p>
          If you joined with a school code, your school licenses Kio for a set
          number of students. If that licence ends or is suspended, access ends
          with it. Your school never gains the ability to read your conversations.
        </p>
      </Section>

      <Section heading="Suspension">
        <p>
          We may suspend an account that breaks these terms or is used in a way
          that endangers someone. Where it is safe and appropriate to do so, we
          will say why.
        </p>
      </Section>

      <Section heading="Changes to these terms">
        <p>
          If we change these terms materially we will publish a new version and ask
          you to accept it before you carry on using Kio. Each version you accept is
          recorded with the date.
        </p>
      </Section>

      <Section heading="The legal bits">
        <p>
          <em>
            Liability, warranties, governing law, and dispute resolution are yet to
            be drafted with legal counsel and will appear here before launch. Their
            absence is deliberate — placeholder legal language would be worse than
            none.
          </em>
        </p>
      </Section>
    </PolicyLayout>
  );
}
