import keycloak from "https://cdn.jsdelivr.net/npm/keycloak-js@26.2.3/+esm";

/* ---------- Cookie helpers (always set path=/) ---------- */

/**
 * Deletes all cookies for the current domain by setting their expiration
 * date to a past date. Includes the `path=/` attribute so that the deletion
 * applies to the entire domain, not just the current path.
 */
const deleteAllCookies = () => {
  document.cookie.split(';').forEach(cookie => {
    const eqPos = cookie.indexOf('=');
    const name = eqPos > -1 ? cookie.substring(0, eqPos).trim() : cookie.trim();

    document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/`;
  });
};

/**
 * Sets a cookie with a given name, value, and optional expiration date.
 * Automatically encodes the value and sets `path=/` so the cookie is
 * available across all paths on the domain.
 *
 * @param {string} name       - The name of the cookie.
 * @param {string} value      - The value to store; will be URI-encoded.
 * @param {string} [expiresUTC] - Optional expiration date in UTC string format
 *                                (e.g., the result of `Date.toUTCString()`).
 */
const setCookie = (name, value, expiresUTC) => {
  let cookieString = `${name}=${encodeURIComponent(value)};path=/`;

  if (expiresUTC) {
    cookieString += `;expires=${expiresUTC}`;
  }

  document.cookie = cookieString;
};

/**
 * Retrieves the value of a cookie by name.
 *
 * @param {string} name - The cookie name to look up.
 * @returns {string} The decoded cookie value, or an empty string if not found.
 */
const getCookie = (name) =>
  document.cookie.match(`(^|;)\\s*${name}\\s*=\\s*([^;]+)`)?.pop() || '';

/* ---------- Idle detection (pure client‑side) ---------- */

let idleTimer = null;
const IDLE_CHECK_INTERVAL = 5000; // poll every 5 s

/**
 * Starts idle detection: monitors user activity and calls the `onIdle`
 * callback after `timeoutMs` milliseconds of inactivity.
 *
 * Detected activity includes mouse movement, key presses, scrolling,
 * and mouse clicks.
 *
 * @param {number}   timeoutMs - Time in milliseconds before the user is
 *                               considered idle.
 * @param {Function} onIdle    - Callback function to execute when idle
 *                               is detected (no arguments expected).
 */
const startIdleDetection = (timeoutMs, onIdle) => {
  let lastActivity = Date.now();

  const resetTimer = () => {
    lastActivity = Date.now();
  };

  // Events that indicate the user is active
  ['mousemove', 'keydown', 'scroll', 'click'].forEach(evt =>
    document.addEventListener(evt, resetTimer, { passive: true })
  );

  // Check periodically whether the timeout has been exceeded
  const check = () => {
    if (Date.now() - lastActivity >= timeoutMs) {
      clearInterval(idleTimer);
      onIdle();
    }
  };

  // Start polling
  if (idleTimer) {
    clearInterval(idleTimer);
  }

  idleTimer = setInterval(check, IDLE_CHECK_INTERVAL);
};

/**
 * Stops the idle detection timer, if one is running.
 */
const stopIdleDetection = () => {
  if (idleTimer) {
    clearInterval(idleTimer);
    idleTimer = null;
  }
};

/* ---------- Keycloak helpers ---------- */

/**
 * Calculates the lifetime of the Keycloak refresh token in milliseconds.
 *
 * @param {KeycloakInstance} keycloakStore - An authenticated Keycloak instance.
 * @returns {number} The computed lifetime (exp - iat) in milliseconds.
 */
const fetchTokenLifetimeMs = (keycloakStore) => {
  const iat = keycloakStore.refreshTokenParsed.iat * 1000;
  const exp = keycloakStore.refreshTokenParsed.exp * 1000;

  return exp - iat;
};

/**
 * Writes the Keycloak access token into the `SSOToken` cookie. The Django
 * backend validates it (signature, issuer, client, expiry) and reads the
 * email, name and roles from it to complete the authentication process.
 *
 * @param {KeycloakInstance} keycloakStore - Authenticated Keycloak instance.
 * @param {string}           expiresUTC    - UTC string for the cookie expiration
 *                                           (typically derived from the token's `exp`).
 */
const setSSOInfo = (keycloakStore, expiresUTC) => {
  setCookie('SSOToken', keycloakStore.token, expiresUTC);
};

/**
 * Initializes a Keycloak authentication adapter, handles the login flow,
 * sets SSO cookies, starts idle detection, and redirects to the Django
 * backend endpoint (`/auth/complete/`) after a successful authentication.
 *
 * @param {string} url      - The base URL of the Keycloak server.
 * @param {string} realm    - The realm to authenticate against.
 * @param {string} clientId - The client ID configured in Keycloak.
 * @returns {KeycloakInstance} The created Keycloak instance for further reference.
 */
export const keycloakInit = (
  url,
  realm,
  clientId
) => {
  const keycloakStore = new keycloak({
    url,
    realm,
    clientId
  });

  // ---------- Token refresh handler ----------
  keycloakStore.onTokenExpired = () => {
    keycloakStore.updateToken(30)
      .then(refreshed => {
        if (refreshed) {
          // Refresh the SSO cookies with the new token’s expiry
          const expiresUTC = new Date(keycloakStore.idTokenParsed.exp * 1000).toUTCString();

          setSSOInfo(keycloakStore, expiresUTC);
          // Restart idle detection with the new timeout
          restartIdle(keycloakStore);
        }
      })
      .catch(err => {
        console.error('Token refresh failed', err);
        keycloakLogout(keycloakStore);
      });
  };

  // ---------- Idle management ----------
  const restartIdle = (store) => {
    const timeoutMs = fetchTokenLifetimeMs(store);

    stopIdleDetection();
    startIdleDetection(timeoutMs, () => keycloakLogout(store));
  };

  // ---------- Main authentication flow ----------
  keycloakStore.init({
    onLoad: 'login-required',
    checkLoginIframe: false,
  }).then(authenticated => {
    if (!authenticated) {
      window.location.reload();

      return;
    }

    console.log('Authenticated');

    // 1. Immediately persist the token and cookies
    if (keycloakStore.token) {
      window.localStorage.setItem('keycloakToken', keycloakStore.token);
    }

    const expiresUTC = new Date(keycloakStore.idTokenParsed.exp * 1000).toUTCString();

    setSSOInfo(keycloakStore, expiresUTC);

    // 2. Start idle detection
    restartIdle(keycloakStore);

    // 3. Redirect to Django to finish server‑side session setup
    //    (cookies are already set, path=/ ensures they are sent to /auth/complete/)
    window.location = "/auth/complete/?next=/app";

  }).catch(error => {
    alert('Failed to initialize Keycloak');
    console.error(error);
  });

  return keycloakStore;
};

/**
 * Logs the user out of Keycloak, clears all related cookies, stops idle
 * detection, removes the locally stored token, and redirects to the
 * Django logout URL.
 *
 * @param {KeycloakInstance} keycloakStore - The Keycloak instance to log out.
 */
export const keycloakLogout = (keycloakStore) => {
  keycloakStore.logout()
    .then(success => {
      deleteAllCookies();
      stopIdleDetection();
      window.localStorage.removeItem('keycloakToken');
      console.log('Logout success', success);
      window.location = "/auth/logout/";
    })
    .catch(error => {
      console.error('Logout error', error);
    });
};
