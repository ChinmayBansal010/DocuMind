class AzureServiceError(RuntimeError):
    def __init__(self, service: str, message: str, *, status_code: int = 503):
        self.service = service
        self.status_code = status_code
        super().__init__(f"Azure {service}: {message}")
