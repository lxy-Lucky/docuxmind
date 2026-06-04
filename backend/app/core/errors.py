import os


class AppError(Exception):
    def __init__(self, message: str, *, code: str = "app_error", status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


class NotFoundError(AppError):
    def __init__(self, what: str = "resource") -> None:
        super().__init__(f"{what} not found", code="not_found", status=404)


def is_safe_filename(name: str) -> bool:
    """Reject path traversal, separators, null bytes."""
    if not name:
        return False
    bad = (os.sep, "/", "\\", "..", "\x00")
    return not any(b in name for b in bad)
