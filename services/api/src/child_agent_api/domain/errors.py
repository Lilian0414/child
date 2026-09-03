"""Typed errors raised before any state is committed."""


class DomainError(Exception):
    pass


class NotFoundError(DomainError):
    pass


class VersionConflictError(DomainError):
    def __init__(self, expected: int, current: int) -> None:
        super().__init__(f"expected state version {expected}, current version is {current}")
        self.expected = expected
        self.current = current


class InvalidReferenceError(DomainError):
    pass
