"""Expected service-layer errors safe to map to user-facing responses."""


class ServiceError(Exception):
    """Base class for expected use-case failures."""


class AuthenticationError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass


class NotFoundError(ServiceError):
    pass


class ValidationError(ServiceError):
    pass
