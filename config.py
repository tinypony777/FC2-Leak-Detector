"""
FC2 视频分析器 - 配置模块

包含程序的所有可配置选项，已按功能分类整理。
用户可根据需求调整这些设置以优化程序性能和行为。
"""
import os
import platform
from typing import Any, Dict, List, Tuple, Union, Optional

# -----------------------------------------------
# 路径设置
# -----------------------------------------------

# 获取项目根目录
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# 数据存储基础目录 - 默认使用项目目录下的data文件夹
BASE_CACHE_DIR = os.path.join(ROOT_DIR, "data")


class Config:
    """配置类，用于管理所有配置项"""
    
    _instance = None
    
    def __new__(cls):
        """单例模式，确保全局只有一个Config实例"""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化配置项，只在第一次创建实例时执行"""
        if self._initialized:
            return
            
        self._initialized = True
        
        # -------------------------
        # 基本信息
        # -------------------------
        self.version = "1.1.0"  # 程序版本号
        
        # -------------------------
        # 网络请求设置
        # -------------------------
        # 请求间隔设置 - 防止请求过于频繁导致IP被限制
        self.page_interval = (0.5, 1.2)  # 分页请求间隔时间范围(秒)
        self.request_interval = (0.5, 1.0)  # 普通请求间隔时间范围(秒)
        self.request_limit_count = 20  # 每X次请求后强制等待一次
        # 并发与超时设置
        self.max_workers = 30  # 最大并发线程数 (增加可提升速度，但可能增加被限制风险)
        self.timeout = 15  # 请求超时时间(秒)，网络不稳定时可适当增加
        # 重试策略设置
        self.max_retries = 4  # 最大重试次数，遇到网络问题时会自动重试
        self.retry_base = 2.0  # 重试间隔基数，决定每次重试等待的时间
        
        # -------------------------
        # 缓存设置
        # -------------------------
        self.cache_ttl = 172800  # 缓存有效期(秒)，默认48小时
        
        # -------------------------
        # 数据存储目录设置
        # -------------------------
        self.cache_dir = os.path.join(BASE_CACHE_DIR, "id_cache")  # 作者和女优ID缓存目录
        self.image_dir = os.path.join(BASE_CACHE_DIR, "img")  # 视频缩略图存储目录
        self.result_dir = os.path.join(BASE_CACHE_DIR, "results")  # 分析结果存储目录
        self.magnet_dir = os.path.join(BASE_CACHE_DIR, "magnets")  # 磁链信息存储目录
        self.log_dir = os.path.join(BASE_CACHE_DIR, "logs")  # 日志文件存储目录
        self.summary_report = os.path.join(
            BASE_CACHE_DIR, "fc2_multi_author_summary.txt"
        )  # 多作者汇总报告路径
        
        # -------------------------
        # 视频检查站点设置
        # -------------------------
        self.check_sites = [
            {
                "name": "24AV",
                "url": "https://24av.net/en/dm1/v/fc2-ppv-{vid}",
                "priority": 1,
                "status_codes": [200],
            },
            # 可添加更多检查站点
        ]
        
        # -------------------------
        # API设置
        # -------------------------
        self.fc2ppvdb_api_base = "https://fc2ppvdb.com"  # FC2PPVDB API基础URL
        self.video_api_path = "/writers/writer-articles"  # 获取视频列表的API路径
        self.author_api_path = "/writers/"  # 获取作者信息的API路径
        
        # -------------------------
        # 磁链搜索设置
        # -------------------------
        # 注意：以下设置仅用于演示目的，指向的是公开索引网站
        # 本工具不鼓励用户获取或分享侵犯版权的内容
        # 使用者必须在遵守所在地区法律法规的前提下使用该功能
        self.magnet_search_base = "https://sukebei.nyaa.si/"  # 磁链搜索网站基础URL
        self.magnet_search_path = "?f=0&c=2_2&q=FC2-PPV-{vid}"  # 磁链搜索路径模板
        
        # -------------------------
        # 界面设置
        # -------------------------
        self.ui_refresh_interval = 0.5  # 界面刷新间隔(秒)
        self.progress_color = "green"  # 进度条颜色 (可选: green, blue, yellow, red, cyan, magenta)
        self.error_color = "red"  # 错误信息颜色
        
        # -------------------------
        # 结果输出设置
        # -------------------------
        self.save_format = ["text", "json"]  # 保存格式，可选: "text", "json", 或同时使用
        self.report_batch_size = 100  # 报告中每批显示的视频数量
        
        # -------------------------
        # 高级设置
        # -------------------------
        self.log_level = "INFO"  # 日志级别: DEBUG, INFO, WARNING, ERROR
        self.enable_proxy = False  # 是否启用代理
        self.proxy = {  # 代理设置 (仅当enable_proxy为True时生效)
            "http": "",  # HTTP代理地址
            "https": "",  # HTTPS代理地址
        }
        
        # 浏览器标识轮换，减少访问限制风险
        self.user_agents = [
            # Windows Chrome
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            # macOS Safari
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
            # Windows Firefox
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
            # Linux Chrome
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.6494.65 Safari/537.36",
            # Windows Edge
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
            # Mobile User Agents
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.6558.50 Mobile Safari/537.36",
        ]
        
        # 基础请求头
        self.base_headers = {
            "User-Agent": self.user_agents[0],
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "DNT": "1",  # Do Not Track
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
        }
        
        # API请求头
        self.api_headers = {
            "User-Agent": self.user_agents[0],
            "accept": "*/*",
            "sec-fetch-site": "same-origin",
            "x-requested-with": "XMLHttpRequest",
            "referer": "https://fc2ppvdb.com/",
        }
        
        # 获取系统环境信息
        self.system_info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "python_version": platform.python_version(),
        }
        
        # 根据操作系统调整文件路径长度限制
        if self.system_info["os"] == "Windows":
            self.file_path_max_length = 260  # Windows路径长度限制
        elif self.system_info["os"] == "Darwin":  # macOS
            self.file_path_max_length = 1024
        else:  # Linux和其他系统
            self.file_path_max_length = 4096
            
        # 创建所需目录
        self._create_directories()
    
    def _create_directories(self):
        """创建所需的目录"""
        directories = [
            self.cache_dir,
            self.result_dir,
            self.image_dir,
            self.log_dir,
            self.magnet_dir,
            # 添加基础数据目录
            BASE_CACHE_DIR
        ]
        
        for directory in directories:
            try:
                os.makedirs(directory, exist_ok=True)
            except Exception as e:
                print(f"警告: 无法创建目录 {directory}: {e}")
                
        # 创建.gitkeep文件确保空目录被版本控制
        for directory in directories:
            gitkeep_file = os.path.join(directory, ".gitkeep")
            if not os.path.exists(gitkeep_file):
                try:
                    with open(gitkeep_file, "w") as f:
                        pass  # 创建空文件
                except Exception:
                    pass  # 忽略创建.gitkeep失败的错误
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项，与字典兼容的方法"""
        return getattr(self, key, default)
    
    def set(self, key: str, value: Any) -> None:
        """设置配置项"""
        setattr(self, key, value)
    
    def update(self, config_dict: Dict[str, Any]) -> None:
        """从字典更新多个配置项"""
        for key, value in config_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典形式"""
        result = {}
        for key in dir(self):
            if not key.startswith('_') and not callable(getattr(self, key)):
                result[key] = getattr(self, key)
        return result
    
    def __getitem__(self, key: str) -> Any:
        """支持以字典形式访问配置"""
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"配置项 '{key}' 不存在")
    
    def __setitem__(self, key: str, value: Any) -> None:
        """支持以字典形式设置配置"""
        setattr(self, key, value)


# 创建全局配置实例
config = Config()

