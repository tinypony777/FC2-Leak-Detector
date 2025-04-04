"""
FC2Checker - 用于检查FC2视频状态的模块

提供全面的FC2视频检查功能，可检测视频流出状态并生成分析报告
"""
import concurrent.futures
import json
import os
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config import config


class FC2Checker:
    def __init__(self):
        # 使用配置文件中的请求头
        self.headers = config.base_headers
        self.results = []
        self.leaked_count = 0
        self.total_count = 0

    def fetch_videos(self, actress_id):
        """获取指定演员ID的所有视频"""
        all_videos = []
        page = 1

        print(f"开始获取演员ID {actress_id} 的视频列表...")

        while True:
            # 使用配置文件中的API基础URL
            url = f"{config.fc2ppvdb_api_base}/actresses/actress-articles?actressid={actress_id}&page={page}"
            try:
                # 使用配置文件中的超时设置
                response = requests.get(url, headers=self.headers, timeout=config.timeout)
                if response.status_code != 200:
                    print(f"获取第{page}页失败，状态码: {response.status_code}")
                    break

                data = response.json()
                videos = data.get("data", [])

                if not videos:
                    break

                for video in videos:
                    video_id = video.get("video_id")
                    title = video.get("title", "无标题")
                    if video_id:
                        all_videos.append({"video_id": video_id, "title": title})

                print(f"已获取第{page}页，找到{len(videos)}个视频")
                page += 1

                # 使用配置文件中的请求间隔设置
                time.sleep(random.uniform(config.page_interval[0], config.page_interval[1]))

                # 检查是否是最后一页
                if page > data.get("last_page", 1):
                    break

            except Exception as e:
                print(f"获取视频列表时出错: {str(e)}")
                break

        print(f"总计获取到 {len(all_videos)} 个视频")
        self.total_count = len(all_videos)
        return all_videos

    def check_video_status(self, video):
        """检查单个视频是否流出"""
        video_id = video["video_id"]
        title = video["title"]

        # 使用配置文件中的检查站点URL
        check_site = config.check_sites[0]  # 使用第一个检查站点
        check_url = check_site["url"].format(vid=video_id)

        try:
            # 添加重试逻辑和超时设置
            max_retries = config.max_retries
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    response = requests.get(check_url, headers=self.headers, timeout=config.timeout)
                    break
                except requests.exceptions.RequestException as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        raise e
                    # 使用指数退避策略进行重试
                    sleep_time = config.retry_base ** retry_count
                    time.sleep(sleep_time)

            # 根据状态码判断是否流出
            if response.status_code in check_site["status_codes"]:
                status = "已流出"
                self.leaked_count += 1
                self.results.append(
                    {"video_id": video_id, "title": title, "status": status}
                )
                print(f"✅ {video_id} | {title} - {status}")
            elif response.status_code == 404:
                status = "未流出"
                # 未流出的不记录在结果中
                print(f"❌ {video_id} | {title} - {status}")
            else:
                status = f"异常({response.status_code})"
                print(f"⚠️ {video_id} | {title} - {status}")

            return {"video_id": video_id, "title": title, "status": status}

        except Exception as e:
            print(f"检查视频 {video_id} 时出错: {str(e)}")
            return {"video_id": video_id, "title": title, "status": "请求失败"}

    def check_all_videos(self, videos, max_workers=None):
        """并发检查所有视频状态"""
        # 使用配置文件中的最大并发数
        max_workers = max_workers or config.max_workers
        
        print(f"开始检查 {len(videos)} 个视频是否流出...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.check_video_status, video): video
                for video in videos
            }

            for future in as_completed(futures):
                try:
                    future.result()  # 获取结果（主要为了捕获异常）
                except Exception as e:
                    video = futures[future]
                    print(f"处理视频 {video['video_id']} 时发生异常: {str(e)}")

        # 排序结果
        self.results.sort(key=lambda x: x["video_id"])

        # 打印汇总信息
        print("\n===== 检查完成 =====")
        print(f"总视频数: {self.total_count}")
        print(f"已流出数: {self.leaked_count}")
        print(f"流出比例: {self.leaked_count / self.total_count * 100:.2f}%")

        # 打印已流出的视频列表
        if self.leaked_count > 0:
            print("\n===== 已流出视频列表 =====")
            for idx, result in enumerate(self.results, 1):
                print(f"{idx}. {result['video_id']} | {result['title']}")

        return self.results

    def save_results(self, results, actress_id):
        """保存结果到文件

        Args:
            results: 结果列表
            actress_id: 女优ID

        Returns:
            str: 保存的文件路径
        """
        if not results:
            print("没有结果可保存")
            return None

        # 创建结果目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_dir = os.path.join(config.result_dir, f"actress_{actress_id}")
        os.makedirs(save_dir, exist_ok=True)

        # 文件路径
        filepath = os.path.join(save_dir, f"results_{timestamp}")  # 去掉.json后缀

        try:
            # 计算统计数据
            total = len(results)
            leaked = sum(1 for r in results if r.get("status") == "已流出")
            unleaked = total - leaked
            leak_ratio = (leaked / total) * 100 if total > 0 else 0

            # 使用配置的保存格式
            if "text" in config.save_format:
                # 文本格式保存
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(f"FC2 女优视频分析结果\n")
                    f.write(f"女优ID: {actress_id}\n")
                    f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"总视频数: {total}\n")
                    f.write(f"已流出视频数: {leaked}\n")
                    f.write(f"未流出视频数: {unleaked}\n")
                    f.write(f"流出比例: {leak_ratio:.2f}%\n\n")

                    # 保存已流出视频
                    f.write(f"=== 已流出视频 ({leaked}) ===\n\n")
                    leaked_videos = [r for r in results if r.get("status") == "已流出"]
                    for idx, video in enumerate(leaked_videos, 1):
                        f.write(
                            f"{idx}. {video.get('video_id', 'unknown')} | {video.get('title', '未知标题')}\n"
                        )
                        if "magnet" in video:
                            f.write(f"   磁力链接: {video['magnet']}\n")

                    # 保存未流出视频
                    f.write(f"\n=== 未流出视频 ({unleaked}) ===\n\n")
                    unleaked_videos = [r for r in results if r.get("status") != "已流出"]
                    for idx, video in enumerate(unleaked_videos, 1):
                        f.write(
                            f"{idx}. {video.get('video_id', 'unknown')} | {video.get('title', '未知标题')}\n"
                        )

            # 添加JSON格式保存选项
            if "json" in config.save_format:
                json_filepath = f"{filepath}.json"
                json_data = {
                    "actress_id": actress_id,
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "total_videos": total,
                    "leaked_videos": leaked,
                    "unleaked_videos": unleaked,
                    "leak_ratio": leak_ratio,
                    "results": results
                }
                with open(json_filepath, "w", encoding="utf-8") as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=2)

            print(f"结果已保存到 {filepath}")
            return filepath

        except Exception as e:
            print(f"保存结果失败: {e}")
            return None


def main():
    """主程序入口"""
    print("=== FC2 视频检查工具 ===")
    actress_id = input("请输入女优ID (如在fc2ppvdb.com的URL中): ").strip()

    if not actress_id:
        print("ID不能为空！")
        return

    checker = FC2Checker()

    # 获取视频列表
    videos = checker.fetch_videos(actress_id)

    # 检查视频可用性
    results = checker.check_all_videos(videos)

    # 保存结果
    checker.save_results(results, actress_id)
    print("程序执行完毕！")


if __name__ == "__main__":
    main()
