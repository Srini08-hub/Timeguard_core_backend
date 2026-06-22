class ExtractionError(Exception):
    """Raised after all attempts fail. Carries the raw response for review."""

    def __init__(self, message: str, raw_response: str, attempts: int):
        super().__init__(message)
        self.raw_response = raw_response
        self.attempts = attempts
