"""Secure password hashing boundary using Argon2id."""

from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class PasswordHasher:
    """Hash and verify passwords without exposing provider details to repositories."""

    def __init__(self, hasher: Argon2PasswordHasher | None = None) -> None:
        self._hasher = hasher or Argon2PasswordHasher()

    def hash(self, password: str) -> str:
        """Return an Argon2id encoded password hash."""
        if not password:
            raise ValueError("Password must not be empty.")
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        """Return false for mismatches and malformed stored hashes."""
        try:
            return self._hasher.verify(password_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        """Return whether current Argon2 parameters should replace a valid hash."""
        try:
            return self._hasher.check_needs_rehash(password_hash)
        except InvalidHashError:
            return True
