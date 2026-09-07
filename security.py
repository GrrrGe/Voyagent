import hashlib
import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from fastapi import HTTPException


def session_secret(data_dir):
    configured = os.getenv('SESSION_SECRET')
    if configured:
        if len(configured) < 32:
            raise RuntimeError('SESSION_SECRET must contain at least 32 characters.')
        return configured
    if os.getenv('APP_ENV') == 'production':
        raise RuntimeError('Set SESSION_SECRET in production.')
    path = Path(data_dir) / 'session.key'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        try:
            with path.open('x') as stream:
                stream.write(secrets.token_hex(32))
            path.chmod(0o600)
        except FileExistsError:
            pass
    return path.read_text().strip()


def internal_thread(session, thread_id):
    return hashlib.sha256(f'{session}:{thread_id}'.encode()).hexdigest()


def validate_providers():
    for name, key in [('FLIGHT_PROVIDER', 'AVIATIONSTACK_API_KEY'), ('HOTEL_PROVIDER', 'TAVILY_API_KEY')]:
        mode = os.getenv(name, 'mock')
        if mode not in ('mock', 'live'):
            raise RuntimeError(f'{name} must be mock or live.')
        if mode == 'live' and not os.getenv(key):
            raise RuntimeError(f'Set {key} before enabling {name}.')
    mode = os.getenv('LLM_PROVIDER', 'mock')
    if mode not in ('mock', 'live', 'groq', 'openai'):
        raise RuntimeError('LLM_PROVIDER must be mock, groq, openai, or live.')
    key = 'OPENAI_API_KEY' if mode == 'openai' else 'GROQ_API_KEY'
    if mode != 'mock' and not os.getenv(key):
        raise RuntimeError(f'Set {key} before enabling LLM_PROVIDER.')


class RateLimiter:
    def __init__(self, limit=20):
        self.limit = limit
        self.events = defaultdict(deque)
    def check(self, key):
        now = time.monotonic()
        for old in list(self.events):
            if not self.events[old] or self.events[old][-1] <= now - 60:
                del self.events[old]
        bucket = self.events[key]
        while bucket and bucket[0] <= now - 60:
            bucket.popleft()
        if len(bucket) >= self.limit:
            raise HTTPException(429, 'Too many requests. Try again in one minute.')
        bucket.append(now)
