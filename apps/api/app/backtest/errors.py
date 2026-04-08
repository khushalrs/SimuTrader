"""Structured backtest failure types."""

from __future__ import annotations


class BacktestError(Exception):
    """Base class for safe, structured backtest failures."""

    def __init__(
        self,
        code: str,
        public_message: str,
        retryable: bool = False,
        *,
        internal_message: str | None = None,
    ) -> None:
        self.code = code
        self.public_message = public_message
        self.retryable = retryable
        self.internal_message = internal_message or public_message
        super().__init__(self.internal_message)


class ConfigValidationError(BacktestError):
    def __init__(self, internal_message: str | None = None) -> None:
        super().__init__(
            code="E_CONFIG_INVALID",
            public_message="This strategy configuration could not be validated.",
            retryable=False,
            internal_message=internal_message,
        )


class DataUnavailableError(BacktestError):
    def __init__(self, internal_message: str | None = None) -> None:
        super().__init__(
            code="E_DATA_UNAVAILABLE",
            public_message="Required market data was unavailable for this run.",
            retryable=True,
            internal_message=internal_message,
        )


class NoTradingDaysError(BacktestError):
    def __init__(self, internal_message: str | None = None) -> None:
        super().__init__(
            code="E_NO_TRADING_DAYS",
            public_message="No trading days were found in the selected range.",
            retryable=False,
            internal_message=internal_message,
        )


class UnsupportedStrategyError(ConfigValidationError):
    pass
