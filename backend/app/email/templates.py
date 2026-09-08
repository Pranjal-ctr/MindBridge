"""
Kio transactional email templates.

Each builder returns (subject, text_body, html_body). Plain text is always sent
alongside the HTML so the message stays readable in text-only clients and scores
better with spam filters.

Design notes for email HTML (deliberately not our web stack):
  - Inline styles only. Email clients strip <style> blocks and never load Tailwind.
  - No webfonts. Poppins/Inter won't load in most clients, so we use a system stack.
  - Kio brand colors from theme.css: navy #232B6D, blue #5A6BFF, teal #31D7C2.
"""

from __future__ import annotations

BRAND_NAVY = "#232B6D"
BRAND_BLUE = "#5A6BFF"
BRAND_TEAL = "#31D7C2"
TEXT_PRIMARY = "#111827"
TEXT_MUTED = "#6B7280"
SURFACE = "#F8FAFC"

_FONT_STACK = (
    "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif"
)


def _shell(*, heading: str, intro: str, cta_label: str, cta_url: str, outro: str) -> str:
    """Wrap a single call-to-action message in the shared Kio email chrome."""
    return f"""\
<div style="margin:0;padding:24px 12px;background:{SURFACE};font-family:{_FONT_STACK};">
  <div style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:12px;
              overflow:hidden;border:1px solid #E5E7EB;">
    <div style="background:{BRAND_NAVY};padding:20px 28px;">
      <span style="color:#ffffff;font-size:20px;font-weight:600;letter-spacing:-0.02em;">Kio</span>
      <span style="color:{BRAND_TEAL};font-size:20px;font-weight:600;">.</span>
    </div>
    <div style="padding:28px;">
      <h1 style="margin:0 0 12px;font-size:20px;line-height:1.35;color:{TEXT_PRIMARY};font-weight:600;">
        {heading}
      </h1>
      <p style="margin:0 0 24px;font-size:15px;line-height:1.6;color:{TEXT_MUTED};">
        {intro}
      </p>
      <a href="{cta_url}"
         style="display:inline-block;background:{BRAND_BLUE};color:#ffffff;text-decoration:none;
                font-size:15px;font-weight:600;padding:12px 24px;border-radius:8px;">
        {cta_label}
      </a>
      <p style="margin:24px 0 0;font-size:13px;line-height:1.6;color:{TEXT_MUTED};">
        {outro}
      </p>
      <p style="margin:16px 0 0;font-size:12px;line-height:1.6;color:{TEXT_MUTED};
                word-break:break-all;">
        If the button doesn't work, paste this link into your browser:<br />
        <span style="color:{BRAND_BLUE};">{cta_url}</span>
      </p>
    </div>
    <div style="padding:16px 28px;background:{SURFACE};border-top:1px solid #E5E7EB;">
      <p style="margin:0;font-size:12px;line-height:1.5;color:{TEXT_MUTED};">
        Kio — AI companion for student wellness and parenting guidance.<br />
        Kio is not a medical or diagnostic service and does not replace professional care.
      </p>
    </div>
  </div>
</div>"""


def verification_email(*, first_name: str, link: str, expires_hours: int) -> tuple[str, str, str]:
    """Email confirming a newly registered address."""
    greeting = f"Hi {first_name}," if first_name else "Hi,"
    subject = "Verify your email for Kio"

    text = f"""\
{greeting}

Welcome to Kio! Please confirm your email address to finish setting up your account.

Verify your email:
{link}

This link expires in {expires_hours} hours. If you didn't create a Kio account,
you can safely ignore this message.

— The Kio team
"""

    html = _shell(
        heading="Confirm your email address",
        intro=(
            f"{greeting} welcome to Kio. Confirm your email address to finish "
            "setting up your account."
        ),
        cta_label="Verify email",
        cta_url=link,
        outro=(
            f"This link expires in {expires_hours} hours. "
            "If you didn't create a Kio account, you can safely ignore this email."
        ),
    )
    return subject, text, html


def password_reset_email(*, first_name: str, link: str, expires_hours: int) -> tuple[str, str, str]:
    """Email carrying a one-time password reset link."""
    greeting = f"Hi {first_name}," if first_name else "Hi,"
    subject = "Reset your Kio password"
    window = "1 hour" if expires_hours == 1 else f"{expires_hours} hours"

    text = f"""\
{greeting}

We received a request to reset the password for your Kio account.

Reset your password:
{link}

This link expires in {window} and can only be used once. If you didn't request a
password reset, you can safely ignore this message — your password won't change.

— The Kio team
"""

    html = _shell(
        heading="Reset your password",
        intro=f"{greeting} we received a request to reset the password for your Kio account.",
        cta_label="Reset password",
        cta_url=link,
        outro=(
            f"This link expires in {window} and can only be used once. "
            "If you didn't request this, you can safely ignore this email — "
            "your password won't change."
        ),
    )
    return subject, text, html


