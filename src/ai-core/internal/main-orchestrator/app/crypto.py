import json

from cryptography.fernet import Fernet


class Cipher:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode())

    def encrypt(self, value: object) -> str:
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        return self._fernet.encrypt(raw).decode()

    def decrypt(self, value: str) -> object:
        return json.loads(self._fernet.decrypt(value.encode()))
