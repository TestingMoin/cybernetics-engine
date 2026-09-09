from __future__ import annotations
from contextlib import contextmanager
from typing import Iterator, Protocol, Any


class Connection(Protocol):
    def transaction(self): ...


@contextmanager
def atomic_fill_transaction(connection: Connection) -> Iterator[Any]:
    """Yield one transaction; connection acquisition remains caller-owned."""
    with connection.transaction() as tx:
        yield tx
