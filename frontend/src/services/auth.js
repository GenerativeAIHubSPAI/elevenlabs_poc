const COGNITO_DOMAIN = import.meta.env.VITE_COGNITO_DOMAIN;
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID;
const REDIRECT_URI =
  import.meta.env.VITE_COGNITO_REDIRECT_URI || window.location.origin + window.location.pathname;

const TOKEN_STORAGE_KEY = "voicecopilot_cognito_tokens";
const PKCE_STORAGE_KEY = "voicecopilot_pkce_verifier";

function base64UrlEncode(buffer) {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

async function sha256(value) {
  const data = new TextEncoder().encode(value);
  return crypto.subtle.digest("SHA-256", data);
}

function randomString(length = 64) {
  const charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~";
  const values = crypto.getRandomValues(new Uint8Array(length));

  return Array.from(values)
    .map((value) => charset[value % charset.length])
    .join("");
}

function decodeJwt(token) {
  const [, payload] = token.split(".");
  const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
  const json = decodeURIComponent(
    atob(normalized)
      .split("")
      .map((char) => `%${`00${char.charCodeAt(0).toString(16)}`.slice(-2)}`)
      .join("")
  );

  return JSON.parse(json);
}

export async function login() {
  const verifier = randomString();
  const challenge = base64UrlEncode(await sha256(verifier));

  sessionStorage.setItem(PKCE_STORAGE_KEY, verifier);

  const params = new URLSearchParams({
    response_type: "code",
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    scope: "openid email profile",
    code_challenge: challenge,
    code_challenge_method: "S256",
  });

  window.location.href = `${COGNITO_DOMAIN}/oauth2/authorize?${params.toString()}`;
}

export async function handleAuthCallback() {
  const url = new URL(window.location.href);
  const code = url.searchParams.get("code");

  if (!code) {
    return getStoredAuth();
  }

  const verifier = sessionStorage.getItem(PKCE_STORAGE_KEY);

  if (!verifier) {
    throw new Error("Missing PKCE verifier.");
  }

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: CLIENT_ID,
    code,
    redirect_uri: REDIRECT_URI,
    code_verifier: verifier,
  });

  const res = await fetch(`${COGNITO_DOMAIN}/oauth2/token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body,
  });

  if (!res.ok) {
    throw new Error(`Cognito token exchange failed: ${res.status}: ${await res.text()}`);
  }

  const tokens = await res.json();
  const claims = decodeJwt(tokens.id_token);

  const auth = {
    ...tokens,
    claims,
    userId: claims.sub,
    userName:
      claims.name ||
      [claims.given_name, claims.family_name].filter(Boolean).join(" ") ||
      claims.email ||
      "Authenticated user",
    email: claims.email,
  };

  localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(auth));
  sessionStorage.removeItem(PKCE_STORAGE_KEY);

  url.searchParams.delete("code");
  url.searchParams.delete("state");
  window.history.replaceState({}, document.title, url.pathname);

  return auth;
}

export function getStoredAuth() {
  const raw = localStorage.getItem(TOKEN_STORAGE_KEY);

  if (!raw) {
    return null;
  }

  try {
    const auth = JSON.parse(raw);
    const now = Math.floor(Date.now() / 1000);

    if (auth.claims?.exp && auth.claims.exp <= now) {
      logout(false);
      return null;
    }

    return auth;
  } catch {
    logout(false);
    return null;
  }
}

export function logout(redirect = true) {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  sessionStorage.removeItem(PKCE_STORAGE_KEY);

  if (!redirect) {
    return;
  }

  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    logout_uri: REDIRECT_URI,
  });

  window.location.href = `${COGNITO_DOMAIN}/logout?${params.toString()}`;
}