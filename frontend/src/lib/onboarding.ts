// Client-side "skip onboarding" escape hatch.
//
// `GET /onboarding/status` derives `completed` purely from profile data — there
// is deliberately no stored flag and no endpoint to set one (see
// api/routers/onboarding.py), so nothing can drift out of sync with reality.
// The tradeoff is that "skip for now" has nowhere to live server-side, so it
// lives here: it suppresses the redirect guard on this browser only, and stops
// mattering entirely once a real profile exists.

const KEY = "onboarding.skipped";

export function isOnboardingSkipped(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false; // private mode / storage disabled — just show the wizard
  }
}

export function markOnboardingSkipped(): void {
  try {
    localStorage.setItem(KEY, "1");
  } catch {
    /* non-fatal: the guard simply keeps prompting */
  }
}
