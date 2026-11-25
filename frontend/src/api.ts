// Backend base URL. By default the app calls /api/... on its own origin. In development, Vite forwards /api
// to the API. In the preview, scripts/serve_preview.py serves the built app and forwards /api the same way.
// Set VITE_API_URL at build time only when the API is on a different host (no trailing slash).
export const API_URL: string = ((import.meta.env.VITE_API_URL as string) || '').trim().replace(/\/$/, '');

const TOKEN_KEY = 'healthu_token';
export const SESSION_EXPIRED_EVENT = 'healthu:session-expired';

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

// Some browsers block or clear localStorage (private mode, strict privacy settings). The token is also kept
// in memory so the signed-in session still works for this page; a reload then asks for sign-in again.
let memoryToken: string | null = null;

export function getToken(): string | null {
  try {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (stored) return stored;
  } catch {
    /* storage blocked: fall back to memory */
  }
  return memoryToken;
}

export function setToken(token: string | null): void {
  memoryToken = token;
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage blocked: the in-memory token above still holds */
  }
}

function authHeader(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

function errorMessage(json: any, status: number): string {
  const detail = json?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    const field = Array.isArray(first?.loc) ? String(first.loc[first.loc.length - 1]) : '';
    return `Please check the "${field || 'input'}" field.`;
  }
  return `Request failed (${status}).`;
}

async function handle<T>(res: Response, sentToken: string | null = null): Promise<T> {
  let json: any = null;
  try {
    json = await res.json();
  } catch {
    json = null;
  }
  if (!res.ok) {
    // Only the server's own token check ends the session, and only for the token that is still saved.
    // A late reply to an older token must not sign out a newer sign-in.
    const stillCurrent = sentToken !== null && sentToken === getToken();
    if (res.status === 401 && stillCurrent && json?.detail === 'Please sign in again.') {
      setToken(null);
      window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT, { detail: res.headers.get('X-Auth-Reason') || '' }));
    }
    throw new ApiError(errorMessage(json, res.status), res.status);
  }
  return json as T;
}

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const sent = getToken();
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...authHeader() },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError('Could not reach the Health-U server. Check your connection and that the API is running.', 0);
  }
  return handle<T>(res, sent);
}

export const postJSON = <T = any>(path: string, body: unknown): Promise<T> => send<T>('POST', path, body);
export const getJSON = <T = any>(path: string): Promise<T> => send<T>('GET', path);
export const deleteRequest = (path: string): Promise<void> => send<void>('DELETE', path);

export async function uploadFile<T = any>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append('file', file);
  const sent = getToken();
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method: 'POST', headers: authHeader(), body: form });
  } catch {
    throw new ApiError('Could not reach the Health-U server. Please try again.', 0);
  }
  return handle<T>(res, sent);
}

/** Downloads a file that needs the bearer token. Plain links cannot send headers. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const sent = getToken();
  const res = await fetch(`${API_URL}${path}`, { headers: authHeader() });
  if (!res.ok) {
    await handle(res, sent);
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
