"""Протокол наблюдателя для метрик контейнера.

Все методы вызываются синхронно на горячем пути, поэтому реализации
должны быть максимально дешёвыми. По умолчанию используется
:class:`NoopMetrics` — нулевой оверхед, никаких аллокаций.
"""

from typing import Protocol


class Metrics(Protocol):
    """Наблюдатель за событиями контейнера.

    Пользователь реализует этот протокол под свою систему метрик
    (Prometheus, OpenTelemetry, StatsD и т.п.) и передаёт инстанс в
    :class:`~ext.zorge.container.Container`.
    """

    def resolve(
        self,
        *,
        scope: str,
        outcome: str,
        duration: float,
        depth: int,
    ) -> None:
        """Один вызов ``Provider.resolve`` для конкретной зависимости.

        :param outcome: один из ``"cache_hit"``, ``"built"``,
            ``"not_found"``, ``"error"``.
        :param duration: длительность вызова в секундах.
        :param depth: глубина рекурсии в графе зависимостей (0 для
            верхнеуровневого вызова).
        """
        ...

    def instance_created(self, *, scope: str, duration: float) -> None:
        """Создан новый экземпляр зависимости (вызван конструктор/фабрика).

        ``duration`` — время, потраченное собственно на вызов
        ``entity(**args)``/``partial(...)``, без времени резолва аргументов.
        """
        ...

    def instance_alive(self, *, scope: str, delta: int) -> None:
        """Изменение числа живых инстансов в scope.

        ``+1`` при кэшировании нового инстанса, ``-N`` при закрытии
        registry.
        """
        ...

    def scope_opened(self, *, scope: str) -> None:
        """Провайдер вошёл в ``async with``."""
        ...

    def scope_closed(self, *, scope: str, lifetime: float, instances: int) -> None:
        """Провайдер вышел из ``async with``.

        :param lifetime: время между ``__aenter__`` и ``__aexit__`` в секундах.
        :param instances: сколько инстансов было в registry на момент закрытия.
        """
        ...

    def ctx_exit_error(self, *, scope: str) -> None:
        """``__exit__``/``__aexit__`` одной из зависимостей бросил исключение."""
        ...


class NoopMetrics:
    """Реализация по умолчанию — ничего не делает, нулевой оверхед."""

    __slots__ = ()

    def resolve(self, *, scope, outcome, duration, depth): ...
    def instance_created(self, *, scope, duration): ...
    def instance_alive(self, *, scope, delta): ...
    def scope_opened(self, *, scope): ...
    def scope_closed(self, *, scope, lifetime, instances): ...
    def ctx_exit_error(self, *, scope): ...


NOOP_METRICS: Metrics = NoopMetrics()
