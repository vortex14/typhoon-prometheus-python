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

class Settings(BaseModel):
    prometheus_prefix: str = "prefixapp"
    app_name: str = "myapp"

class Config(BaseModel):
    registry: Any = None
    _metrics: dict = {}
    settings: Settings

class TyphoonMetric(BaseModel):
    settings: Settings
    metric: Metric
    active: bool = False
    config: Any = None
    exceptions_config: Any = None
    prometheus_path: str = None

    @root_validator
    def set_prometheus_config(cls, values):
        prometheus_path = f"{values['settings'].prometheus_prefix}_{values['settings'].app_name.replace('-', '_')}_{values['metric'].name}"
        values["prometheus_path"] = prometheus_path
        if values["metric"].type in Types.__dict__:
            Metric_class_type = Types.__dict__[values["metric"].type].value
            values["config"] = Metric_class_type(prometheus_path, values["metric"].description)
            if values["metric"].type == "counter":
                values["exceptions_config"] = Metric_class_type(f"{prometheus_path}_exceptions_total", f"{values['metric'].description}. Only Exceptions.")
        else:
            raise ValueError("metric type isn't valid")

        return values



class Metrics:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.config.registry = Registry()

    def show(self):
        return self.config._metrics


    def add_new_metric(self, metric: Metric):
        if not self.config._metrics.get(metric.name):
            self.config._metrics[metric.name] = TyphoonMetric(
                metric = metric,
                settings=self.config.settings
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
    metric = Metric(name="on_message", type="counter", description="Input messages.", labels={})
    metric_2 = Metric(name="on_products", type="counter", description="Input messages.", labels={})
    metrics = Metrics(Config(settings=Settings(prometheus_prefix="testprefix", app_name="typhoon")))
    metrics.add_new_metric(metric)
    metrics.add_new_metric(metric_2)
    debug(metrics.show())