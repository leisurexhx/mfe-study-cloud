"""Typed provider failures used by job retry policy."""


class AnalysisError(RuntimeError):
    retryable = False


class ProviderDisabledError(AnalysisError):
    pass


class ProviderConfigurationError(AnalysisError):
    pass


class ProviderRefusalError(AnalysisError):
    pass


class ProviderSchemaError(AnalysisError):
    pass


class ProviderQuotaError(AnalysisError):
    """The provider account cannot accept paid work until an administrator acts."""


class ProviderTransientError(AnalysisError):
    retryable = True
