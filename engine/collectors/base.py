from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import RawItem


class Collector(ABC):
    name: str

    @abstractmethod
    def collect(self) -> list[RawItem]:
        raise NotImplementedError
