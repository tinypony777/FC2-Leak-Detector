"""
日志工具模块，提供统一的日志记录功能
"""
import logging
import os
import sys
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

from rich.console import Console
from rich.logging import RichHandler

from config import config

console = Console()

# 配置日志目录结构
LOG_BASE_DIR = config.log_dir
LOG_APP_DIR = os.path.join(LOG_BASE_DIR, "app")
LOG_ANALYSIS_DIR = os.path.join(LOG_BASE_DIR, "analysis")
LOG_ERROR_DIR = os.path.join(LOG_BASE_DIR, "errors")

# 确保所有日志目录存在
for log_dir in [LOG_BASE_DIR, LOG_APP_DIR, LOG_ANALYSIS_DIR, LOG_ERROR_DIR]:
    os.makedirs(log_dir, exist_ok=True)

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

    # 如果未指定日志文件，使用默认的应用程序日志文件
    if not log_file:
        # 创建带有日期的日志文件名
        today = datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(LOG_APP_DIR, f"fc2analyzer_{today}.log")

    # 添加文件处理器
    # 使用日期轮换处理器
    file_handler = TimedRotatingFileHandler(
        log_file,
        when='midnight',  # 每天午夜轮换
        interval=1,       # 每1天
        backupCount=30,   # 保留30天
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


def get_analysis_logger(name, entity_id=None):
    """
    获取用于记录分析结果的日志记录器
    
    参数:
        name: 日志记录器名称
        entity_id: 实体ID（作者ID或女优ID）
        
    返回:
        Logger: 分析日志记录器实例
    """
    logger = logging.getLogger(f"analysis.{name}")
    
    # 检查是否已经有处理器，避免重复添加
    if not logger.handlers:
        # 创建分析日志文件名
        today = datetime.now().strftime("%Y%m%d")
        if entity_id:
            log_file = os.path.join(LOG_ANALYSIS_DIR, f"{name}_{entity_id}_{today}.log")
        else:
            log_file = os.path.join(LOG_ANALYSIS_DIR, f"{name}_{today}.log")
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_formatter = logging.Formatter(
            "%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_error_logger(name):
    """
    获取用于记录错误的日志记录器
    
    参数:
        name: 日志记录器名称
        
    返回:
        Logger: 错误日志记录器实例
    """
    logger = logging.getLogger(f"error.{name}")
    
    # 检查是否已经有处理器，避免重复添加
    if not logger.handlers:
        # 创建错误日志文件名
        today = datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(LOG_ERROR_DIR, f"error_{name}_{today}.log")
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.ERROR)  # 只记录错误及以上级别
        logger.addHandler(file_handler)
    
    return logger
