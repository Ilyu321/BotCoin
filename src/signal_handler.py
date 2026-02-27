import signal
import sys
import logging
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class SignalHandler:
    """Handles graceful shutdown signals"""

    def __init__(self):
        self._handlers = []
        self._exit_code = 0
        self._signals_setup = False

    def register_handler(self, handler: Callable[[int, object], None]):
        """Register a signal handler"""
        self._handlers.append(handler)
        logger.debug(f"Registered signal handler: {handler.__name__}")

    def handle_signal(self, signum: int, frame):
        """Handle incoming signal"""
        logger.info(f"Signal {signum} received, initiating graceful shutdown...")

        # Call all registered handlers
        for handler in self._handlers:
            try:
                handler(signum, frame)
            except Exception as e:
                logger.error(f"Error in signal handler {handler.__name__}: {e}")

        # Exit with appropriate code
        sys.exit(self._exit_code)

    def setup(self, signals: Optional[List[int]] = None):
        """Setup signal handlers"""
        if signals is None:
            signals = [signal.SIGTERM, signal.SIGINT, signal.SIGQUIT]

        for sig in signals:
            try:
                signal.signal(sig, self.handle_signal)
                logger.debug(f"Signal handler setup for signal {sig}")
            except ValueError as e:
                logger.warning(f"Could not setup handler for signal {sig}: {e}")

        self._signals_setup = True
        logger.info(f"Signal handlers setup for: {signals}")

    def set_exit_code(self, exit_code: int):
        """Set exit code for shutdown"""
        self._exit_code = exit_code
        logger.debug(f"Exit code set to: {exit_code}")

    def is_setup(self) -> bool:
        """Check if signal handlers are setup"""
        return self._signals_setup


# Global signal handler instance
_signal_handler = SignalHandler()


def register_signal_handler(handler: Callable[[int, object], None]):
    """Register a signal handler with the global instance"""
    _signal_handler.register_handler(handler)


def setup_signal_handlers(signals: Optional[List[int]] = None):
    """Setup signal handlers with the global instance"""
    _signal_handler.setup(signals)


def set_exit_code(exit_code: int):
    """Set exit code for the global signal handler"""
    _signal_handler.set_exit_code(exit_code)


def is_signal_handler_setup() -> bool:
    """Check if signal handlers are setup"""
    return _signal_handler.is_setup()


# Example usage:
# def graceful_shutdown(signum, frame):
#     logger.info("Shutting down gracefully...")
#     # Save state, close connections, etc.
#     time.sleep(2)  # Simulate cleanup

# register_signal_handler(graceful_shutdown)
# setup_signal_handlers()


class GracefulShutdownManager:
    """Manager for graceful shutdown operations"""

    def __init__(self):
        self.cleanup_functions = []
        self._shutdown_in_progress = False

    def register_cleanup_function(self, func: Callable[[], None]):
        """Register a cleanup function to be called on shutdown"""
        self.cleanup_functions.append(func)
        logger.debug(f"Registered cleanup function: {func.__name__}")

    def shutdown(self, signum: int = None, frame = None):
        """Perform graceful shutdown"""
        if self._shutdown_in_progress:
            logger.warning("Shutdown already in progress, skipping...")
            return

        self._shutdown_in_progress = True
        logger.info("Starting graceful shutdown...")

        # Call all cleanup functions
        for func in self.cleanup_functions:
            try:
                func()
            except Exception as e:
                logger.error(f"Error in cleanup function {func.__name__}: {e}")

        logger.info("Graceful shutdown completed")

    def is_shutdown_in_progress(self) -> bool:
        """Check if shutdown is in progress"""
        return self._shutdown_in_progress


# Global graceful shutdown manager
_graceful_shutdown_manager = GracefulShutdownManager()


def register_cleanup_function(func: Callable[[], None]):
    """Register a cleanup function with the global manager"""
    _graceful_shutdown_manager.register_cleanup_function(func)


def perform_graceful_shutdown(signum: int = None, frame = None):
    """Perform graceful shutdown with the global manager"""
    _graceful_shutdown_manager.shutdown(signum, frame)


def is_graceful_shutdown_in_progress() -> bool:
    """Check if graceful shutdown is in progress"""
    return _graceful_shutdown_manager.is_shutdown_in_progress()


# Integration with signal handler
register_signal_handler(perform_graceful_shutdown)
