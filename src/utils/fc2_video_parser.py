"""
FC2视频解析模块 - 视频信息和作者数据提取工具

提供从FC2PPV数据库网站获取视频和作者信息的功能，支持ID映射和关联数据解析
"""
import os
import re
import time

import requests
from bs4 import BeautifulSoup

from config import config
from src.utils.logger import get_logger

# 获取日志记录器
logger = get_logger("fc2_video_parser")


def get_writer_username_from_vid(vid, max_retries=3):
    """
    从视频ID获取作者用户名

    Args:
        vid: 视频ID
        max_retries: 最大重试次数

    Returns:
        str: 作者用户名，失败返回None
    """
    url = f"{config.fc2ppvdb_api_base}/articles/{vid}"

    # 使用配置中的请求头
    headers = config.base_headers.copy()

    retry_count = 0
    while retry_count < max_retries:
        try:
            logger.info(f"获取视频 {vid} 的作者信息...")
            response = requests.get(url, headers=headers, timeout=config.timeout)

            # 处理429错误
            if response.status_code == 429:
                wait_time = 30 * (retry_count + 1)  # 增加等待时间
                logger.warning(f"收到429错误，等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
                retry_count += 1
                continue

            # 处理404错误
            if response.status_code == 404:
                logger.warning(f"视频 {vid} 不存在于FC2PPVDB")
                return None

            response.raise_for_status()

            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # 方法1: 查找包含"販売者："文本的div元素
            seller_divs = []
            for div in soup.find_all("div"):
                if div.get_text() and "販売者：" in div.get_text():
                    seller_divs.append(div)

            # 如果找到了销售者div，从中提取作者链接
            for div in seller_divs:
                author_link = div.find("a")
                if (
                    author_link
                    and "href" in author_link.attrs
                    and author_link["href"].startswith("/writers/")
                ):
                    href = author_link["href"]
                    username_match = re.search(r"/writers/([^/]+)", href)
                    if username_match:
                        writer_username = username_match.group(1)
                        logger.info(f"成功获取视频 {vid} 的作者用户名: {writer_username}")
                        return writer_username

            # 方法2: 使用更精确的CSS选择器，查找作者信息附近的链接
            # 尝试匹配紧跟在"販売者："文本后的链接
            for element in soup.find_all(string=lambda text: text and "販売者：" in text):
                parent = element.parent
                if parent:
                    # 查找父元素下的链接
                    links = parent.find_all("a")
                    for link in links:
                        if "href" in link.attrs and link["href"].startswith(
                            "/writers/"
                        ):
                            href = link["href"]
                            username_match = re.search(r"/writers/([^/]+)", href)
                            if username_match:
                                writer_username = username_match.group(1)
                                logger.info(f"成功获取视频 {vid} 的作者用户名: {writer_username}")
                                return writer_username

            # 方法3: 查找包含具体作者属性的元素
            for element in soup.select('.text-white.ml-2 a[href^="/writers/"]'):
                if "href" in element.attrs:
                    href = element["href"]
                    username_match = re.search(r"/writers/([^/]+)", href)
                    if username_match:
                        writer_username = username_match.group(1)
                        logger.info(f"成功获取视频 {vid} 的作者用户名: {writer_username}")
                        return writer_username

            logger.warning(f"无法在页面中找到作者信息: {url}")
            # 保存页面源码以便调试
            debug_file = os.path.join(
                config.log_dir, f"debug_html_{vid}.txt"
            )
            try:
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(response.text)
                logger.info(f"已保存HTML源码到 {debug_file} 以供调试")
            except Exception as e:
                logger.error(f"保存HTML源码失败: {e}")

            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"请求错误: {e}")
            wait_time = 5 * (retry_count + 1)
            logger.info(f"等待 {wait_time} 秒后重试...")
            time.sleep(wait_time)
            retry_count += 1
        except Exception as e:
            logger.error(f"解析错误: {e}")
            return None

    logger.error(f"已达最大重试次数，无法获取作者信息")
    return None


def get_writer_info(writerusername, request_counter, max_retries=5):
    """获取作者的ID，使用基于请求次数的退避策略"""
    url = f"{config.fc2ppvdb_api_base}/writers/{writerusername}"

    # 检查是否需要等待 - 每20次请求后的第一次(21,41,61...)
    if request_counter % 20 == 1 and request_counter > 1:
        logger.info(f"达到请求限制点 ({request_counter})，等待30秒以避免被封...")
        time.sleep(30)

    retry_count = 0

    # 使用配置中的请求头
    headers = config.base_headers.copy()

    while retry_count < config.max_retries:
        try:
            # 发送HTTP请求获取页面内容
            response = requests.get(url, headers=headers, timeout=config.timeout)

            # 如果是429错误，进行重试
            if response.status_code == 429:
                wait_time = 30  # 固定等待30秒
                logger.warning(f"收到429错误，等待 {wait_time} 秒后重试 {writerusername}...")
                time.sleep(wait_time)
                retry_count += 1
                continue

            response.raise_for_status()

            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # 从HTML中直接解析writerid
            writerid = None

            # 尝试从data-writerid属性中获取
            writer_articles_div = soup.find("div", id="writer-articles")
            if writer_articles_div and "data-writerid" in writer_articles_div.attrs:
                writerid = writer_articles_div["data-writerid"]

            # 如果上面的方法失败，尝试从其他地方获取
            if not writerid:
                # 尝试从input标签中获取
                writer_id_input = soup.find("input", {"name": "writer_id"})
                if writer_id_input and "value" in writer_id_input.attrs:
                    writerid = writer_id_input["value"]

            if not writerid:
                # 尝试从JavaScript常量中查找
                script_tags = soup.find_all("script")
                for script in script_tags:
                    if script.string and "const id =" in script.string:
                        id_match = re.search(r"const id = '(\d+)'", script.string)
                        if id_match:
                            writerid = id_match.group(1)
                            break

            logger.info(f"成功获取作者 {writerusername} 的ID: {writerid}")
            return writerid

        except Exception as e:
            logger.error(f"获取作者信息失败: {e}")
            retry_count += 1
            time.sleep(5)

    logger.error(f"已达最大重试次数，无法获取作者 {writerusername} 的ID")
    return None


def find_writer_by_video(vid):
    """
    通过视频ID查找作者信息

    Args:
        vid: 视频ID

    Returns:
        tuple: (作者ID, 作者用户名) 或 (None, None)
    """
    # 第一步：从视频ID获取作者用户名
    writer_username = get_writer_username_from_vid(vid)

    if not writer_username:
        logger.error(f"无法从视频 {vid} 获取作者用户名")
        return None, None

    # 第二步：从作者用户名获取作者ID
    # 使用一个静态计数器来控制请求频率
    writer_id = get_writer_info(writer_username, 1)

    if not writer_id:
        logger.error(f"无法获取作者 {writer_username} 的ID")
        return None, writer_username

    return writer_id, writer_username
