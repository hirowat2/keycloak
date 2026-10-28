from csp.constants import NONCE, SELF
import os

CDNS = [
    "https://cdn.plot.ly",
    "https://cdn.jsdelivr.net",
    "https://unpkg.com",
    "http://www.w3.org/",
    "https://buttons.github.io",
    "https://cdnjs.cloudflare.com",
    "https://www.youtube-nocookie.com",
    "https://flowbite-admin-dashboard.vercel.app",
    "https://raw.githubusercontent.com",
    "https://mozilla.github.io",
    "https://cdn.bokeh.org",
]

CONNECT = [
    "https://fonts.googleapis.com",
]

FONT = [
    "https://cdn.jsdelivr.net",
    "https://fonts.googleapis.com",
    "https://fonts.gstatic.com",
    "https://cdnjs.cloudflare.com",
]


SCRIPT = [
    "'unsafe-eval'",
    "'unsafe-inline'",
]

OTHERS = [
    "https://youtu.be/",
    "https://www.youtube.com/",
    # os.environ["KEYCLOAK_HOST"],
]

if keycloak_host := os.getenv("KEYCLOAK_HOST"):
    OTHERS.append(keycloak_host)

JERRY_RIG = ["data:"]

JERRY_RIG_2 = ["blob:"]

CONTENT_SECURITY_POLICY = {
    "EXCLUDE_URL_PREFIXES": ["/excluded-path/"],
    "DIRECTIVES": {
        "default-src": [SELF] + CDNS + FONT + OTHERS + [NONCE],
        "connect-src": [SELF] + CONNECT + CDNS + OTHERS,
        "img-src": [SELF] + CDNS + OTHERS + JERRY_RIG + [NONCE],
        "font-src": [SELF] + FONT,
        "font-src-elem": [SELF] + FONT + [NONCE],
        "script-src": [SELF] + SCRIPT + JERRY_RIG_2 + CDNS,
        "script-src-elem": [SELF] + SCRIPT + JERRY_RIG_2 + CDNS,
        "style-src": [SELF, "'unsafe-inline'"] + FONT + CDNS,
        "frame-src": [SELF] + CDNS + OTHERS + JERRY_RIG + JERRY_RIG_2 + ["about:"],
        "child-src": [SELF] + CDNS + OTHERS + JERRY_RIG + JERRY_RIG_2 + ["about:"],
        "frame-ancestors": [SELF] + OTHERS,
    },
}
