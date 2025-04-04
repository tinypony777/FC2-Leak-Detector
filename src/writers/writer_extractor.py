"""
作者提取模块 - 用于从FC2PPVDB网站提取作者信息

提供全面的作者ID和用户名提取功能，支持从排名页面批量获取作者数据
"""
import json
import os
import random
import re
import time
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config import config



def extract_writerusername(url):
    """从writers URL中提取writerusername"""
    # 处理完整URL或相对路径
    if url.startswith("http"):
        parsed = urlparse(url)
        path = parsed.path
    else:
        path = url

    # 提取writerusername
    if path.startswith("/writers/"):
        parts = path.split("/")
        # 确保有足够的部分且不是空的
        if len(parts) >= 3 and parts[2]:
            return parts[2]
    return None


def get_writer_info(writerusername, request_counter, max_retries=None):
    """获取作者的ID，使用基于请求次数的退避策略"""
    # 使用配置的重试次数
    if max_retries is None:
        max_retries = config.max_retries
    url = f"{config.fc2ppvdb_api_base}/writers/{writerusername}"

    # 检查是否需要等待 - 每X次请求后的第一次进行等待
    if request_counter % config.request_limit_count == 1 and request_counter > 1:
        wait_time = (config.retry_base ** 2) + random.uniform(1, 3)  # 使用适当的等待时间
        print(f"达到请求限制点 ({request_counter})，等待 {wait_time:.2f} 秒以避免被封...")
        time.sleep(wait_time)

    retry_count = 0
    
    # 使用配置中的请求头
    headers = config.base_headers.copy()
    
    while retry_count < max_retries:
        try:
            # 发送HTTP请求获取页面内容
            response = requests.get(url, headers=headers, timeout=config.timeout)

            # 如果是429错误，进行重试
            if response.status_code == 429:
                # 使用指数退避策略
                wait_time = (config.retry_base ** retry_count) + random.uniform(1, 3)
                print(f"收到429错误，等待 {wait_time:.2f} 秒后重试 {writerusername}...")
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

            return writerid

        except requests.exceptions.RequestException as e:
            if "429" in str(e):
                # 429错误处理 - 使用指数退避策略
                wait_time = (config.retry_base ** retry_count) + random.uniform(1, 3)
                print(f"收到429错误，等待 {wait_time:.2f} 秒后重试 {writerusername}...")
                time.sleep(wait_time)
                retry_count += 1
            else:
                print(f"获取 {writerusername} 的信息时出错: {e}")
                return None
        except Exception as e:
            print(f"获取 {writerusername} 的信息时出错: {e}")
            return None

    # 如果尝试了最大次数仍然失败
    print(f"达到最大重试次数，无法获取 {writerusername} 的信息")
    return None


