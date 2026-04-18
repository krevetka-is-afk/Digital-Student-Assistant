class SlowQueryFilter:
    def __init__(self, *, threshold_ms: float):
        self.threshold_ms = float(threshold_ms)

    def filter(self, record) -> bool:
        duration_seconds = getattr(record, "duration", None)
        if duration_seconds is None:
            return False
        return (float(duration_seconds) * 1000) >= self.threshold_ms
