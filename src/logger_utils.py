#!/usr/bin/env python3
"""
Logger utilities for layer-relayer-mvp

Provides colored logging similar to bridge-data-collector
"""

import logging
import sys
import os

# Global flag to track if logging has been configured
_logging_configured = False

class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels"""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # cyan
        'INFO': '\033[32m',     # green
        'WARNING': '\033[33m',  # yellow
        'ERROR': '\033[31m',    # red
        'CRITICAL': '\033[35m', # magenta
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    def __init__(self, use_colors=True):
        super().__init__()
        self.use_colors = use_colors and self._supports_color()
    
    def _supports_color(self):
        """Check if terminal supports colors"""
        return (
            hasattr(sys.stderr, "isatty") and sys.stderr.isatty() and
            os.environ.get('TERM') != 'dumb' and
            os.environ.get('NO_COLOR') is None
        )
    
    def format(self, record):
        if self.use_colors:
            level_color = self.COLORS.get(record.levelname, '')
            level_name = f"{level_color}{self.BOLD}{record.levelname:<8}{self.RESET}"
            
            # format timestamp with subdued color
            timestamp = f"\033[90m{self.formatTime(record, '%H:%M:%S')}\033[0m"
            
            # format module name in cosmos SDK style with "module=" in purple and module name in cyan
            module_label = f"\033[95mmodule\033[0m="  # purple for "module="
            module_value = f"\033[96m{record.name}\033[0m"  # cyan for module name
            module_part = f"{module_label}{module_value}"
            
            return f"{timestamp} {level_name} {record.getMessage()} {module_part}"
        else:
            # fallback to standard format without colors
            return f"{self.formatTime(record, '%Y-%m-%d %H:%M:%S')} - {record.levelname} - {record.getMessage()} module={record.name}"

def setup_logging(verbose=False, no_color=False):
    """Setup logging with colors and appropriate level"""
    global _logging_configured
    
    # Get root logger and clear any existing handlers only if not configured yet
    root_logger = logging.getLogger()
    if not _logging_configured:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # create console handler with colored formatter
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(ColoredFormatter(use_colors=not no_color))
        root_logger.addHandler(console_handler)
        
        # Mark as configured
        _logging_configured = True
    
    # Always update the level based on verbose flag (this allows changing verbose on subcommands)
    level = logging.DEBUG if verbose else logging.INFO
    root_logger.setLevel(level)
    for handler in root_logger.handlers:
        handler.setLevel(level)

    # Clamp noisy third-party libraries to WARNING so they never drown out
    # application logs, even when --verbose is set.
    for noisy_logger in (
        "web3",
        "web3.RequestManager",
        "web3.providers.HTTPProvider",
        "urllib3",
        "urllib3.connectionpool",
    ):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

def get_logger(module_name):
    """Get a logger for a specific module"""
    # Just return a logger - don't configure here to avoid duplicates
    return logging.getLogger(module_name) 