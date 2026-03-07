class ExecutionStats:
    """Encapsulates execution statistics for an LLM run."""

    def __init__(self, executed=0, cached=0, pending=0):
        self.executed = executed
        self.cached = cached
        self.pending = pending

    def __add__(self, other):
        if not isinstance(other, ExecutionStats):
            return NotImplemented
        return ExecutionStats(
            executed=self.executed + other.executed,
            cached=self.cached + other.cached,
            pending=self.pending + other.pending,
        )

    def __iadd__(self, other):
        if not isinstance(other, ExecutionStats):
            return NotImplemented
        result = self + other
        self.executed = result.executed
        self.cached = result.cached
        self.pending = result.pending
        return self

    def __str__(self):
        total = self.executed + self.cached + self.pending
        parts = []
        if self.executed:
            parts.append(f"{self.executed} executed")
        if self.cached:
            parts.append(f"{self.cached} cached")
        if self.pending:
            parts.append(f"{self.pending} pending")
        details = f" ({', '.join(parts)})" if parts else ""
        return f"{total} task(s) processed{details}"

    def __repr__(self):
        return (f"ExecutionStats(executed={self.executed}, "
                f"cached={self.cached}, pending={self.pending})")
