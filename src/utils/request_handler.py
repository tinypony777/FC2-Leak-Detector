"""
请求处理模块 - 管理HTTP请求的核心组件

提供统一的网络请求功能，包含会话管理、自动重试和错误处理机制
"""
import os
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin

import requests
from requests.exceptions import ConnectionError, RequestException, Timeout

from config import config
from src.utils.logger import get_logger

# 使用统一的日志记录器
logger = get_logger("request_handler")


class RequestHandler:
    # 单例会话
    _session = None

    @classmethod
    def get_session(cls):
        """获取会话实例，使用单例模式"""
        if cls._session is None:
            cls._session = requests.Session()
        return cls._session

    @classmethod
    def reset_session(cls):
        """重置会话，主要用于测试"""
        if cls._session:
            cls._session.close()
        cls._session = None

    @classmethod
    def make_request(
        cls,
        url,
        headers=None,
        timeout=None,
        step_name=None,
        max_retries=None,
        verify=True,
        allow_redirects=True,
    ):
        """发送GET请求，包含重试机制

        Args:
            url: 请求URL
            headers: 请求头
            timeout: 超时时间
            step_name: 步骤名称，用于日志
            max_retries: 最大重试次数
            verify: 是否验证SSL证书
            allow_redirects: 是否允许重定向

        Returns:
            Response: 请求响应对象
        """
        # 使用配置的默认值
        if timeout is None:
            timeout = config.timeout
        if max_retries is None:
            max_retries = config.max_retries
            
        retry_count = 0

        while retry_count <= max_retries:
            try:
                # 使用自定义通知
                if step_name:
                    retry_suffix = (
                        f" (重试 {retry_count}/{max_retries})" if retry_count > 0 else ""
                    )
                    logger.info(f"{step_name}{retry_suffix}")

                # 发送请求
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=timeout,
                    verify=verify,
                    allow_redirects=allow_redirects,
                )

                # 成功获取响应
                return response

            except (requests.RequestException, ConnectionError, TimeoutError) as e:
                # 记录日志
                logger.error(f"请求失败: {str(e)}")

                retry_count += 1

                # 如果达到最大重试次数，则返回None
                if retry_count > max_retries:
                    logger.error(f"达到最大重试次数，请求失败: {url}")
                    return None

                # 计算退避时间
                wait_time = (2**retry_count) + random.uniform(0, 1)
                logger.info(f"等待 {wait_time:.2f} 秒后重试...")
                time.sleep(wait_time)

    @classmethod
    def check_video_leak_status(
        cls, video_id
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """检查视频是否已经流出

        Args:
            video_id: 视频ID

        Returns:
            tuple: (是否流出, 站点名称, 状态码)
        """
        # 确保video_id是字符串
        video_id = str(video_id)

        # 尝试不同的站点进行检查
        check_sites_config = config.check_sites
        # 确保check_sites是列表类型
        check_sites = []
        if isinstance(check_sites_config, list):
            check_sites = check_sites_config
        
        if not check_sites:
            # 默认检查站点
            check_sites = [
                {
                    "name": "MissAV",
                    "url": "https://missav.ws/dm18/en/fc2-ppv-{vid}",
                    "priority": 1,
                }
            ]

        # 按优先级排序
        # 确保所有项都有priority键，避免类型错误
        for site in check_sites:
            if "priority" not in site:
                site["priority"] = 999
        check_sites.sort(key=lambda x: x["priority"])

        for site in check_sites:
            site_name = site.get("name", "未知站点")
            # 兼容两种URL格式：使用{video_id}或{vid}
            site_url = site.get("url", "")
            if "{video_id}" in site_url:
                site_url = site_url.format(video_id=video_id)
            else:
                site_url = site_url.format(vid=video_id)

            if not site_url:
                continue

            # 使用统一的请求功能
            logger.info(f"检查视频 {video_id} 是否在 {site_name} 流出")
            response = cls.make_request(
                site_url,
                step_name=f"检查视频 {video_id} 在 {site_name}",
                max_retries=1,  # 减少重试次数以加快速度
                timeout=config.timeout,  # 使用配置的超时时间
            )

            if response:
                # 根据状态码判断视频是否存在
                if response.status_code == 200:
                    logger.info(f"视频 {video_id} 在 {site_name} 已流出")
                    return True, site_name, response.status_code

                elif response.status_code == 404:
                    logger.info(f"视频 {video_id} 在 {site_name} 未找到")
                else:
                    logger.warning(
                        f"检查视频 {video_id} 在 {site_name} 时状态码异常: {response.status_code}"
                    )

        # 所有站点都未找到，视为未流出
        return False, None, None

    @staticmethod
    def _save_error_log(step_name, url, response=None, error_msg=None):
        """记录详细的错误信息到日志文件

        参数:
            step_name: 步骤名称
            url: 请求URL
            response: 响应对象
            error_msg: 错误信息
        """
        try:
            # 确保错误日志目录存在
            log_dir = str(config.log_dir)
            error_dir = os.path.join(log_dir, "errors")
            os.makedirs(error_dir, exist_ok=True)

            # 使用单一日志文件记录所有请求错误
            error_log_path = os.path.join(error_dir, "request_errors.log")

            # 构建错误信息
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status_code = response.status_code if response else "No Response"

            # 记录基本错误信息到日志
            logger.error(f"{step_name} 请求失败: URL={url}, 状态码={status_code}")

            # 记录详细信息到错误日志文件
            with open(error_log_path, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"时间: {timestamp}\n")
                f.write(f"步骤: {step_name}\n")
                f.write(f"请求URL: {url}\n")
                f.write(f"响应状态: {status_code}\n")

                if error_msg:
                    f.write(f"错误信息: {error_msg}\n")

                # 记录部分响应内容，避免日志文件过大
                if response and response.text:
                    content_preview = response.text[:1000] + (
                        "..." if len(response.text) > 1000 else ""
                    )
                    f.write(f"\n响应内容预览:\n{content_preview}\n")
                else:
                    f.write("\n无响应内容\n")
        except Exception as e:
            logger.error(f"保存错误日志失败: {str(e)}")
