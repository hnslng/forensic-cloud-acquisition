"""Authentication providers return identities; case permissions are separate."""
from typing import Protocol
from threading import BoundedSemaphore
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1)
hash_slots = BoundedSemaphore(2)
DUMMY_HASH = hasher.hash('synthetic-non-user-dummy-password')


class IdentityProvider(Protocol):
    def authenticate(self, conn, username: str, password: str): ...


class BusyAuthentication(Exception):
    pass


def verify_password(password_hash, password):
    if not hash_slots.acquire(blocking=False):
        raise BusyAuthentication()
    try:
        return hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False
    finally:
        hash_slots.release()


def hash_password(password):
    if not hash_slots.acquire(blocking=False):
        raise BusyAuthentication()
    try:
        return hasher.hash(password)
    finally:
        hash_slots.release()


class LocalIdentityProvider:
    def authenticate(self, conn, username, password):
        user = conn.execute('SELECT * FROM users WHERE username=%s', (username,)).fetchone()
        correct = verify_password(user['password_hash'] if user else DUMMY_HASH, password)
        if not correct or not user or not user['active'] or user['identity_provider'] != 'local':
            return None
        if hasher.check_needs_rehash(user['password_hash']):
            conn.execute('UPDATE users SET password_hash=%s WHERE id=%s', (hash_password(password), user['id']))
        return user


identity_provider: IdentityProvider = LocalIdentityProvider()
