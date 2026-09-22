// Cognito email OTP (§C4) by direct fetch, no AWS SDK.
//
// InitiateAuth and RespondToAuthChallenge are unsigned, public operations,
// so they need no credentials and no SigV4. Pulling in the SDK for two POSTs
// would cost more bundle than the rest of the app.

const REGION = import.meta.env.VITE_AWS_REGION
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID
const TOKEN_KEY = 'splitly.id_token'

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
    AuthParameters: { USERNAME: email, PREFERRED_CHALLENGE: 'EMAIL_OTP' },
  })
  return data.Session
}

export async function submitCode(email, code, session) {
  const data = await idp('RespondToAuthChallenge', {
    ChallengeName: 'EMAIL_OTP',
    ClientId: CLIENT_ID,
    Session: session,
    ChallengeResponses: { USERNAME: email, EMAIL_OTP_CODE: code },
  })
  const token = data.AuthenticationResult?.IdToken
  if (!token) throw new Error('no token returned')
  setToken(token)
  return token
}

// Storage can throw in private mode or with site data blocked, so every
// access is guarded and an unreadable store simply means signed out.
export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

function setToken(token) {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    /* signed in for this page load only */
  }
}

export function signOut() {
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* nothing to clear */
  }
}
