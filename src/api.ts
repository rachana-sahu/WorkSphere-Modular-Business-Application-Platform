const CSRF_COOKIE_NAME = "worksphere_csrf";
const CSRF_HEADER_NAME = "X-CSRF-Token";
const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function readCookie(name: string): string | null {
  const cookie = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${name}=`));
  return cookie ? decodeURIComponent(cookie.slice(name.length + 1)) : null;
}

export function readCsrfToken(): string {
  return readCookie(CSRF_COOKIE_NAME) ?? "";
}

export function sessionFetch(
  input: RequestInfo | URL,
  options: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(options.headers);
  const method = (options.method ?? "GET").toUpperCase();
  if (UNSAFE_METHODS.has(method)) {
    const csrfToken = readCookie(CSRF_COOKIE_NAME);
    if (csrfToken) {
      headers.set(CSRF_HEADER_NAME, csrfToken);
    }
  }
  return fetch(input, {
    ...options,
    credentials: "same-origin",
    headers,
  });
}
