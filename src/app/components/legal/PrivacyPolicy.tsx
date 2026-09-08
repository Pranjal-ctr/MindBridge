/**
 * Privacy Policy — DRAFT, pending legal review.
 *
 * Written to describe accurately what the Kio codebase actually does with data,
 * so that a lawyer reviewing it is correcting the law rather than discovering
 * the system. Every claim below corresponds to real behaviour:
 *   - conversation privacy from parents:  app/parents/service.py returns
 *     aggregated insights only; there is no endpoint exposing message text to a
 *     parent role.
 *   - counselor access:                   app/risk/ + the counselor dashboard.
 *   - break-glass:                        app/admin/service.py, audit-logged.
 *   - crisis notifications:               app/intelligence/crisis.py.
 *
 * If any of those change, this document is wrong and must change with them.
 */

import { PRIVACY_VERSION } from '../../../lib/policy';
import { PolicyLayout, Section } from './PolicyLayout';

export function PrivacyPolicy() {
  return (
    <PolicyLayout title="Privacy Policy" version={PRIVACY_VERSION}>
      <p className="text-muted-foreground">
        Kio is a wellbeing companion used mostly by students under 18. This page
        explains what we collect, who can see it, and what you can ask us to do
        about it.
      </p>

      <Section heading="What we collect">
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Account details</strong> — name, email, mobile number, date of
            birth, school code, and your role.
          </li>
          <li>
            <strong>What you tell Kio</strong> — your conversations with Comrade,
            daily check-ins, reflections, journal entries, and goals.
          </li>
          <li>
            <strong>What Kio infers</strong> — a wellness score, mood and emotion
            trends, likely sources of stress, and a risk level. These are
            algorithmic estimates, not clinical assessments.
          </li>
          <li>
            <strong>Technical records</strong> — sign-in times, IP address and
            browser when you consent or perform sensitive actions, and audit logs of
            staff access.
          </li>
        </ul>
      </Section>

      <Section heading="Who can see your conversations">
        <p>
          This is the part most people want to know, so it is stated plainly.
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Your parent or guardian cannot read your conversations.</strong>{' '}
            They see wellbeing insights — mood trends, general stress areas,
            suggestions for supporting you — never the messages themselves.
          </li>
          <li>
            <strong>Your school cannot read your conversations.</strong> School
            administrators only ever see whole-school aggregates, and only when the
            school is large enough that a figure cannot identify an individual.
          </li>
          <li>
            <strong>A counselor can see a safety assessment about you</strong> — the
            risk level, the categories that contributed, and an AI-written summary —
            when Kio flags a concern.
          </li>
          <li>
            <strong>Kio staff can access conversations only through a
            &ldquo;break-glass&rdquo; process</strong> that records who looked, at
            what, and when. That record cannot be edited or deleted.
          </li>
        </ul>
      </Section>

      <Section heading="When we break confidentiality">
        <p>
          If Kio detects a serious risk to your safety, we alert a trained
          counselor at your school and notify your parent or guardian that
          something needs attention. The notification to a parent does not include
          what you said or why it was flagged.
        </p>
        <p>
          We would rather tell you this clearly than have you discover it later.
        </p>
      </Section>

      <Section heading="Automated processing">
        <p>
          Kio uses AI to generate replies, summarise conversations, estimate a
          wellness score, and detect possible risk. These outputs can be wrong.
          They are not a diagnosis, and no decision about you is made by the system
          alone — a human counselor reviews every safety flag and records their own
          judgment.
        </p>
      </Section>

      <Section heading="If you are under 18">
        <p>
          We ask for your date of birth when you sign up. If you are under 13 we
          cannot give you an account. If you are between 13 and 17, we ask a parent
          or guardian to approve your account by email before you can use it, and
          we keep a record of that approval.
        </p>
      </Section>

      <Section heading="Where your data goes">
        <p>
          Your messages are sent to our AI provider to generate a reply. We do not
          sell personal data, and we do not use it for advertising. Data is stored
          in an encrypted database with access limited to the roles described
          above.
        </p>
      </Section>

      <Section heading="How long we keep it">
        <p>
          Account and conversation data is retained while the account is active.
          Safety and audit records are retained longer, because they exist to be
          reviewable after the fact.{' '}
          <em>
            Specific retention periods are still to be set with legal counsel and
            will be stated here before launch.
          </em>
        </p>
      </Section>

      <Section heading="Your choices">
        <ul className="list-disc space-y-1 pl-5">
          <li>Ask for a copy of your data.</li>
          <li>Ask us to correct something wrong.</li>
          <li>Ask us to delete your account.</li>
          <li>Withdraw consent — this ends your use of Kio.</li>
        </ul>
        <p>
          <em>
            A contact address and response timeframe will be added here before
            launch.
          </em>
        </p>
      </Section>

      <Section heading="Kio is not a medical service">
        <p>
          Kio does not diagnose, treat, or provide emergency care. If you are in
          immediate danger, contact your local emergency services or a crisis
          helpline right away.
        </p>
      </Section>
    </PolicyLayout>
  );
}
