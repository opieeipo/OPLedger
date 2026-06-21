"""In-memory runtime state.

Holds process-lifetime state that must never be persisted: whether the
database is currently unlocked, and the JWT signing secret (loaded from the
encrypted database after unlock). Nothing here is written to disk.
"""


class Runtime:
    def __init__(self) -> None:
        self.unlocked: bool = False
        self.jwt_secret: str | None = None

    def lock(self) -> None:
        self.unlocked = False
        self.jwt_secret = None


runtime = Runtime()
