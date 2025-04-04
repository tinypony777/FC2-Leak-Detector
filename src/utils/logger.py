"""
日志工具模块，提供统一的日志记录功能
"""
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

from rich.console import Console
from rich.logging import RichHandler

console = Console()

# 配置日志目录
LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs"
)
os.makedirs(LOG_DIR, exist_ok=True)

# 日志格式
FORMAT = "%(levelname)s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"

# 日志级别映射
LOG_LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


# 自定义过滤器类，用于过滤重复日志
class DuplicateFilter(logging.Filter):
    """过滤重复的日志记录"""

    def __init__(self):
        super().__init__()
        self.last_log = None

    def filter(self, record):
        # 创建当前日志的唯一标识（消息内容+级别）
        current_log = f"{record.levelno}:{record.getMessage()}"

        # 如果与上一条日志相同，则过滤掉
        if current_log == self.last_log:
            return False

        # 保存当前日志内容作为下一次比较的基准
        self.last_log = current_log
        return True


def configure_logging(log_level="info", log_file=None, enable_duplicate_filter=True):
    """
    配置日志记录

    参数:
        log_level: 日志级别，默认为info
        log_file: 日志文件路径，默认为None，即不记录到文件
        enable_duplicate_filter: 是否启用日志去重过滤
    """
    # 获取根记录器
    root_logger = logging.getLogger()

    # 设置日志级别
    level = LOG_LEVEL_MAP.get(log_level.lower(), logging.INFO)
    root_logger.setLevel(level)

    # 移除所有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 添加控制台处理器
    console_handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        console=console,
        show_path=False,
        enable_link_path=False,
    )
    console_handler.setFormatter(logging.Formatter(FORMAT))
    console_handler.setLevel(level)

    # 添加日志去重过滤器
    if enable_duplicate_filter:
        console_handler.addFilter(DuplicateFilter())

    root_logger.addHandler(console_handler)

    # 如果指定了日志文件，添加文件处理器
    if log_file:
        file_path = os.path.join(LOG_DIR, log_file)
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_formatter = logging.Formatter(
            "%(asctime)s - " + FORMAT, datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(level)

        # 添加日志去重过滤器
        if enable_duplicate_filter:
            file_handler.addFilter(DuplicateFilter())

        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name):
    """
    获取指定名称的日志记录器

    参数:
        name: 日志记录器名称

    返回:
        Logger: 日志记录器实例
    """
    logger = logging.getLogger(name)
    return logger
