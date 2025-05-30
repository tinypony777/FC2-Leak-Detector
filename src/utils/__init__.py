"""
__init__ module for utils package
"""
import os
from config import config
from src.utils.cache_manager import CacheManager
from src.utils.logger import configure_logging, get_logger, get_analysis_logger, get_error_logger
from src.utils.report_generator import ReportGenerator
from src.utils.request_handler import RequestHandler
from src.utils.ui_manager import RichUIManager

# 配置统一的日志记录
configure_logging(
    log_level=config.log_level,
    # 不再指定log_file，让logger模块自动创建带日期的日志文件
)

__all__ = [
    "CacheManager",
    "RequestHandler",
    "ReportGenerator",
    "RichUIManager",
    "get_logger",
    "get_analysis_logger",
    "get_error_logger",
    "configure_logging",
]
