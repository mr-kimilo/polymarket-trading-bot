"""
Risk Control Module - Pre-launch Volatility Check

Checks BTC price volatility over the past 24 hours using Binance Klines API.
If the high-low range exceeds a configurable threshold (default: 4000 USD),
displays a red warning and requires manual confirmation before proceeding.

Usage:
    from lib.risk_control import RiskChecker, VolatilityResult

    checker = RiskChecker(threshold=4000.0)
    result = checker.check_24h_volatility()

    if result.is_high_risk:
        # Show warning and ask for confirmation
        checker.prompt_confirmation(result)
"""

import sys
from dataclasses import dataclass
from typing import Optional

import requests

from lib.console import Colors


BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
BINANCE_KLINES_TIMEOUT = 10
DEFAULT_VOLATILITY_THRESHOLD = 4000.0


@dataclass(frozen=True)
class VolatilityResult:
    """Result of a 24-hour BTC volatility check.

    Attributes:
        high: Highest BTC price in the past 24 hours
        low: Lowest BTC price in the past 24 hours
        price_range: Difference between high and low
        threshold: The risk threshold used
        is_high_risk: Whether the price range exceeds the threshold
        error: Error message if the check failed
    """

    high: float
    low: float
    price_range: float
    threshold: float
    is_high_risk: bool
    error: Optional[str] = None

    @staticmethod
    def from_error(message: str, threshold: float) -> "VolatilityResult":
        """Create a result representing a failed check."""
        return VolatilityResult(
            high=0.0,
            low=0.0,
            price_range=0.0,
            threshold=threshold,
            is_high_risk=False,
            error=message,
        )


class RiskChecker:
    """Checks BTC price volatility before strategy launch.

    Args:
        threshold: Price range (in USD) that triggers a high-risk warning.
                   Default is 4000.
    """

    def __init__(self, threshold: float = DEFAULT_VOLATILITY_THRESHOLD) -> None:
        self._threshold = threshold

    def check_24h_volatility(self) -> VolatilityResult:
        """Fetch 24h BTC klines from Binance and compute high-low range.

        Uses 1-hour klines for the past 24 hours (24 candles) to determine
        the overall high and low prices.

        Returns:
            VolatilityResult with the computed price range and risk flag.
        """
        try:
            klines = self._fetch_24h_klines()
            return self._evaluate_klines(klines)
        except requests.RequestException as exc:
            return VolatilityResult.from_error(
                f"Network error fetching Binance klines: {exc}",
                self._threshold,
            )
        except (ValueError, KeyError, IndexError) as exc:
            return VolatilityResult.from_error(
                f"Failed to parse Binance klines: {exc}",
                self._threshold,
            )

    def _fetch_24h_klines(self) -> list:
        """Fetch 24 hourly klines from Binance API.

        Returns:
            Raw klines list from Binance API.

        Raises:
            requests.RequestException: On network failure.
            ValueError: If the response is invalid.
        """
        params = {
            "symbol": "BTCUSDT",
            "interval": "1h",
            "limit": "24",
        }
        response = requests.get(
            BINANCE_KLINES_URL, params=params, timeout=BINANCE_KLINES_TIMEOUT
        )
        response.raise_for_status()
        klines = response.json()

        if not klines:
            raise ValueError("Empty klines response from Binance")

        return klines

    def _evaluate_klines(self, klines: list) -> VolatilityResult:
        """Compute high/low/range from raw klines data.

        Binance kline format: [open_time, open, high, low, close, ...].
        Index 2 = high, index 3 = low.

        Args:
            klines: Raw klines list from Binance.

        Returns:
            VolatilityResult with computed values.
        """
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]

        highest = max(highs)
        lowest = min(lows)
        price_range = highest - lowest

        return VolatilityResult(
            high=highest,
            low=lowest,
            price_range=price_range,
            threshold=self._threshold,
            is_high_risk=price_range > self._threshold,
        )

    def print_result(self, result: VolatilityResult) -> None:
        """Print the volatility check result to console.

        Args:
            result: The volatility check result to display.
        """
        if result.error:
            print(
                f"{Colors.YELLOW}!! Volatility check failed: {result.error}{Colors.RESET}",
                flush=True,
            )
            return

        print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}", flush=True)
        print(
            f"{Colors.CYAN}  BTC 24h Volatility Check (Risk Control){Colors.RESET}",
            flush=True,
        )
        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}", flush=True)
        print(
            f"  24h High : ${result.high:,.2f}",
            flush=True,
        )
        print(
            f"  24h Low  : ${result.low:,.2f}",
            flush=True,
        )
        print(
            f"  Range    : ${result.price_range:,.2f}",
            flush=True,
        )
        print(
            f"  Threshold: ${result.threshold:,.2f}",
            flush=True,
        )

        if result.is_high_risk:
            print(
                f"\n{Colors.RED}{Colors.BOLD}"
                f"  !!!  HIGH VOLATILITY WARNING  !!!{Colors.RESET}",
                flush=True,
            )
            print(
                f"{Colors.RED}"
                f"  BTC price range (${result.price_range:,.2f}) "
                f"exceeds ${result.threshold:,.2f} threshold!{Colors.RESET}",
                flush=True,
            )
            print(
                f"{Colors.RED}"
                f"  Trading in high volatility carries increased risk.{Colors.RESET}",
                flush=True,
            )
        else:
            # Windows 兼容ASCII符号
            print(
                f"\n{Colors.GREEN}  OK Volatility is within safe range.{Colors.RESET}",
                flush=True,
            )

        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n", flush=True)

    def prompt_confirmation(self, result: VolatilityResult) -> bool:
        """Display warning and ask for manual confirmation if high risk.

        If the result is high risk, prints a red warning and prompts
        the user to type 'yes' to continue. If not high risk, returns
        True immediately.

        Args:
            result: The volatility check result.

        Returns:
            True if the user confirms or risk is acceptable, False otherwise.
        """
        self.print_result(result)

        if result.error:
            # On error, allow continuing with a warning
            return True

        if not result.is_high_risk:
            return True

        # High risk - require manual confirmation
        try:
            answer = input(
                f"{Colors.RED}{Colors.BOLD}"
                f"  Continue trading? (Y/N): "
                f"{Colors.RESET}"
            )
            if answer.strip().upper() == "Y":
                print(
                    f"{Colors.YELLOW}  User confirmed. Proceeding...{Colors.RESET}\n",
                    flush=True,
                )
                return True

            print(
                f"{Colors.YELLOW}  Cancelled by user. Exiting.{Colors.RESET}",
                flush=True,
            )
            return False
        except (EOFError, KeyboardInterrupt):
            print(
                f"\n{Colors.YELLOW}  Cancelled. Exiting.{Colors.RESET}",
                flush=True,
            )
            return False


def check_volatility_before_start(
    threshold: float = DEFAULT_VOLATILITY_THRESHOLD,
) -> None:
    """Convenience function: check volatility and exit if user declines.

    Call this during startup before launching the strategy.

    Args:
        threshold: Price range threshold in USD. Default: 4000.
    """
    checker = RiskChecker(threshold=threshold)
    result = checker.check_24h_volatility()
    confirmed = checker.prompt_confirmation(result)

    if not confirmed:
        sys.exit(0)
