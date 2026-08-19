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


class ProviderTransientError(AnalysisError):
    retryable = True

