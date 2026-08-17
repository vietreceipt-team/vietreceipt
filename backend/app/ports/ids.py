from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4


@runtime_checkable
class IdGenerator(Protocol):
    def new_id(self) -> UUID:
        ...


class UUID4Generator:
    def new_id(self) -> UUID:
        return uuid4()