def get_writers_from_ranking_pages(request_counter):
    """从排名页面获取所有writerusername
    
    Args:
        request_counter: 请求计数器
        
    Returns:
        tuple: (过滤后的用户名集合, 更新后的请求计数器)
    """
    all_usernames = set()

    # 使用配置的请求头
    headers = config.base_headers.copy()
    
    # 复制计数器以便返回更新后的值
    counter = request_counter

    # 爬取排名页面 1-3
    for page in range(1, 4):
        url = f"{config.fc2ppvdb_api_base}/writers/ranking?page={page}"
        try:
            # 检查是否需要等待
            if counter % config.request_limit_count == 1 and counter > 1:
                wait_time = (config.retry_base ** 2) + random.uniform(1, 3)  # 使用适当的等待时间
                print(f"达到请求限制点 ({counter})，等待 {wait_time:.2f} 秒以避免被封...")
                time.sleep(wait_time)

            counter += 1  # 增加请求计数

            response = requests.get(url, headers=headers, timeout=config.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # 查找所有指向作者页面的链接
            writer_links = soup.find_all(
                "a", href=lambda href: href and href.startswith("/writers/")
            )

            for link in writer_links:
                href = link.get("href")
                username = extract_writerusername(href)
                if username:
                    all_usernames.add(username)

            print(f"从排名页面 {page} 找到 {len(writer_links)} 个链接")

        except Exception as e:
            print(f"爬取排名页面 {page} 时出错: {e}")

    # 爬取书签排名页面
    try:
        # 检查是否需要等待
        if counter % config.request_limit_count == 1 and counter > 1:
            wait_time = (config.retry_base ** 2) + random.uniform(1, 3)  # 使用适当的等待时间
            print(f"达到请求限制点 ({counter})，等待 {wait_time:.2f} 秒以避免被封...")
            time.sleep(wait_time)

        counter += 1  # 增加请求计数

        url = f"{config.fc2ppvdb_api_base}/writers/bookmark-ranking"
        response = requests.get(url, headers=headers, timeout=config.timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        writer_links = soup.find_all(
            "a", href=lambda href: href and href.startswith("/writers/")
        )

        for link in writer_links:
            href = link.get("href")
            username = extract_writerusername(href)
            if username:
                all_usernames.add(username)

        print(f"从书签排名页面找到 {len(writer_links)} 个链接")

    except Exception as e:
        print(f"爬取书签排名页面时出错: {e}")

    # 过滤掉不是作者名的链接（如登录、注册等）
    filtered_usernames = {
        username
        for username in all_usernames
        if username not in ["login", "register", "ranking", "bookmark-ranking"]
    }

    return filtered_usernames, counter


def save_writer_data(writer_data, filename=None):
    """保存作者数据到单个文件，按要求格式化"""
    if filename is None:
        # 使用配置文件中的路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(config.result_dir, f"writer_data_{timestamp}.txt")

    # 确保目录存在
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    with open(filename, "w", encoding="utf-8") as f:
        # 第一部分：信息对应表
        f.write("=== 作者信息对应表 ===\n")
        for item in writer_data:
            f.write(f"{item['username']}:{item['id']}\n")

        f.write("\n\n")

        # 第二部分：用逗号分隔的ID列表
        f.write("=== ID列表(用逗号分隔) ===\n")
        id_list = [item["id"] for item in writer_data]
        f.write(",".join(id_list))

        f.write("\n\n")

        # 第三部分：用户名列表(用逗号分隔)
        f.write("=== 用户名列表(用逗号分隔) ===\n")
        username_list = [item["username"] for item in writer_data]
        f.write(",".join(username_list))

    print(f"作者数据已保存到: {filename}")
    return filename


class WriterExtractor:
    """作者信息提取器类，用于获取热门作者ID列表"""

    def __init__(self):
        self.request_counter = 0

    def extract_all_writers(self):
        """提取所有热门作者信息

        从排名页面获取热门作者列表并提取其ID

        Returns:
            list: 作者信息列表，每项包含username和id
        """
        # 获取所有writerusername
        writer_usernames, self.request_counter = get_writers_from_ranking_pages(self.request_counter)
        print(f"找到 {len(writer_usernames)} 个不重复的writerusername")

        # 获取每个作者的ID
        writer_ids = []
        writer_data = []  # 存储包含username和id的字典列表

        for i, username in enumerate(writer_usernames, 1):
            print(f"正在处理 ({i}/{len(writer_usernames)}): {username}")

            self.request_counter += 1  # 增加请求计数

            writer_id = get_writer_info(username, self.request_counter)
            if writer_id:
                writer_ids.append(writer_id)
                writer_data.append({"username": username, "id": writer_id})
                print(f"成功: {username} -> {writer_id}")

        # 保存结果
        if writer_data:
            save_writer_data(writer_data)
            print(f"已将 {len(writer_data)} 个作者的信息保存到文件")
        else:
            print("未找到作者信息，无法保存")

        return writer_data


def main():
    """主程序入口"""
    print("=== FC2 热门作者提取工具 ===")

    try:
        extractor = WriterExtractor()
        result = extractor.extract_all_writers()

        if result:
            print(f"成功提取并保存了 {len(result)} 个热门作者信息")
        else:
            print("未能提取到作者信息")

    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序运行时出错: {e}")


if __name__ == "__main__":
    main()
