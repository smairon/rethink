"""Опциональный адаптер для prometheus_client.

Использование:

    pip install prometheus-client

    from ext.zorge.contrib.prometheus import PrometheusMetrics
    container = Container(registry, metrics=PrometheusMetrics())

Модуль не импортируется автоматически из ``ext.zorge``: если
``prometheus_client`` не установлен, обычные пользователи библиотеки
ничего не заметят.
"""

from prometheus_client import Counter, Gauge, Histogram

from ..internal.metrics import Metrics


class PrometheusMetrics(Metrics):
    def __init__(self, namespace: str = "zorge") -> None:
        n = namespace
        self._resolve = Counter(
            f"{n}_resolve_total",
            "Resolve calls by scope and outcome.",
            ["scope", "outcome"],
        )
        self._resolve_duration = Histogram(
            f"{n}_resolve_duration_seconds",
            "Resolve duration in seconds.",
            ["scope"],
        )
        self._resolve_depth = Histogram(
            f"{n}_resolve_depth",
            "Recursion depth of dependency resolution.",
            buckets=(0, 1, 2, 3, 5, 8, 13, 21),
        )
        self._instance_created = Counter(
            f"{n}_instance_created_total",
            "Instances built, by scope.",
            ["scope"],
        )
        self._instance_build = Histogram(
            f"{n}_instance_build_duration_seconds",
            "Constructor/factory duration.",
            ["scope"],
        )
        self._instance_alive = Gauge(
            f"{n}_instances_alive",
            "Live instances held by registries.",
            ["scope"],
        )
        self._scope_opened = Counter(
            f"{n}_scope_opened_total",
            "Providers entered via async with.",
            ["scope"],
        )
        self._scope_closed = Counter(
            f"{n}_scope_closed_total",
            "Providers exited via async with.",
            ["scope"],
        )
        self._scope_lifetime = Histogram(
            f"{n}_scope_lifetime_seconds",
            "Provider lifetime between __aenter__ and __aexit__.",
            ["scope"],
        )
        self._ctx_exit_error = Counter(
            f"{n}_ctx_exit_errors_total",
            "Errors raised by __exit__ / __aexit__ of dependencies.",
            ["scope"],
        )

    def resolve(self, *, scope, outcome, duration, depth):
        self._resolve.labels(scope=scope, outcome=outcome).inc()
        self._resolve_duration.labels(scope=scope).observe(duration)
        self._resolve_depth.observe(depth)

    def instance_created(self, *, scope, duration):
        self._instance_created.labels(scope=scope).inc()
        self._instance_build.labels(scope=scope).observe(duration)

    def instance_alive(self, *, scope, delta):
        self._instance_alive.labels(scope=scope).inc(delta)

    def scope_opened(self, *, scope):
        self._scope_opened.labels(scope=scope).inc()

    def scope_closed(self, *, scope, lifetime, instances):
        self._scope_closed.labels(scope=scope).inc()
        self._scope_lifetime.labels(scope=scope).observe(lifetime)

    def ctx_exit_error(self, *, scope):
        self._ctx_exit_error.labels(scope=scope).inc()
