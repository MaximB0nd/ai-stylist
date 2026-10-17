from dataclasses import dataclass


@dataclass
class AppError(Exception):
    status: int
    code: str
    message: str
    retryable: bool = False

    def body(self) -> dict[str, str | bool]:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}
