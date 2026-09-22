class V2Error(Exception):
    def __init__(self, code, message, status=422, retryable=False):
        super().__init__(message)
        self.code, self.message, self.status, self.retryable = (
            code,
            message,
            status,
            retryable,
        )


def conflict(message="Invoice state or version has changed."):
    return V2Error("CONFLICT", message, 409)
