// Cognito email OTP (§C4) by direct fetch, no AWS SDK.
//
// InitiateAuth and RespondToAuthChallenge are unsigned, public operations,
// so they need no credentials and no SigV4. Pulling in the SDK for two POSTs
// would cost more bundle than the rest of the app.

const REGION = import.meta.env.VITE_AWS_REGION
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID
const TOKEN_KEY = 'splitly.id_token'
// 30 days (infra/cognito.tf). Kept in localStorage — acceptable for four
// known users (§C20, §T11.6).
const REFRESH_KEY = 'splitly.refresh_token'
const EMAIL_KEY = 'splitly.email'

// §V19 — the pool is case-sensitive, so every email is normalised (B7).
const normal = (email) => email.trim().toLowerCase()

async function idp(target, body) {
  const response = await fetch(`https://cognito-idp.${REGION}.amazonaws.com/`, {
    method: 'POST',
    headers: {
      'content-type': 'application/x-amz-json-1.1',
      'x-amz-target': `AWSCognitoIdentityProviderService.${target}`,
    },
    body: JSON.stringify(body),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.message || `${target} failed`)
  return data
}

export async function requestCode(email) {
  const data = await idp('InitiateAuth', {
    AuthFlow: 'USER_AUTH',
    ClientId: CLIENT_ID,
    AuthParameters: { USERNAME: normal(email), PREFERRED_CHALLENGE: 'EMAIL_OTP' },
  })
  return data.Session
}

export async function submitCode(email, code, session) {
  const data = await idp('RespondToAuthChallenge', {
    ChallengeName: 'EMAIL_OTP',
    ClientId: CLIENT_ID,
    Session: session,
    ChallengeResponses: { USERNAME: normal(email), EMAIL_OTP_CODE: code },
  })
  const token = data.AuthenticationResult?.IdToken
  if (!token) throw new Error('no token returned')
  write(TOKEN_KEY, token)
  write(REFRESH_KEY, data.AuthenticationResult.RefreshToken)
  write(EMAIL_KEY, normal(email))
  return token
}

// One refresh at a time: requests that expire together share it.
let refreshing = null

export function refreshSession() {
  refreshing ??= (async () => {
    const refreshToken = read(REFRESH_KEY)
    if (!refreshToken) throw new Error('no session to refresh')
    const data = await idp('InitiateAuth', {
      AuthFlow: 'REFRESH_TOKEN_AUTH',
      ClientId: CLIENT_ID,
      AuthParameters: { REFRESH_TOKEN: refreshToken },
    })
    const token = data.AuthenticationResult?.IdToken
    if (!token) throw new Error('no token returned')
    write(TOKEN_KEY, token)
    return token
  })().finally(() => {
    refreshing = null
  })
  return refreshing
}

export const lastEmail = () => read(EMAIL_KEY) ?? ''

// Storage can throw in private mode or with site data blocked, so every
// access is guarded and an unreadable store simply means signed out.
function read(key) {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key, value) {
  try {
    if (value) localStorage.setItem(key, value)
  } catch {
    /* signed in for this page load only */
  }
}

export const getToken = () => read(TOKEN_KEY)

// §V22 — every credential. The email stays: it is a convenience, not a key.
export function signOut() {
  for (const key of [TOKEN_KEY, REFRESH_KEY]) {
    try {
      localStorage.removeItem(key)
    } catch {
      /* nothing to clear */
    }
  }
}
