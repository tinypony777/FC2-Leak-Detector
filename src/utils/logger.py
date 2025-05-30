"""
日志工具模块，提供统一的日志记录功能

特性：
1. 支持控制台彩色日志输出
2. 支持文件日志记录（按日期自动轮转）
3. 支持日志去重过滤
4. 支持不同类型的日志（应用、分析、错误）分别存储
"""
import logging
import os
import sys
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

from rich.console import Console
from rich.logging import RichHandler

from config import config

# 创建Rich控制台对象
console = Console()

# 从配置中获取日志目录结构
LOG_BASE_DIR = config.log_dir
LOG_APP_DIR = config.log_app_dir
LOG_ANALYSIS_DIR = config.log_analysis_dir
LOG_ERROR_DIR = config.log_error_dir

# 日志格式从配置中获取
CONSOLE_FORMAT = config.log_console_format
FILE_FORMAT = config.log_file_format
ERROR_FORMAT = config.log_error_format
ANALYSIS_FORMAT = config.log_analysis_format

# 日志日期格式从配置中获取
LOG_DATE_FORMAT = config.log_date_format
LOG_DATETIME_FORMAT = config.log_datetime_format
LOG_TIMESTAMP_FORMAT = config.log_timestamp_format
LOG_USE_DATETIME = config.log_use_datetime

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
    """过滤重复的日志记录，避免日志文件中出现大量重复内容"""

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


def configure_logging(log_level=None, log_file=None, enable_duplicate_filter=None):
    """
    配置日志记录系统

    参数:
        log_level: 日志级别，默认从配置获取
        log_file: 日志文件路径，默认为None时使用自动生成的路径
        enable_duplicate_filter: 是否启用日志去重过滤，默认从配置获取
    
    返回:
        Logger: 配置好的根日志记录器
    """
    # 使用默认配置（如果未指定参数）
    if log_level is None:
        log_level = config.log_level.lower()
    
    if enable_duplicate_filter is None:
        enable_duplicate_filter = config.log_enable_duplicate_filter
    
    # 获取根记录器
    root_logger = logging.getLogger()

    # 设置日志级别
    level = LOG_LEVEL_MAP.get(log_level.lower(), logging.INFO)
    root_logger.setLevel(level)

    # 移除所有处理器（避免重复）
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 添加控制台处理器（如果配置允许）
    if config.log_enable_console:
        console_handler = RichHandler(
            rich_tracebacks=True,
            markup=True,
            console=console,
            show_path=False,
            enable_link_path=False,
        )
        console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))
        console_handler.setLevel(level)

        # 添加日志去重过滤器（如果启用）
        if enable_duplicate_filter:
            console_handler.addFilter(DuplicateFilter())

        root_logger.addHandler(console_handler)

    # 如果未指定日志文件，使用默认的应用程序日志文件
    if not log_file:
        # 根据配置决定使用日期格式还是日期时间格式
        if LOG_USE_DATETIME:
            # 创建带有精确到秒的时间戳的日志文件名
            timestamp = datetime.now().strftime(LOG_DATETIME_FORMAT)
            log_file = os.path.join(LOG_APP_DIR, f"fc2analyzer_{timestamp}.log")
        else:
            # 创建只带日期的日志文件名
            today = datetime.now().strftime(LOG_DATE_FORMAT)
            log_file = os.path.join(LOG_APP_DIR, f"fc2analyzer_{today}.log")

    # 添加文件处理器
    # 使用日期轮换处理器
    file_handler = TimedRotatingFileHandler(
        log_file,
        when=config.log_rotation,     # 轮转时间点（从配置获取）
        interval=1,                   # 每1个时间单位
        backupCount=config.log_backup_count,  # 保留的备份数量
        encoding="utf-8",
    )
    file_formatter = logging.Formatter(
        FILE_FORMAT, datefmt=LOG_TIMESTAMP_FORMAT
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(level)

    # 添加日志去重过滤器（如果启用）
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
        name: 日志记录器名称（通常是'writer'或'actress'）
        entity_id: 实体ID（作者ID或女优ID）
        
    返回:
        Logger: 分析日志记录器实例
    """
    logger = logging.getLogger(f"analysis.{name}")
    
    # 检查是否已经有处理器，避免重复添加
    if not logger.handlers:
        # 根据配置决定使用日期格式还是日期时间格式
        if LOG_USE_DATETIME:
            # 创建带有精确到秒的时间戳的日志文件名
            timestamp = datetime.now().strftime(LOG_DATETIME_FORMAT)
            if entity_id:
                log_file = os.path.join(LOG_ANALYSIS_DIR, f"{name}_{entity_id}_{timestamp}.log")
            else:
                log_file = os.path.join(LOG_ANALYSIS_DIR, f"{name}_{timestamp}.log")
        else:
            # 创建只带日期的日志文件名
            today = datetime.now().strftime(LOG_DATE_FORMAT)
            if entity_id:
                log_file = os.path.join(LOG_ANALYSIS_DIR, f"{name}_{entity_id}_{today}.log")
            else:
                log_file = os.path.join(LOG_ANALYSIS_DIR, f"{name}_{today}.log")
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_formatter = logging.Formatter(
            ANALYSIS_FORMAT, datefmt=LOG_TIMESTAMP_FORMAT
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_error_logger(name):
    """
    获取用于记录错误的日志记录器
    
    参数:
        name: 日志记录器名称（通常是组件名如'magnetfetch'）
        
    返回:
        Logger: 错误日志记录器实例
    """
    logger = logging.getLogger(f"error.{name}")
    
    # 检查是否已经有处理器，避免重复添加
    if not logger.handlers:
        # 根据配置决定使用日期格式还是日期时间格式
        if LOG_USE_DATETIME:
            # 创建带有精确到秒的时间戳的日志文件名
            timestamp = datetime.now().strftime(LOG_DATETIME_FORMAT)
            log_file = os.path.join(LOG_ERROR_DIR, f"error_{name}_{timestamp}.log")
        else:
            # 创建只带日期的日志文件名
            today = datetime.now().strftime(LOG_DATE_FORMAT)
            log_file = os.path.join(LOG_ERROR_DIR, f"error_{name}_{today}.log")
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_formatter = logging.Formatter(
            ERROR_FORMAT, datefmt=LOG_TIMESTAMP_FORMAT
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.ERROR)  # 只记录错误及以上级别
        logger.addHandler(file_handler)
    
    return logger
