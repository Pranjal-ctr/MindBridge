/**
 * Kio Consent API — age gate, policy acceptance, guardian approval.
 *
 * The guardian endpoints are intentionally unauthenticated: the person deciding
 * is a parent with no Kio account. Their authorisation is the signed token in
 * the emailed link.
 */

import api from './api';
import type {
  ConsentStatus,
  GuardianConsentContext,
  PolicyVersions,
} from './types';

/** Public — the signup screen needs these before anyone is authenticated. */
export async function getPolicyVersions(): Promise<PolicyVersions> {
  const { data } = await api.get<PolicyVersions>('/consent/policies');
  return data;
}

export async function getMyConsentStatus(): Promise<ConsentStatus> {
  const { data } = await api.get<ConsentStatus>('/consent/me');
  return data;
}

/** Accept the current policy versions (re-consent after a version bump). */
export async function acceptPolicies(): Promise<ConsentStatus> {
  const { data } = await api.post<ConsentStatus>('/consent/accept', {
    accept_terms: true,
    accept_privacy: true,
  });
  return data;
}

/** Email a guardian a link to approve or decline this account. */
export async function requestGuardianConsent(
  guardianEmail: string,
  guardianName?: string,
): Promise<void> {
  await api.post('/consent/guardian/request', {
    guardian_email: guardianEmail,
    ...(guardianName ? { guardian_name: guardianName } : {}),
  });
}

/** Resolve an emailed consent link into what the guardian needs to see. */
export async function getGuardianContext(
  token: string,
): Promise<GuardianConsentContext> {
  const { data } = await api.get<GuardianConsentContext>('/consent/guardian/context', {
    params: { token },
  });
  return data;
}

export async function decideGuardianConsent(
  token: string,
  granted: boolean,
): Promise<{ guardian_consent_status: string }> {
  const { data } = await api.post('/consent/guardian/decide', { token, granted });
  return data;
}
