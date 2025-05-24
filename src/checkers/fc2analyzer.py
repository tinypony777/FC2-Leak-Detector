"""
FC2流出检测器 - 视频状态检查与数据处理的核心模块

提供全面的FC2视频分析功能，支持视频状态检查、磁力链接获取和缩略图下载，
可处理单个视频或批量视频，支持多线程并行处理以提高效率
"""
import json
import os
import random
import re
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table, box

from config import config
from src.utils import get_logger
from src.utils.cache_manager import CacheManager
from src.utils.request_handler import RequestHandler
from src.utils.i18n import get_text as _

# 创建console实例
console = Console()

# 获取日志记录器
logger = get_logger("fc2analyzer")

# 忽略警告
warnings.filterwarnings("ignore")

class FC2Analyzer:
    """FC2流出检测器，检查FC2视频的状态和获取相关信息"""

    def __init__(
        self,
        write_id=None,
        ui_manager=None,
        name=None,
        download_path=None,
        with_magnet=True,
        download_images=True,
        quiet_mode=False,
        is_actress=False,
    ):
        """
        初始化FC2分析器

        参数:
            write_id: 作者ID或女优ID
            ui_manager: UI管理器
            name: 作者名称或女优名称
            download_path: 下载路径
            with_magnet: 是否获取磁力链接
            download_images: 是否下载图片
            quiet_mode: 是否安静模式
            is_actress: 是否为女优ID
        """
        self.write_id = write_id
        self.name = name
        self.ui_manager = ui_manager
        self.is_actress = is_actress  # 标记是否为女优ID

        # 设置下载路径
        self.download_path = download_path or config.image_dir
        os.makedirs(self.download_path, exist_ok=True)

        # 设置是否下载磁力链接和图片
        self.with_magnet = with_magnet
        self.download_images = download_images
        self.quiet_mode = quiet_mode

        # 创建线程锁，用于多线程安全
        self.lock = threading.Lock()

        # 初始化统计信息
        self.stats = {
            "total": 0,  # 总视频数
            "processed": 0,  # 已处理视频数
            "available": 0,  # 可用视频数
            "unavailable": 0,  # 不可用视频数
            "errors": 0,  # 错误数
            "with_magnet": 0,  # 有磁力链接的视频数
            "without_magnet": 0,  # 无磁力链接的视频数
            "image_success": 0,  # 图片下载成功数
            "image_fail": 0,  # 图片下载失败数
            "magnet_success": 0,  # 磁力链接获取成功数
            "magnet_fail": 0,  # 磁力链接获取失败数
            "magnet_not_found": 0,  # 未找到磁力链接数
            # 新增重试相关统计
            "magnet_retries": 0,  # 磁力链接重试总次数
            "image_retries": 0,  # 图片下载重试总次数
            "magnet_retry_success": 0,  # 磁力链接重试成功次数
            "image_retry_success": 0,  # 图片下载重试成功次数
        }

        # 直接使用统一的日志模块
        from src.utils.logger import get_logger

        self.logger = get_logger(f"fc2analyzer.{write_id if write_id else 'main'}")

        # 其他初始化保持不变
        self.base_url = f"{config.fc2ppvdb_api_base}/api/v1"

        # 数据存储
        self.all_videos = []  # 所有视频信息

        # 请求控制参数
        self.request_interval = config.request_interval
        self.page_interval = config.page_interval
        self.max_retries = config.max_retries
        self.retry_base = config.retry_base

        # 基础设置
        self.magnet_base_url = config.magnet_search_base
        self.magnet_search_path = config.magnet_search_path

        # 目录设置
        self.cache_dir = config.cache_dir
        self.image_dir = config.image_dir
        self.magnet_dir = config.magnet_dir
        self.result_dir = config.result_dir

        # 获取检查站点列表并按优先级排序
        self.check_sites = sorted(
            config.check_sites, key=lambda x: x.get("priority", 99)
        )

    def fetch_author_name(self, max_retries=3):
        """专门用于获取作者/女优名称的方法，包含重试机制

        Args:
            max_retries: 最大重试次数

        Returns:
            str: 作者/女优名称
        """
        if hasattr(self, "name") and self.name:
            return self.name

        self.name = None  # 初始化属性

        # 根据不同类型使用不同的URL和提取方式
        base_url = config.fc2ppvdb_api_base

        # 根据是否是女优，设置不同的API路径和参数
        if self.is_actress:
            entity_type = "actresses"
            entity_id_param = "actressid"
            entity_desc = "女优"
            api_path = "actresses/actress-articles"  # 使用单数形式
        else:
            entity_type = "writers"
            entity_id_param = "writerid"
            entity_desc = "作者"
            api_path = (
                "writers/writer-articles"  # 修正：使用单数形式writer-articles而非writers-articles
            )

        for attempt in range(max_retries):
            try:
                # 直接从API获取名称（最可靠的方法）
                api_url = (
                    f"{base_url}/{api_path.lstrip('/')}?{entity_id_param}={self.write_id}&page=1"
                )
                print(f"名称获取URL: {api_url}")  # 调试信息
                api_response = RequestHandler.make_request(
                    api_url,
                    headers=config.api_headers,
                    step_name=f"API获取{entity_desc}名称[第{attempt+1}次]",
                )

                if api_response and api_response.status_code == 200:
                    try:
                        data = json.loads(api_response.text)
                        if "data" in data and len(data["data"]) > 0:
                            for article in data["data"]:
                                entity_key = entity_type[:-1]  # 'writer' or 'actress'
                                if (
                                    entity_key in article
                                    and article[entity_key]
                                    and "name" in article[entity_key]
                                ):
                                    self.name = article[entity_key]["name"]
                                    console.print(
                                        f"[bold green]✅ 从API获取到{entity_desc}名称:[/bold green] [cyan]{self.name}[/cyan]"
                                    )
                                    return self.name
                    except Exception as e:
                        console.print(f"[yellow]⚠️ API数据解析失败: {str(e)}[/yellow]")

                # 如果API获取失败，尝试其他方法
                entity_url = f"{base_url}/{entity_type.lstrip('/')}/{self.write_id}"
                response = RequestHandler.make_request(
                    entity_url,
                    headers=config.api_headers,
                    step_name=f"获取{entity_desc}名称[第{attempt+1}次]",
                )

                if response and response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")

                    # 优先从info部分获取
                    info_selector = f".{entity_type[:-1]}-info h3, .{entity_type[:-1]} h3, .user-info h3"
                    info_elem = soup.select_one(info_selector)
                    if info_elem and info_elem.text.strip():
                        self.name = info_elem.text.strip()
                        console.print(
                            f"[bold green]✅ 从页面信息获取到{entity_desc}名称:[/bold green] [cyan]{self.name}[/cyan]"
                        )
                        return self.name

                    # 尝试从页面标题获取
                    title = soup.select_one("title")
                    if title:
                        title_text = title.text.strip()
                        # 标题通常格式为: "名称 - FC2-PPV-DB"
                        if " - " in title_text:
                            self.name = title_text.split(" - ")[0].strip()
                            console.print(
                                f"[bold green]✅ 从页面标题获取到{entity_desc}名称:[/bold green] [cyan]{self.name}[/cyan]"
                            )
                            return self.name

                    # 尝试查找任何可能包含名称的元素
                    possible_elements = soup.select(
                        "h1, h2, h3, .profile-name, .user-name"
                    )
                    for elem in possible_elements:
                        text = elem.text.strip()
                        if text and len(text) < 30:  # 假设名称不会太长
                            self.name = text
                            console.print(
                                f"[bold green]✅ 从页面元素获取到{entity_desc}名称:[/bold green] [cyan]{self.name}[/cyan]"
                            )
                            return self.name

            except Exception as e:
                print(f"❌ 获取{entity_desc}名称时出错: {str(e)}")
                if attempt < max_retries - 1:  # 如果不是最后一次尝试
                    wait_time = (2**attempt) + random.uniform(1, 3)
                    print(f"等待 {wait_time:.1f} 秒后重试...")
                    time.sleep(wait_time)

        # 如果所有尝试都失败，使用ID作为名称
        id_prefix = "Actress" if self.is_actress else "Writer"
        self.name = f"{id_prefix}_{self.write_id}"
        print(f"⚠️ 无法获取{entity_desc}名称，使用ID: {self.name}")
        return self.name

    def fetch_video_ids(self):
        """获取作者/女优的所有视频ID

        首先尝试从缓存加载视频列表，如果缓存不存在或已过期，
        则从FC2PPVDB API获取所有视频信息。

        Returns:
            list: 包含视频信息的列表
        """
        # 根据类型设置不同的API路径和参数
        if self.is_actress:
            # 女优使用特定的API路径
            entity_type = "actresses"
            entity_id_param = "actressid"
            entity_desc = "女优"
            api_path = "/actresses/actress-articles"
            print(f"[调试] 使用女优API路径: {api_path}")
        else:
            # 作者使用常规API路径
            entity_type = "writers"
            entity_id_param = "writerid"
            entity_desc = "作者"
            api_path = "/writers/writer-articles"
            print(f"[调试] 使用作者API路径: {api_path}")

        # 首先尝试从缓存中加载
        cached_videos = CacheManager.load(self.write_id, self.is_actress)
        if cached_videos:
            self.stats["total"] = len(cached_videos)
            print(f"✅ 从缓存中读取到 {self.stats['total']} 个视频")
            return cached_videos

        print(f"🔄 开始获取{entity_desc} {self.write_id} 的视频列表...")
        all_videos = []
        page = 1

        # 确保API基础URL配置正确
        api_base = config.fc2ppvdb_api_base

        while True:
            try:
                # 从API获取视频列表
                api_url = f"{api_base}/{api_path.lstrip('/')}"
                print(f"请求URL: {api_url}?{entity_id_param}={self.write_id}&page={page}")
                response = requests.get(
                    api_url,
                    params={
                        entity_id_param: self.write_id,
                        "page": page,
                        "per_page": 100,
                    },
                    headers=config.api_headers,
                )

                if response.status_code != 200:
                    print(f"❌ API请求失败: {response.status_code}")
                    break

                data = response.json()
                if not data.get("data"):
                    print(f"⚠️ API返回数据为空，可能该{entity_desc}没有视频")
                    break

                # 记录API返回的第一个视频数据结构（用于调试）
                if page == 1 and len(data.get("data", [])) > 0:
                    sample_video = data["data"][0]
                    print(f"\n[调试] {entity_desc}API返回的视频数据示例:")
                    for key, value in sample_video.items():
                        if key not in ["search_data", "pivot"]:  # 跳过太长的字段
                            print(f"  - {key}: {value}")
                    print("")

                # 处理视频数据
                for video in data["data"]:
                    try:
                        # 根据不同实体类型处理视频数据
                        if self.is_actress:
                            # 女优API的特殊处理 - 使用专门的字段
                            if "video_id" not in video:
                                print(f"⚠️ 女优视频数据中找不到video_id字段，跳过")
                                continue

                            video_id = str(video["video_id"])
                            title = video.get("title", f"FC2-PPV-{video_id}")

                            # 直接使用API返回的image_url，仅添加基础URL
                            image_url = video.get("image_url", "")
                            if image_url and not image_url.startswith(
                                ("http://", "https://")
                            ):
                                image_url = f"{api_base}/storage/{image_url}"

                            print(f"[调试] 女优视频: ID={video_id}, 图片URL={image_url}")

                            video_info = {
                                "video_id": video_id,
                                "title": title,
                                "image_url": image_url,
                                "author_name": self.name
                                or f"{entity_desc}_{self.write_id}",
                            }
                        else:
                            # 作者数据处理 - 尝试查找video_id字段
                            video_id = None
                            for id_field in [
                                "video_id",
                                "id",
                                "articleid",
                                "article_id",
                                "videoid",
                            ]:
                                if id_field in video:
                                    video_id = str(video[id_field])
                                    print(
                                        f"[调试] 作者视频: 使用字段 '{id_field}' 获取ID={video_id}"
                                    )
                                    break

                            # 如果没有找到，尝试第一个数字类型的字段
                            if video_id is None:
                                for key, value in video.items():
                                    if (
                                        isinstance(value, (int, str))
                                        and str(value).isdigit()
                                    ):
                                        video_id = str(value)
                                        print(
                                            f"[调试] 作者视频: 使用字段 '{key}' 作为ID={video_id}"
                                        )
                                        break

                            # 如果还是没找到ID，则跳过此视频
                            if video_id is None:
                                print(f"⚠️ 无法确定作者视频ID，跳过此视频数据")
                                continue

                            # 处理图片URL - 使用算法构建
                            first_digit = video_id[0]
                            first_part = f"00{first_digit}"
                            second_part = video_id[1:3]
                            image_url = f"{api_base}/storage/thumbs/article/{first_part}/{second_part}/fc2ppv-{video_id}.jpg"

                            video_info = {
                                "video_id": video_id,
                                "title": video.get("title", f"FC2-PPV-{video_id}"),
                                "image_url": image_url,
                                "author_name": self.name
                                or f"{entity_desc}_{self.write_id}",
                            }

                        all_videos.append(video_info)

                    except Exception as e:
                        print(f"⚠️ 处理单个视频数据时出错: {str(e)}")
                        continue

                # 检查是否还有更多页
                if data.get("next_page_url") is None:
                    break

                page += 1
                time.sleep(random.uniform(1, 3))  # 随机延迟
            except Exception as e:
                print(f"❌ 获取视频列表页面 {page} 时出错: {str(e)}")
                break

        # 完成获取所有视频
        total_videos = len(all_videos)
        if total_videos > 0:
            print(f"✅ 已获取 {total_videos} 个视频，开始保存缓存...")
            self.all_videos = all_videos
            self.stats["total"] = total_videos

            # 调试打印前5个视频的ID，确认数据正确
            print("\n[调试] 前5个视频ID和图片URL示例:")
            for i, v in enumerate(all_videos[: min(5, len(all_videos))]):
                print(
                    f"  {i+1}. video_id: {v['video_id']}, image_url: {v['image_url']}"
                )
            print("")

            # 保存到缓存
            CacheManager.save(self.write_id, all_videos, self.is_actress)
            return all_videos
        else:
            print(f"⚠️ 未找到任何视频，请检查{entity_desc}ID是否正确")
            return []

    def check_video_status(self, video_id):
        """
        检查视频状态，判断是否可用

        参数:
            video_id: 视频ID

        返回:
            str: 视频状态 ('available', 'unavailable', 'error')
        """
        try:
            # 使用RequestHandler统一的视频检查方法
            from src.utils.request_handler import RequestHandler

            is_leaked, site_name, status_code = RequestHandler.check_video_leak_status(
                video_id
            )

            # 映射结果到现有的返回格式
            if is_leaked:
                self.logger.info(
                    f"视频 {video_id} 在站点 {site_name} 的响应码为 {status_code}，视频已流出"
                )
                return "available"
            else:
                # 如果未找到视频，视为未流出
                self.logger.info(f"视频 {video_id} 未在任何站点找到，视频未流出")
                return "unavailable"

        except Exception as e:
            # 记录错误
            self.logger.error(f"检查视频 {video_id} 状态出错: {str(e)}")
            # 连接错误、超时等异常情况也应该保守处理为未流出
            return "unavailable"

    def _parse_size(self, size_str):
        """解析文件大小字符串为字节数"""
        size_str = size_str.lower().strip()
        if not size_str:
            return 0

        multipliers = {
            "b": 1,
            "kb": 1024,
            "k": 1024,
            "mb": 1024**2,
            "m": 1024**2,
            "gb": 1024**3,
            "g": 1024**3,
            "tb": 1024**4,
            "t": 1024**4,
        }

        # 匹配数字和单位
        match = re.match(r"([0-9.]+)\s*([a-z]+)", size_str)
        if not match:
            return 0

        size, unit = match.groups()

        # 确保单位在我们的映射中
        if unit not in multipliers:
            return 0

        try:
            return float(size) * multipliers[unit]
        except (ValueError, TypeError):
            return 0

    def fetch_magnet_link(self, video_id):
        """获取视频的磁力链接，按文件大小排序且使用三级重试策略"""
        if not self.with_magnet:
            return []

        self.logger.info(f"准备获取视频 {video_id} 的磁力链接")

        try:
            # 构建搜索URL
            search_url = urljoin(
                self.magnet_base_url, self.magnet_search_path.format(vid=video_id)
            )

            # 三级重试策略
            backoff_strategy = [
                random.uniform(1.5, 3.0),  # 第1次重试（1.5-3秒）
                random.uniform(3.0, 6.0),  # 第2次重试（3-6秒）
                random.uniform(6.0, 12.0),  # 第3次重试（6-12秒）
            ]

            max_retries = min(len(backoff_strategy), config.max_retries)

            for attempt in range(max_retries + 1):  # +1是初始尝试
                try:
                    # 仅在重试时显示信息并使用退避策略
                    if attempt > 0:
                        self.logger.info(
                            f"正在重试获取磁力链接({attempt}/{max_retries}): {video_id}"
                        )
                        delay = backoff_strategy[attempt - 1]
                        self.logger.info(f"等待 {delay:.2f} 秒后重试...")
                        time.sleep(delay)
                        # 记录重试统计
                        with self.lock:
                            self.stats["magnet_retries"] += 1

                    # 确保请求间隔≥5秒
                    current_time = time.time()
                    if hasattr(self, "last_request_time"):
                        elapsed = current_time - self.last_request_time
                        if elapsed < 5.0:
                            time.sleep(5.0 - elapsed)
                    self.last_request_time = current_time

                    response = requests.get(
                        search_url,
                        headers=config.api_headers,
                        timeout=config.timeout,
                    )

                    # 智能状态码处理
                    if response.status_code in [429, 403]:
                        wait_time = (2**attempt) + random.uniform(1.0, 3.0)
                        self.logger.warning(
                            f"受到限流或访问拒绝 (状态码: {response.status_code})，等待 {wait_time:.2f} 秒后重试"
                        )
                        time.sleep(wait_time)
                        continue

                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, "html.parser")
                        # 获取种子列表表格
                        torrent_table = soup.select_one("table.torrent-list")

                        if not torrent_table:
                            self.logger.warning(f"未找到种子列表表格")
                            continue

                        # 收集有效的条目
                        valid_entries = []

                        # 遍历表格行
                        for row in torrent_table.select("tbody tr"):
                            try:
                                # 获取磁力链接
                                magnet_link = row.select_one('a[href^="magnet:"]')
                                # 获取文件大小单元格
                                size_cell = row.select_one(
                                    "td.text-center:nth-of-type(4)"
                                )
                                # 获取标题链接
                                title_link = row.select_one(
                                    'td[colspan="2"] a'
                                ) or row.select_one('a[href^="/view"]')

                                if not all([magnet_link, size_cell, title_link]):
                                    continue

                                # 解析文件大小
                                raw_size = size_cell.text.strip()
                                if not raw_size:
                                    continue

                                # 解析大小为字节数
                                parsed_size = self._parse_size(raw_size)

                                # 添加到有效条目
                                valid_entries.append(
                                    {
                                        "size": parsed_size,
                                        "magnet": magnet_link["href"],
                                        "title": title_link.text.strip(),
                                        "raw_size": raw_size,
                                    }
                                )
                            except Exception as e:
                                continue

                        # 如果有有效条目，按大小排序并返回
                        if valid_entries:
                            # 按文件大小降序排序（优先大文件）
                            valid_entries.sort(key=lambda x: x["size"], reverse=True)

                            # 提取前1个磁链（体积最大的）
                            selected_entries = valid_entries[:1]

                            # 如果是重试后成功，更新重试成功统计
                            if attempt > 0:
                                with self.lock:
                                    self.stats["magnet_retry_success"] += 1

                            # 在非安静模式下输出
                            if not hasattr(self, "quiet_mode") or not self.quiet_mode:
                                console.print(
                                    f"[green]找到 {len(selected_entries)} 个磁力链接，选择体积最大的[/green]"
                                )

                            with self.lock:
                                self.stats["magnet_success"] += 1

                            # 返回磁链列表
                            return [entry["magnet"] for entry in selected_entries]
                        else:
                            self.logger.warning(f"未找到视频 {video_id} 的磁力链接")
                    else:
                        self.logger.warning(f"获取磁力链接响应失败，状态码: {response.status_code}")

                except (
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                ) as e:
                    self.logger.warning(f"网络错误: {str(e)}")
                    # 网络错误自动重试（由外层循环控制）
                except Exception as e:
                    self.logger.error(f"获取磁力链接异常: {str(e)}")
                    if attempt == max_retries:
                        self._save_error_log(
                            video_id,
                            search_url,
                            response if "response" in locals() else None,
                            str(e),
                        )

            # 如果所有重试都失败
            with self.lock:
                self.stats["magnet_fail"] += 1
                self.stats["magnet_not_found"] += 1
            return []

        except Exception as e:
            self.logger.error(f"获取磁力链接异常: {str(e)}")
            with self.lock:
                self.stats["magnet_fail"] += 1
            return []

    def _save_error_log(self, video_id, url, response=None, error_msg=None):
        """保存详细的错误日志"""
        try:
            error_dir = os.path.join(config.log_dir, "error_details")
            os.makedirs(error_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{video_id}_{timestamp}.log"
            filepath = os.path.join(error_dir, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"视频ID: {video_id}\n")
                f.write(f"请求URL: {url}\n")
                f.write(
                    f"响应状态: {response.status_code if response else 'No Response'}\n"
                )
                if error_msg:
                    f.write(f"错误信息: {error_msg}\n")
                f.write("\n响应内容:\n")
                if response:
                    f.write(
                        response.text[:10000]
                        + ("..." if len(response.text) > 10000 else "")
                    )
                else:
                    f.write("无响应内容")

            self.logger.info(f"已保存错误详情: {filepath}")
        except Exception as e:
            self.logger.error(f"保存错误日志失败: {str(e)}")

    def download_image(self, video_id):
        """下载视频缩略图，正确区分流出和未流出状态"""
        try:
            if not self.download_images:
                return None

            # 存储图片URL和视频状态
            image_url = None
            video_status = None
            video_title = None

            # 提取video_id和其他信息
            if isinstance(video_id, dict):
                video_obj = video_id
                extracted_id = str(video_obj.get("video_id", ""))
                image_url = video_obj.get("image_url")
                video_status = video_obj.get("status")
                video_title = video_obj.get("title", f"FC2-PPV-{extracted_id}")
                video_id = extracted_id
            else:
                video_id = str(video_id)
                # 如果只有ID，需要获取状态
                if not video_status:
                    video_status = self.check_video_status(video_id)

            # 检查video_id有效性
            if not video_id or not video_id.isdigit():
                self.logger.error(f"无效的视频ID: {video_id}")
                return None

            # 创建基于作者/女优的目录结构
            entity_type = "actress" if self.is_actress else "author"
            entity_name = self.name or ("未知女优" if self.is_actress else "未知作者")
            entity_name = self.clean_filename(entity_name)

            # 构建唯一目录名
            entity_dir = os.path.join(
                self.download_path, f"{entity_type}_{self.write_id}_{entity_name}"
            )

            # 正确分类流出状态 - "available" 对应已流出，应该放在leaked目录
            # 增加更严格的判断逻辑，确保正确识别视频状态
            is_leaked = False
            if video_status == "available":
                is_leaked = True
            elif isinstance(video_status, bool):
                is_leaked = video_status
            elif isinstance(video_status, str) and video_status.lower() in [
                "true",
                "leaked",
                "yes",
            ]:
                is_leaked = True

            # 注意：在日志中正确记录流出状态
            status_desc = "已流出" if is_leaked else "未流出"

            status_dir = os.path.join(entity_dir, "leaked" if is_leaked else "unleaked")
            os.makedirs(status_dir, exist_ok=True)

            # 构造图片文件名 [视频ID].jpg
            file_ext = ".jpg"  # 默认扩展名
            if image_url:
                url_path = urlparse(image_url).path
                if "." in url_path:
                    ext = os.path.splitext(url_path)[1].lower()
                    if ext:
                        file_ext = ext

            save_path = os.path.join(status_dir, f"{video_id}{file_ext}")
            self.logger.info(f"图片保存路径: {save_path}, 流出状态: {status_desc}")

            # 检查是否已存在(重复下载保护)
            if os.path.exists(save_path):
                self.logger.info(f"缩略图已存在，跳过下载: {save_path}")
                # 修改：将已存在的图片也计入下载成功的统计
                with self.lock:
                    self.stats["image_success"] += 1
                return save_path

            # 如果没有图片URL，则需要构建
            if not image_url:
                # 第二种方法：根据ID构建直接URL（更可靠但可能不是最新的）
                video_id_str = str(video_id)
                first_part = video_id_str[:-3]  # 除了最后3位
                second_part = video_id_str[-3:]  # 最后3位
                
                image_url = f"{config.fc2ppvdb_api_base}/storage/thumbs/article/{first_part}/{second_part}/fc2ppv-{video_id}.jpg"

            # 三级重试策略
            backoff_strategy = [
                random.uniform(1.5, 3.0),
                random.uniform(3.0, 6.0),
                random.uniform(6.0, 12.0),
            ]

            max_retries = min(len(backoff_strategy), config.max_retries)

            for attempt in range(max_retries + 1):
                try:
                    # 重试逻辑...
                    if attempt > 0:
                        self.logger.info(
                            f"正在重试下载图片({attempt}/{max_retries}): {video_id}"
                        )
                        delay = backoff_strategy[attempt - 1]
                        self.logger.info(f"等待 {delay:.2f} 秒后重试...")
                        time.sleep(delay)
                        with self.lock:
                            self.stats["image_retries"] += 1

                    response = requests.get(
                        image_url,
                        headers=config.api_headers,
                        timeout=config.timeout,
                    )

                    # 检查响应
                    if response.status_code == 200:
                        # 保存图片
                        with open(save_path, "wb") as f:
                            f.write(response.content)

                        if attempt > 0:
                            with self.lock:
                                self.stats["image_retry_success"] += 1

                        with self.lock:
                            self.stats["image_success"] += 1

                        return save_path
                    else:
                        self.logger.warning(f"下载图片失败，状态码: {response.status_code}")
                except Exception as e:
                    self.logger.error(f"下载图片异常: {str(e)}")

            # 如果所有重试都失败
            with self.lock:
                self.stats["image_fail"] += 1
            return None

        except Exception as e:
            self.logger.error(f"下载视频 {video_id} 图片出错: {str(e)}")
            with self.lock:
                self.stats["image_fail"] += 1
            return None

    def clean_filename(self, name):
        """清理文件名中的非法字符"""
        if not name:
            return ""

        # 先用replace方法手动替换所有可能的非法字符
        cleaned = name
        for char in ["\\", "/", "*", "?", ":", '"', "<", ">", "|"]:
            cleaned = cleaned.replace(char, "_")

        # 再用正则表达式进行一次替换以确保安全
        cleaned = re.sub(r'[\\/*?:"<>|]', "_", cleaned).strip(". ")

        # 限制长度
        if len(cleaned) > 50:
            cleaned = cleaned[:50] + "..."

        return cleaned

    def generate_reports(self, writer_id, results, writer_name=None):
        """生成多种格式的标准化报告，区分作者和女优"""
        try:
            if not results:
                self.logger.warning("没有结果可供生成报告")
                return {}

            # 清理和准备实体名称（作者或女优）
            entity_name = (
                writer_name or self.name or ("未知女优" if self.is_actress else "未知作者")
            )

            # 调试输出 - 不再输出重复日志
            self.logger.info(f"=== 生成报告 ===")
            self.logger.info(f"原始writer_name: '{writer_name}'")
            self.logger.info(f"原始self.name: '{self.name}'")
            self.logger.info(f"使用的entity_name: '{entity_name}'")

            # 创建唯一前缀，区分作者和女优，但保持文件名结构一致
            # 修改：无论是作者还是女优，统一使用"author"为前缀格式，保持一致性
            entity_type = "author"

            # 检查是否包含特殊字符，如果包含则只使用ID
            has_special_chars = any(
                c in entity_name for c in ["\\", "/", "*", "?", ":", '"', "<", ">", "|"]
            )
            self.logger.info(f"是否包含特殊字符: {has_special_chars}")

            if has_special_chars:
                self.logger.info(f"名称包含特殊字符，只使用ID")
                clean_name = ""
                file_prefix = f"{entity_type}_{writer_id}"
            else:
                # 清理名称并使用
                clean_name = self.clean_filename(entity_name)
                self.logger.info(f"清理后的名称: '{clean_name}'")
                file_prefix = f"{entity_type}_{writer_id}_{clean_name}"

            self.logger.info(f"生成的文件前缀: '{file_prefix}'")

            # 确保目录存在
            result_dir = config.result_dir
            os.makedirs(result_dir, exist_ok=True)

            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 分类结果
            leaked_with_magnet = []
            leaked_without_magnet = []
            unleaked = []
            all_leaked = []

            for result in results:
                status = result.get("status", "")
                # "available" 对应已流出
                is_leaked = (status == "available") or result.get("leaked", False)

                if is_leaked:
                    has_magnet = bool(result.get("magnets") or result.get("magnet"))
                    if has_magnet:
                        leaked_with_magnet.append(result)
                    else:
                        leaked_without_magnet.append(result)
                    all_leaked.append(result)
                else:
                    unleaked.append(result)

            # 生成报告文件路径
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            reports = {}

            # 1. 总报告 - 使用固定格式
            summary_path = os.path.join(result_dir, f"{writer_id}_{clean_name}_总报告.txt")
            reports["summary"] = summary_path

            # 统计信息
            total = len(results)
            leaked_count = len(all_leaked)
            unleaked_count = len(unleaked)
            with_magnet_count = len(leaked_with_magnet)
            without_magnet_count = len(leaked_without_magnet)
            leak_ratio = (leaked_count / total) * 100 if total > 0 else 0

            # 生成总报告
            with open(summary_path, "w", encoding="utf-8") as f:
                entity_desc = "女优" if self.is_actress else "作者"
                f.write(f"{entity_desc}ID: {writer_id}\n")

                # 根据是否有特殊字符，决定使用原名还是清理后的名称
                if has_special_chars:
                    f.write(f"{entity_desc}名称: {entity_name} (含特殊字符)\n")
                else:
                    f.write(f"{entity_desc}名称: {clean_name}\n")

                f.write(f"分析时间: {timestamp}\n")
                f.write(f"\n=== 总体统计 ===\n")
                f.write(f"总视频数: {total}\n")
                f.write(f"已流出视频数: {leaked_count}\n")
                f.write(f"未流出视频数: {unleaked_count}\n")
                f.write(f"流出比例: {leak_ratio:.2f}%\n")
                f.write(f"有磁链数量: {with_magnet_count}\n")
                f.write(f"无磁链数量: {without_magnet_count}\n")

                f.write(f"\n=== 已流出视频列表 ===\n")
                for idx, video in enumerate(all_leaked, 1):
                    vid = video.get("video_id")
                    title = video.get("title", f"FC2-PPV-{vid}")
                    has_magnet = bool(video.get("magnets") or video.get("magnet"))
                    f.write(
                        f"{idx}. [{vid}] {'[有磁链]' if has_magnet else '[无磁链]'} {title}\n"
                    )

                f.write(f"\n=== 未流出视频列表 ===\n")
                for idx, video in enumerate(unleaked, 1):
                    vid = video.get("video_id")
                    title = video.get("title", f"FC2-PPV-{vid}")
                    f.write(f"{idx}. [{vid}] {title}\n")

            # 2. 已流出_有磁链 - 使用固定格式
            if leaked_with_magnet:
                with_magnet_path = os.path.join(
                    result_dir, f"{writer_id}_{clean_name}_已流出_有磁链.txt"
                )
                reports["leaked_with_magnet"] = with_magnet_path

                with open(with_magnet_path, "w", encoding="utf-8") as f:
                    entity_desc = "女优" if self.is_actress else "作者"
                    f.write(f"{entity_desc}ID: {writer_id}\n")

                    # 根据是否有特殊字符，决定使用原名还是清理后的名称
                    if has_special_chars:
                        f.write(f"{entity_desc}名称: {entity_name} (含特殊字符)\n")
                    else:
                        f.write(f"{entity_desc}名称: {clean_name}\n")

                    f.write(f"分析时间: {timestamp}\n")
                    f.write(f"有磁链视频数量: {with_magnet_count}\n\n")

                    for idx, video in enumerate(leaked_with_magnet, 1):
                        vid = video.get("video_id")
                        title = video.get("title", f"FC2-PPV-{vid}")
                        f.write(f"=== {idx}. FC2-PPV-{vid} ===\n")
                        f.write(f"标题: {title}\n")

                        # 磁力链接
                        magnets = (
                            video.get("magnets") or [video.get("magnet")]
                            if video.get("magnet")
                            else []
                        )
                        for i, magnet in enumerate(magnets, 1):
                            if magnet:
                                f.write(f"磁链{i}: {magnet}\n")
                        f.write("\n")

            # 3. 已流出_无磁链 - 使用固定格式
            if leaked_without_magnet:
                without_magnet_path = os.path.join(
                    result_dir, f"{writer_id}_{clean_name}_已流出_无磁链.txt"
                )
                reports["leaked_without_magnet"] = without_magnet_path

                with open(without_magnet_path, "w", encoding="utf-8") as f:
                    entity_desc = "女优" if self.is_actress else "作者"
                    f.write(f"{entity_desc}ID: {writer_id}\n")

                    # 根据是否有特殊字符，决定使用原名还是清理后的名称
                    if has_special_chars:
                        f.write(f"{entity_desc}名称: {entity_name} (含特殊字符)\n")
                    else:
                        f.write(f"{entity_desc}名称: {clean_name}\n")

                    f.write(f"分析时间: {timestamp}\n")
                    f.write(f"无磁链视频数量: {without_magnet_count}\n\n")

                    for idx, video in enumerate(leaked_without_magnet, 1):
                        vid = video.get("video_id")
                        title = video.get("title", f"FC2-PPV-{vid}")
                        f.write(f"{idx}. [{vid}] {title}\n")

            # 4. 未流出视频 - 使用固定格式
            if unleaked:
                unleaked_path = os.path.join(
                    result_dir, f"{writer_id}_{clean_name}_未流出.txt"
                )
                reports["unleaked"] = unleaked_path

                with open(unleaked_path, "w", encoding="utf-8") as f:
                    entity_desc = "女优" if self.is_actress else "作者"
                    f.write(f"{entity_desc}ID: {writer_id}\n")

                    # 根据是否有特殊字符，决定使用原名还是清理后的名称
                    if has_special_chars:
                        f.write(f"{entity_desc}名称: {entity_name} (含特殊字符)\n")
                    else:
                        f.write(f"{entity_desc}名称: {clean_name}\n")

                    f.write(f"分析时间: {timestamp}\n")
                    f.write(f"未流出视频数量: {unleaked_count}\n\n")

                    for idx, video in enumerate(unleaked, 1):
                        vid = video.get("video_id")
                        title = video.get("title", f"FC2-PPV-{vid}")
                        f.write(f"{idx}. [{vid}] {title}\n")

            # 5. 已流出视频总表(简洁版-只有ID和标题) - 使用固定格式
            if all_leaked:
                leaked_summary_path = os.path.join(
                    result_dir, f"{writer_id}_{clean_name}_已流出视频总表.txt"
                )
                reports["leaked_summary"] = leaked_summary_path

                with open(leaked_summary_path, "w", encoding="utf-8") as f:
                    for video in all_leaked:
                        vid = video.get("video_id")
                        title = video.get("title", f"FC2-PPV-{vid}")
                        f.write(f"FC2-PPV-{vid} | {title}\n")

            # 6. 已流出的磁链专用文件(只有磁链)
            if leaked_with_magnet:
                magnet_only_path = os.path.join(result_dir, f"{file_prefix}_磁链.txt")
                reports["magnet_only"] = magnet_only_path

                try:
                    with open(magnet_only_path, "w", encoding="utf-8") as f:
                        for video in leaked_with_magnet:
                            vid = video.get("video_id")
                            title = video.get("title", f"FC2-PPV-{vid}")
                            
                            # 获取磁链 - 兼容两种格式
                            magnets = []
                            
                            # 尝试获取magnets列表
                            if video.get("magnets"):
                                magnets = video.get("magnets")
                            # 如果没有magnets列表但有单个magnet
                            elif video.get("magnet"):
                                magnets = [video.get("magnet")]
                            
                            # 写入视频信息作为注释
                            f.write(f"# {vid} | {title}\n")
                            
                            # 写入磁链
                            if magnets:
                                for magnet in magnets:
                                    if magnet and isinstance(magnet, str):
                                        f.write(f"{magnet}\n")
                            else:
                                # 没有磁链时添加提示
                                f.write("# [未获取到磁力链接]\n")
                            
                            # 添加空行分隔
                            f.write("\n")
                            
                    self.logger.info(f"已生成磁链专用文件: {magnet_only_path}")
                except Exception as e:
                    self.logger.error(f"生成磁链专用文件失败: {str(e)}")

            self.logger.info(f"已生成{len(reports)}个报告文件")
            return reports

        except Exception as e:
            self.logger.error(f"生成报告失败: {str(e)}")
            return {}

    def process_video(self, video_id):
        """
        处理单个视频，包括检查视频状态、下载图片和获取磁力链接

        参数:
            video_id: 视频ID或视频对象

        返回:
            dict: 处理结果
        """
        try:
            # 获取日志记录器
            logger = self.logger

            # 判断输入是字符串还是视频对象
            if isinstance(video_id, dict):
                # 如果传入的是视频对象，提取必要信息
                video_obj = video_id
                video_id_str = str(video_obj.get("video_id", ""))
                # 保存视频对象以供后续使用（特别是获取image_url）
                print(f"[调试] 输入是视频对象，提取video_id: {video_id_str}")
            else:
                # 如果只是字符串ID，转换为字符串并创建基本对象
                video_id_str = str(video_id)
                video_obj = {"video_id": video_id_str}
                print(f"[调试] 输入是ID字符串: {video_id_str}")

            # 初始化结果字典
            result = {
                "id": video_id_str,
                "video_id": video_id_str,  # 添加video_id字段确保兼容性
                "status": None,
                "exists": False,
                "has_magnet": False,
                "magnets": [],
                "error": None,
                "image_downloaded": False,
                "image_path": None,
            }

            # 如果有视频对象，复制更多相关信息
            if isinstance(video_id, dict):
                result["title"] = video_obj.get("title", "")
                result["image_url"] = video_obj.get("image_url", "")

            # 在控制台显示处理状态
            if not self.quiet_mode:
                console.print(f"🔍 处理视频 {video_id_str}")

            # 检查视频状态
            status = self.check_video_status(video_id_str)
            result["status"] = status

            # 判断视频是否流出
            if status == "available":
                result["exists"] = True

                # 显示视频类型
                entity_type = "女优" if self.is_actress else "作者"

                # 在控制台显示视频可用状态
                if not self.quiet_mode:
                    console.print(
                        f"✅ 视频 {video_id_str} 已流出 ({entity_type}: {self.write_id})"
                    )

                # 获取磁力链接 - 无论是女优还是作者，都使用相同的方式获取磁链
                if self.with_magnet:
                    try:
                        magnets = self.fetch_magnet_link(video_id_str)
                        if magnets:
                            result["has_magnet"] = True
                            result["magnets"] = magnets
                            # 在控制台显示磁力链接状态
                            if not self.quiet_mode:
                                console.print(f"🧲 视频 {video_id_str} 找到磁力链接")
                        else:
                            # 在控制台显示未找到磁力链接状态
                            if not self.quiet_mode:
                                console.print(f"⚠️ 视频 {video_id_str} 未找到磁力链接")
                    except Exception as e:
                        logger.error(f"获取磁力链接失败: {str(e)}")
                        if not self.quiet_mode:
                            console.print(f"❌ 获取磁力链接失败: {str(e)}")

                # 下载图片 - 传递完整视频对象而不仅仅是ID
                if self.download_images:
                    try:
                        # 修复：将状态信息添加到视频对象中
                        video_obj["status"] = status  # 确保状态正确传递

                        # 传递完整视频对象以便使用image_url和status
                        image_path = self.download_image(video_obj)
                        if image_path:
                            result["image_downloaded"] = True
                            result["image_path"] = image_path
                            # 在控制台显示图片下载状态
                            if not self.quiet_mode:
                                console.print(f"🖼️ 视频 {video_id_str} 图片已下载")
                        else:
                            # 在控制台显示图片下载失败状态
                            if not self.quiet_mode:
                                console.print(f"⚠️ 视频 {video_id_str} 图片下载失败")
                    except Exception as e:
                        logger.error(f"下载图片失败: {str(e)}")
                        if not self.quiet_mode:
                            console.print(f"❌ 下载图片失败: {str(e)}")
            else:
                # 视频不可用，在控制台显示状态
                result["exists"] = False  # 确保一致性

                # 显示视频类型和状态
                entity_type = "女优" if self.is_actress else "作者"
                status_display = "未流出" if status == "unavailable" else f"错误({status})"

                if not self.quiet_mode:
                    console.print(
                        f"⚠️ 视频 {video_id_str} {status_display} ({entity_type}: {self.write_id})"
                    )

                # 即使视频未流出，也尝试下载图片
                if self.download_images:
                    try:
                        # 修复：将状态信息添加到视频对象中
                        video_obj["status"] = status  # 确保状态正确传递

                        # 传递完整视频对象以便使用image_url和status
                        image_path = self.download_image(video_obj)
                        if image_path:
                            result["image_downloaded"] = True
                            result["image_path"] = image_path
                            # 在控制台显示图片下载状态
                            if not self.quiet_mode:
                                console.print(f"🖼️ 视频 {video_id_str} 图片已下载")
                        else:
                            # 在控制台显示图片下载失败状态
                            if not self.quiet_mode:
                                console.print(f"⚠️ 视频 {video_id_str} 图片下载失败")
                    except Exception as e:
                        logger.error(f"下载图片失败: {str(e)}")
                        if not self.quiet_mode:
                            console.print(f"❌ 下载图片失败: {str(e)}")
            # 更新统计信息
            self._update_stats(result)

            return result

        except Exception as e:
            # 使用self.logger
            self.logger.error(
                f"处理视频 {video_id if isinstance(video_id, str) else video_id.get('video_id', 'unknown')} 时出错: {str(e)}"
            )
            if not self.quiet_mode:
                video_id_str = (
                    video_id
                    if isinstance(video_id, str)
                    else video_id.get("video_id", "unknown")
                )
                console.print(f"❌ 处理视频 {video_id_str} 时出错: {str(e)}")

            # 设置错误信息
            video_id_str = (
                video_id
                if isinstance(video_id, str)
                else video_id.get("video_id", "unknown")
            )
            result = {
                "id": video_id_str,
                "video_id": video_id_str,
                "status": "error",
                "exists": False,
                "has_magnet": False,
                "magnets": [],
                "error": str(e),
                "image_downloaded": False,
                "image_path": None,
            }

            # 更新统计信息
            self._update_stats(result)

            return result

    def analyze_videos(self, videos):
        """
        分析一组视频，支持并发处理

        参数:
            videos: 视频ID列表

        返回:
            tuple: (结果列表, 统计信息)
        """
        # 检查videos是否为有效列表
        if not videos:
            if not self.quiet_mode:
                console.print("⚠️ 未找到视频，无法进行分析")
            return [], self.stats

        # 更新总视频数
        self.stats["total"] = len(videos)

        # 创建结果列表
        results = []

        # 显示分析开始信息
        entity_type = "女优" if self.is_actress else "作者"
        entity_id = self.write_id
        entity_name = self.name or entity_id

        # 清理实体名称防止有非法字符
        clean_entity_name = self.clean_filename(entity_name)

        # 显示开始分析消息
        if not self.quiet_mode:
            console.print(
                f"\n[bold cyan]开始分析{entity_type} {entity_id} [{clean_entity_name}] 的 {len(videos)} 个视频[/bold cyan]"
            )
            if self.with_magnet:
                console.print("[dim]将获取已流出视频的磁力链接[/dim]")
            if self.download_images:
                console.print("[dim]将下载视频缩略图[/dim]")

        # 使用进度条跟踪处理进度
        with Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            TimeElapsedColumn(),
            "{task.completed}/{task.total}",
            console=console,
        ) as progress:
            # 创建主任务
            task_desc = f"{entity_type}视频分析进度"
            task = progress.add_task(task_desc, total=len(videos))

            # 使用线程池并发处理视频
            # 从CONFIG获取max_workers配置
            max_workers = config.max_workers
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有视频处理任务
                future_to_video = {
                    executor.submit(self.process_video, video): video
                    for video in videos
                }

                # 收集结果
                for future in as_completed(future_to_video):
                    video = future_to_video[future]
                    try:
                        result = future.result()
                        if result:
                            results.append(result)
                    except Exception as e:
                        self.logger.error(f"处理视频 {video} 时出错: {str(e)}")
                        if not self.quiet_mode:
                            console.print(f"❌ 处理视频 {video} 时出错: {str(e)}")

                    # 更新进度条
                    progress.update(task, advance=1)

        # 整理结果
        sorted_results = sorted(results, key=lambda x: x["id"])

        # 保存结果
        self.results = sorted_results

        # 如果在安静模式，显示简单的完成消息
        if not self.quiet_mode:
            # 计算统计信息
            total = len(results)
            leaked = sum(1 for r in results if r.get("leaked", False))
            leak_ratio = (leaked / total) * 100 if total > 0 else 0
            console.print(
                f"\n[bold green]✅ 分析完成！总共 {total} 个视频，已流出 {leaked} 个 (流出比例: {leak_ratio:.1f}%)[/bold green]"
            )

        # 返回结果和统计信息
        return sorted_results, self.stats

    def display_results(self, results, stats=None):
        """
        显示分析结果

        参数:
            results: 分析结果列表
            stats: 统计信息，如果为None则使用self.stats
        """
        if not stats:
            stats = self.stats

        try:
            # 如果结果为空，显示提示信息
            if not results:
                console.print("[bold yellow]⚠️ 没有分析结果可显示[/bold yellow]")
                return

            # 根据ID排序结果
            sorted_results = sorted(results, key=lambda x: x["id"])

            # 显示统计信息
            total = stats["total"]
            processed = stats["processed"]
            available = stats.get("available", 0)
            unavailable = stats.get("unavailable", 0)
            errors = stats.get("errors", 0)

            # 计算百分比
            avail_ratio = (available / total * 100) if total > 0 else 0
            unavail_ratio = (unavailable / total * 100) if total > 0 else 0
            error_ratio = (errors / total * 100) if total > 0 else 0

            # 创建主表格
            entity_type = "女优" if self.is_actress else "作者"
            entity_id = self.write_id
            entity_name = self.name or entity_id

            # 清理实体名称，防止有非法字符
            clean_entity_name = self.clean_filename(entity_name)

            console.print(
                f"\n[bold cyan]━━━━━━━━━━━━━━ {entity_type}分析结果 ━━━━━━━━━━━━━━[/bold cyan]"
            )

            # 创建更美观的主表格
            table = Table(
                title=f"[bold magenta]{entity_type} {entity_id} [{clean_entity_name}][/bold magenta]",
                box=box.ROUNDED,
                title_justify="center",
                highlight=True,
                border_style="cyan",
            )

            # 添加列
            table.add_column("[bold]分类[/bold]", style="cyan")
            table.add_column("[bold]数量[/bold]", justify="right", style="green")
            table.add_column("[bold]百分比[/bold]", justify="right", style="yellow")
            table.add_column("[bold]状态条[/bold]", justify="left")

            # 添加行
            table.add_row("总视频数", f"{total}", "100%", "━" * 20)

            # 根据百分比选择颜色
            avail_color = "green"  # 已流出始终使用绿色
            unavail_color = "red"  # 未流出始终使用红色
            error_color = (
                "green" if error_ratio < 2 else "yellow" if error_ratio < 5 else "red"
            )

            # 生成进度条
            avail_bar = "█" * int(avail_ratio / 5)
            unavail_bar = "█" * int(unavail_ratio / 5)
            error_bar = "█" * int(error_ratio / 5) if error_ratio > 0 else ""

            table.add_row(
                "已流出",
                f"[bold]{available}[/bold]",
                f"[{avail_color}]{avail_ratio:.1f}%[/{avail_color}]",
                f"[{avail_color}]{avail_bar}[/{avail_color}]",
            )
            table.add_row(
                "未流出",
                f"{unavailable}",
                f"[{unavail_color}]{unavail_ratio:.1f}%[/{unavail_color}]",
                f"[{unavail_color}]{unavail_bar}[/{unavail_color}]",
            )
            table.add_row(
                "错误数",
                f"{errors}",
                f"[{error_color}]{error_ratio:.1f}%[/{error_color}]",
                f"[{error_color}]{error_bar}[/{error_color}]",
            )

            # 显示表格
            console.print(table)

            # 显示详细统计信息
            console.print(
                "\n[bold cyan]━━━━━━━━━━━━━━ 详细统计信息 ━━━━━━━━━━━━━━[/bold cyan]"
            )

            details_table = Table(
                box=box.ROUNDED,
                highlight=True,
                border_style="blue",
                pad_edge=False,
                expand=True,
            )

            # 添加列
            details_table.add_column("[bold]类别[/bold]", style="cyan")
            details_table.add_column("[bold]数量[/bold]", justify="right", style="green")
            details_table.add_column("[bold]比例[/bold]", justify="right", style="yellow")
            details_table.add_column("[bold]状态条[/bold]", justify="left")

            # 添加磁力链接统计
            if self.with_magnet:
                with_magnet = stats.get("with_magnet", 0)
                without_magnet = stats.get("without_magnet", 0)
                magnet_total = with_magnet + without_magnet
                magnet_ratio = (
                    (with_magnet / magnet_total * 100) if magnet_total > 0 else 0
                )

                magnet_color = "green"  # 始终将有磁链状态显示为绿色
                no_magnet_color = "red"  # 始终将无磁链状态显示为红色

                # 生成进度条
                magnet_bar = "█" * int(magnet_ratio / 5)
                no_magnet_bar = "█" * int((100 - magnet_ratio) / 5)

                details_table.add_row(
                    "[bold magenta]== 磁链统计 ==[/bold magenta]", "", "", ""
                )
                details_table.add_row(
                    "流出视频中有磁链",
                    f"[bold]{with_magnet}[/bold]",
                    f"[{magnet_color}]{magnet_ratio:.1f}%[/{magnet_color}]",
                    f"[{magnet_color}]{magnet_bar}[/{magnet_color}]",
                )
                details_table.add_row(
                    "流出视频中无磁链",
                    f"{without_magnet}",
                    f"[{no_magnet_color}]{100-magnet_ratio:.1f}%[/{no_magnet_color}]",
                    f"[{no_magnet_color}]{no_magnet_bar}[/{no_magnet_color}]",
                )

            # 添加图片统计
            if self.download_images:
                image_success = stats.get("image_success", 0)
                image_fail = stats.get("image_fail", 0)
                image_total = image_success + image_fail
                image_ratio = (
                    (image_success / image_total * 100) if image_total > 0 else 0
                )

                image_color = (
                    "green"
                    if image_ratio > 80
                    else "yellow"
                    if image_ratio > 50
                    else "red"
                )
                fail_color = (
                    "red"
                    if (100 - image_ratio) > 20
                    else "yellow"
                    if (100 - image_ratio) > 10
                    else "green"
                )

                # 生成进度条
                image_bar = "█" * int(image_ratio / 5)
                fail_bar = (
                    "█" * int((100 - image_ratio) / 5)
                    if (100 - image_ratio) > 0
                    else ""
                )

                details_table.add_row("", "", "", "")
                details_table.add_row(
                    "[bold magenta]== 图片统计 ==[/bold magenta]", "", "", ""
                )
                details_table.add_row(
                    "成功下载图片",
                    f"[bold]{image_success}[/bold]",
                    f"[{image_color}]{image_ratio:.1f}%[/{image_color}]",
                    f"[{image_color}]{image_bar}[/{image_color}]",
                )
                details_table.add_row(
                    "图片下载失败",
                    f"{image_fail}",
                    f"[{fail_color}]{100-image_ratio:.1f}%[/{fail_color}]",
                    f"[{fail_color}]{fail_bar}[/{fail_color}]",
                )

            # 显示详细统计表格
            console.print(details_table)

            # 显示结果摘要
            console.print("\n[bold cyan]━━━━━━━━━━━━━━ 结果摘要 ━━━━━━━━━━━━━━[/bold cyan]")

            summary = Table(
                show_header=False,
                box=box.ROUNDED,
                border_style="green",
                pad_edge=False,
                highlight=True,
            )

            # 添加列
            summary.add_column("项目", style="cyan", justify="right")
            summary.add_column("值", style="bold green", justify="left")

            # 添加行 - 删除emoji图标
            summary.add_row("总计视频:", f"[bold]{total}[/bold] 个")
            summary.add_row(
                "已泄漏:",
                f"[bold green]{available}[/bold green] 个 (含磁链: [bold]{stats.get('with_magnet', 0)}[/bold])",
            )
            summary.add_row("未泄漏:", f"[bold red]{unavailable}[/bold red] 个")
            summary.add_row("检查失败:", f"[bold yellow]{errors}[/bold yellow] 个")

            # 根据比例选择颜色
            ratio_color = (
                "green" if avail_ratio > 70 else "yellow" if avail_ratio > 40 else "red"
            )
            summary.add_row(
                "流出比例:", f"[bold {ratio_color}]{avail_ratio:.1f}%[/bold {ratio_color}]"
            )

            # 添加图片下载统计 - 删除emoji图标
            if self.download_images:
                image_success = stats.get("image_success", 0)
                image_fail = stats.get("image_fail", 0)
                image_total = image_success + image_fail
                image_ratio = (
                    (image_success / image_total * 100) if image_total > 0 else 0
                )

                # 根据成功率选择颜色
                image_color = (
                    "green"
                    if image_ratio > 80
                    else "yellow"
                    if image_ratio > 50
                    else "red"
                )
                summary.add_row("", "")
                summary.add_row(
                    "图片下载:",
                    f"成功: [bold green]{image_success}[/bold green]，失败: [bold red]{image_fail}[/bold red]",
                )
                summary.add_row(
                    "图片下载成功率:",
                    f"[bold {image_color}]{image_ratio:.1f}%[/bold {image_color}]",
                )

            # 添加磁链统计 - 删除emoji图标
            if self.with_magnet and available > 0:
                with_magnet = stats.get("with_magnet", 0)
                without_magnet = stats.get("without_magnet", 0)
                magnet_total = with_magnet + without_magnet
                magnet_ratio = (
                    (with_magnet / magnet_total * 100) if magnet_total > 0 else 0
                )

                # 根据成功率选择颜色
                magnet_color = (
                    "green"
                    if magnet_ratio > 70
                    else "yellow"
                    if magnet_ratio > 40
                    else "red"
                )
                summary.add_row("", "")
                summary.add_row(
                    "磁链统计:",
                    f"有磁链: [bold green]{with_magnet}[/bold green]，无磁链: [bold red]{without_magnet}[/bold red]",
                )
                summary.add_row(
                    "磁链获取成功率:",
                    f"[bold {magnet_color}]{magnet_ratio:.1f}%[/bold {magnet_color}]",
                )

                # 添加重试统计
                magnet_retries = stats.get("magnet_retries", 0)
                magnet_retry_success = stats.get("magnet_retry_success", 0)
                if magnet_retries > 0:
                    retry_success_ratio = (
                        (magnet_retry_success / magnet_retries * 100)
                        if magnet_retries > 0
                        else 0
                    )
                    retry_color = (
                        "green"
                        if retry_success_ratio > 70
                        else "yellow"
                        if retry_success_ratio > 40
                        else "red"
                    )
                    summary.add_row(
                        "磁链重试次数:",
                        f"[bold]{magnet_retries}[/bold] 次，成功: [bold green]{magnet_retry_success}[/bold green] 次",
                    )
                    summary.add_row(
                        "磁链重试成功率:",
                        f"[bold {retry_color}]{retry_success_ratio:.1f}%[/bold {retry_color}]",
                    )

            # 添加图片重试统计
            if self.download_images:
                image_retries = stats.get("image_retries", 0)
                image_retry_success = stats.get("image_retry_success", 0)
                if image_retries > 0:
                    image_retry_ratio = (
                        (image_retry_success / image_retries * 100)
                        if image_retries > 0
                        else 0
                    )
                    retry_img_color = (
                        "green"
                        if image_retry_ratio > 70
                        else "yellow"
                        if image_retry_ratio > 40
                        else "red"
                    )
                    summary.add_row("", "")
                    summary.add_row(
                        "图片重试次数:",
                        f"[bold]{image_retries}[/bold] 次，成功: [bold green]{image_retry_success}[/bold green] 次",
                    )
                    summary.add_row(
                        "图片重试成功率:",
                        f"[bold {retry_img_color}]{image_retry_ratio:.1f}%[/bold {retry_img_color}]",
                    )

            # 显示摘要
            console.print(summary)

        except Exception as e:
            self.logger.error(f"显示结果出错: {e}")
            console.print(f"[bold red]❌ 显示结果出错: {e}[/bold red]")

    def _update_stats(self, result):
        """
        更新统计信息

        参数:
            result: 视频处理结果
        """
        with self.lock:
            # 更新总处理数
            self.stats["processed"] += 1

            # 根据视频状态更新统计
            if result["status"] == "error":
                self.stats["errors"] += 1
            elif result["status"] == "available":
                self.stats["available"] += 1

                # 更新磁力链接统计
                if self.with_magnet:
                    if result.get("has_magnet"):
                        self.stats["with_magnet"] += 1
                        self.stats["magnet_success"] = (
                            self.stats.get("magnet_success", 0) + 1
                        )
                    else:
                        self.stats["without_magnet"] += 1
                        self.stats["magnet_fail"] = self.stats.get("magnet_fail", 0) + 1
            else:
                self.stats["unavailable"] += 1

            # 更新图片下载统计 - 不在这里更新，避免重复计数
            # 图片下载统计已经在download_image方法中更新

            # 确保重试统计字段存在
            for key in [
                "magnet_retries",
                "image_retries",
                "magnet_retry_success",
                "image_retry_success",
            ]:
                if key not in self.stats:
                    self.stats[key] = 0


def main():
    """程序主入口

    提供命令行交互界面，让用户输入作者ID和线程数，然后执行分析
    """
    print("=== FC2流出检测器 ===")

    writer_id = input("请输入FC2作者ID: ").strip()
    if not writer_id:
        print("❌ 作者ID不能为空")
        return

    # 创建分析器
    analyzer = FC2Analyzer(writer_id)

    # 获取作者名称
    author_name = analyzer.fetch_author_name()
    if author_name:
        print(f"✅ 作者名称: {author_name}")

    # 获取视频列表
    videos = analyzer.fetch_video_ids()
    if not videos:
        print("❌ 未找到视频，程序退出")
        return

    # 设置线程数
    threads = input(f"请输入并行线程数 (默认{config.max_workers}): ").strip()
    max_workers = (
        config.max_workers if not threads or not threads.isdigit() else int(threads)
    )

    # 分析视频
    results, stats = analyzer.analyze_videos(videos)

    # 保存结果
    analyzer.save_results()

    print("✅ 程序执行完毕！结果已保存")


if __name__ == "__main__":
    main()
