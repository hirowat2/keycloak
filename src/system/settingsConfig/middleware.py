import sys


IS_RUNNING_TESTS = "test" in sys.argv

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",  # needs to be first
    "csp.middleware.CSPMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django_permissions_policy.PermissionsPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "system.sso.EmailPermitidoMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # "debug_toolbar.middleware.DebugToolbarMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
    "silk.middleware.SilkyMiddleware",
    # "pseudoproject.keycloak.middleware.KeycloakSessionMiddleware",
    "django_guid.middleware.guid_middleware",
    "django_htmx.middleware.HtmxMiddleware",
    "django_components.middleware.ComponentDependencyMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",  # needs to be last
]

if not IS_RUNNING_TESTS:
    MIDDLEWARE.insert(
        MIDDLEWARE.index("auditlog.middleware.AuditlogMiddleware"),
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    )