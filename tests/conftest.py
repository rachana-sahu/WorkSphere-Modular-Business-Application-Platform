import os

os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-only-signing-key-for-worksphere-tests-1234567890",
)
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")
