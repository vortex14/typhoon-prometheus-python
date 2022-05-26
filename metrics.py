from aioprometheus import Counter, Gauge, Summary, Histogram
from pydantic import BaseModel, root_validator
from aioprometheus import Registry
from devtools import debug
from typing import Any, Tuple
from enum import Enum

class Types(Enum):
    counter = Counter
    gauge = Gauge
    summary = Summary
    histogram = Histogram

class MetricData(BaseModel):
    name: str
    labels: dict
    value: int = 0

class Metric(MetricData):
    type: str
    description: str

class TyphoonMetric(BaseModel):
    metric: Metric
    project_name: str
    component_name: str
    active: bool = False
    config: Any = None
    exceptions_config: Any = None
    prometheus_path: str = None

    @root_validator
    def set_prometheus_config(cls, values):
        prefix = "typhoon_" + values["project_name"].replace('-', '_') + f"_{values['component_name']}"
        prometheus_path = f'{prefix}_{values["metric"].name}'
        values["prometheus_path"] = prometheus_path
        if values["metric"].type in Types.__dict__:
            Metric_class_type = Types.__dict__[values["metric"].type].value
            values["config"] = Metric_class_type(prometheus_path, values["metric"].description)
            if values["metric"].type == "counter":
                values["exceptions_config"] = Metric_class_type(prometheus_path + "_exceptions_total", values["metric"].description + ". Only Exceptions.")
        else:
            raise ValueError("metric type isn't valid")

        return values


class Metrics:
    def __init__(self, config) -> None:
        self.config = config
        self.config.registry = Registry()
        self.config._metrics = {}

    def show(self):
        return self.config._metrics


    def add_new_metric(self, metric: Metric):
        if not self.config._metrics.get(metric.name):
            self.config._metrics[metric.name] = TyphoonMetric(
                metric = metric,
                component_name = self.config.component_name,
                project_name = self.config.project_name
            )
            self._init_metrics()

    def set_exception(self, data: MetricData):
        current_metric = self.config._metrics[data.name]
        current_metric.exceptions_config.inc(data.labels)
    
    def update(self, data: MetricData):
        current_metric = self.config._metrics[data.name]
        current_metric.config.inc(data.labels)

    def add(self, data: MetricData):
        current_metric = self.config._metrics[data.name]
        current_metric.config.add(data.labels, data.value)

    def dec(self, data: MetricData):
        current_metric = self.config._metrics[data.name]
        current_metric.config.dec(data.labels)

    def _init_metrics(self):
        for name in self.config._metrics:
            ins = self.config._metrics[name]
            if ins.active: continue
            self.config.registry.register(ins.config)
            if ins.exceptions_config:
                self.config.registry.register(ins.exceptions_config)
            ins.active = True
    
    @staticmethod
    def add_metric(*metrics: Tuple[Metric, ...]):
        def decor(func):
            async def wrapper(self, *args, **kwargs):
                for metric in metrics:
                    self.config.metrics.add_new_metric(metric)
                    if metric.type in ["counter", "gauge"]:
                        self.config.metrics.update(MetricData(name=metric.name, labels=metric.labels))
                return await func(self, *args, **kwargs)
            return wrapper
        return decor


if __name__ == "__main__":
    class TestConfig:
        registry: Any = None
        _metrics: dict = {}
        component_name = "processor"
        project_name = "test-project"

    metric = Metric(name="on_message", type="counter", description="Input messages.", labels={})
    metric_2 = Metric(name="on_products", type="counter", description="Input messages.", labels={})
    metrics = Metrics(TestConfig())
    metrics.add_new_metric(metric)
    metrics.add_new_metric(metric_2)
    debug(metrics.show())