def crisis_alert_email(
    *, staff_first_name: str, student_name: str, risk_level: str, link: str
) -> tuple[str, str, str]:
    """Alert a counselor or school admin that a student needs review.

    Deliberately content-free. It carries the student's name, the tier, and a
    link — never message text, risk categories, or the AI's summary. Email is
    the least controlled channel Kio uses: it forwards, it sits on phones on
    lock screens, and it lands in shared school inboxes. Anything sensitive
    stays behind the login, which is what the link is for.

    The subject deliberately omits the student's name for the same reason —
    a lock-screen preview shouldn't name a student in crisis.
    """
    greeting = f"Hi {staff_first_name}," if staff_first_name else "Hi,"
    tier = risk_level.capitalize()
    subject = "Kio: a student needs review"

    text = f"""\
{greeting}

A student in your school has been flagged for review by Kio.

Student: {student_name}
Risk level: {tier}

Open the risk queue to see the assessment and record your decision:
{link}

Details are intentionally not included in this email. Sign in to review.

If this student may be in immediate danger, follow your school's emergency
escalation procedure now — do not wait to review in Kio first.

— Kio
"""

    html = _shell(
        heading="A student needs review",
        intro=(
            f"{greeting} <strong>{student_name}</strong> has been flagged at "
            f"<strong>{tier}</strong> risk and is waiting in your review queue. "
            "Details are intentionally not included in this email — sign in to review."
        ),
        cta_label="Open risk queue",
        cta_url=link,
        outro=(
            "If this student may be in immediate danger, follow your school's "
            "emergency escalation procedure now — do not wait to review in Kio first."
        ),
    )
    return subject, text, html


def guardian_consent_email(
    *, guardian_name: str, student_name: str, link: str, expires_hours: int
) -> tuple[str, str, str]:
    """Ask a parent or guardian to approve a minor's Kio account.

    This email IS the verification step for a minor's account, so it has to be
    informative enough to make the consent meaningful: what Kio does, what the
    guardian will and will not be able to see, and that declining is a real
    option with a real consequence.

    Note the explicit privacy boundary. A guardian who expects to read their
    child's conversations and discovers otherwise later has not given informed
    consent, and the student loses a service they were told was private.
    """
    greeting = f"Hi {guardian_name}," if guardian_name else "Hello,"
    days = round(expires_hours / 24)
    window = f"{days} days" if days > 1 else f"{expires_hours} hours"
    subject = f"Approve {student_name}'s Kio account"

    text = f"""{greeting}

{student_name} has signed up for Kio and listed you as their parent or guardian.
Because they are under 18, we need your permission before their account can be
used.

What Kio is:
  A private AI companion students can talk to about school stress, friendships,
  motivation and how they are feeling. It is not a medical or diagnostic
  service and does not replace professional care.

What you will see:
  Wellness insights — mood trends, general areas of stress, and suggestions for
  supporting them.

What you will NOT see:
  Your child's actual conversations. Those stay private. That privacy is what
  makes students willing to be honest, which is what makes the support work.

  The exception is safety: if Kio detects a serious risk, a trained counselor
  is alerted and you receive a notification that something needs attention.

Approve or decline here:
{link}

This link expires in {window}. If you did not expect this email, you can ignore
it — no account will be activated without your approval.

— The Kio team
"""

    html = _shell(
        heading=f"Approve {student_name}'s Kio account",
        intro=(
            f"{greeting} <strong>{student_name}</strong> has signed up for Kio and listed "
            "you as their parent or guardian. Because they are under 18, we need your "
            "permission before their account can be used.<br /><br />"
            "Kio is a private AI companion for school stress, friendships and wellbeing. "
            "It is not a medical or diagnostic service.<br /><br />"
            "<strong>You will see</strong> wellness insights — mood trends, areas of "
            "stress, and ways to support them.<br />"
            "<strong>You will not see</strong> their actual conversations; those stay "
            "private, which is what makes students honest enough for the support to "
            "work. If Kio detects a serious risk, a trained counselor is alerted and you "
            "are notified that something needs attention."
        ),
        cta_label="Review and decide",
        cta_url=link,
        outro=(
            f"This link expires in {window}. If you did not expect this email you can "
            "ignore it — no account will be activated without your approval."
        ),
    )
    return subject, text, html
