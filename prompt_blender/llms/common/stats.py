class ExecutionStats:
    """Encapsulates execution statistics for an LLM run."""

    def __init__(self, executed=0, cached=0, pending=0,
                 tokens_in=0, tokens_out=0, bytes_in=0, bytes_out=0,
                 cost=0.0, max_cost=0.0):
        self.executed = executed
        self.cached = cached
        self.pending = pending
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.bytes_in = bytes_in
        self.bytes_out = bytes_out
        self.cost = cost
        self.max_cost = max_cost

    def __add__(self, other):
        if not isinstance(other, ExecutionStats):
            return NotImplemented
        return ExecutionStats(
            executed=self.executed + other.executed,
            cached=self.cached + other.cached,
            pending=self.pending + other.pending,
            tokens_in=self.tokens_in + other.tokens_in,
            tokens_out=self.tokens_out + other.tokens_out,
            bytes_in=self.bytes_in + other.bytes_in,
            bytes_out=self.bytes_out + other.bytes_out,
            cost=self.cost + other.cost,
            max_cost=max(self.max_cost, other.max_cost),
        )

    def __iadd__(self, other):
        if not isinstance(other, ExecutionStats):
            return NotImplemented
        result = self + other
        self.executed = result.executed
        self.cached = result.cached
        self.pending = result.pending
        self.tokens_in = result.tokens_in
        self.tokens_out = result.tokens_out
        self.bytes_in = result.bytes_in
        self.bytes_out = result.bytes_out
        self.cost = result.cost
        self.max_cost = result.max_cost
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
                f"cached={self.cached}, pending={self.pending}, "
                f"tokens_in={self.tokens_in}, tokens_out={self.tokens_out}, "
                f"bytes_in={self.bytes_in}, bytes_out={self.bytes_out}, "
            f"cost={self.cost}, max_cost={self.max_cost})")
