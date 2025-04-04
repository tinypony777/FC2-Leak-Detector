"""
__init__ module for utils package
"""
from src.utils.cache_manager import CacheManager
from src.utils.logger import configure_logging, get_logger
from src.utils.report_generator import ReportGenerator
from src.utils.request_handler import RequestHandler
from src.utils.ui_manager import RichUIManager

# 配置统一的日志记录
configure_logging(log_level="info", log_file=f"fc2analyzer.log")

__all__ = [
    "CacheManager",
    "RequestHandler",
    "ReportGenerator",
    "RichUIManager",
    "get_logger",
    "configure_logging",
]
