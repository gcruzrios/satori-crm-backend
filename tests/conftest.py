import os

# Tests never touch a real database; provide dummy settings before the app is imported.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:1/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
