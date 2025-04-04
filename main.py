# -*- coding: utf-8 -*-
"""
FC2 流出检测器 - 主程序

此程序用于分析FC2视频信息，可通过作者ID或女优ID进行分析，
获取视频流出状态、磁力链接和缩略图等信息。
"""
import argparse
import json
import os
import re
import ssl
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from json.decoder import JSONDecodeError
from urllib.error import HTTPError, URLError

from requests.exceptions import ConnectionError, RequestException, Timeout

from src.checkers.fc2analyzer import FC2Analyzer
from config import config
from src.utils.fc2_video_parser import find_writer_by_video
from src.utils.logger import get_logger
from src.utils.report_generator import ReportGenerator
from src.utils.ui_manager import RichUIManager
from src.writers.writer_extractor import WriterExtractor

# 获取主程序日志记录器
logger = get_logger("main")


# 定义自定义异常类型
class FC2AnalyzerError(Exception):
    """FC2分析器基础异常类"""

    pass


class NetworkError(FC2AnalyzerError):
    """网络相关错误"""

    pass


class DataParsingError(FC2AnalyzerError):
    """数据解析错误"""

    pass


class ResourceNotFoundError(FC2AnalyzerError):
    """资源未找到错误"""

    pass


class FileOperationError(FC2AnalyzerError):
    """文件操作错误"""

    pass


def is_leaked(video_result):
    """
    判断视频是否已流出

    参数:
        video_result: 视频结果字典

    返回:
        bool: 视频是否已流出
    """
    if "exists" in video_result:
        return video_result["exists"]
    # 默认视为未流出
    return False


def print_usage():
    """显示程序使用说明"""
    usage = """
使用方法: python run.py [选项]

选项:
  -h, --help                显示此帮助信息
  -c, --config              显示配置信息
  -s, --sites               显示检查站点列表
  -w ID, --writer ID        分析作者ID的视频
  -a ID, --actress ID       分析女优ID的视频
  -b IDs, --batch IDs       批量处理多个作者ID（用英文逗号分隔）
  -ba IDs, --batch-actress IDs  批量处理多个女优ID（用英文逗号分隔）
  -e, --extract             提取热门作者列表
  -v ID, --video ID         通过视频ID查找并分析作者
  -t NUM, --threads NUM     指定并行线程数（默认30）   
  --no-magnet               不获取磁力链接
  --no-image                不下载视频缩略图

示例:
  python run.py -w 5656               # 分析作者ID 5656 的视频
  python run.py -a 5711               # 分析女优ID 5711 的视频
  python run.py -b 5656,3524,4461     # 批量处理多个作者
  python run.py -ba 5711,3986,4219    # 批量处理多个女优
  python run.py -e                    # 提取热门作者列表
  python run.py -v 1248860            # 通过视频ID查找并分析作者
  python run.py -c                    # 显示配置信息
  python run.py -w 5656 -t 10         # 使用10个线程分析作者视频
  python run.py -a 5711 --no-magnet   # 分析女优视频但不获取磁力链接
  python run.py -w 5656 --no-image    # 分析作者视频但不下载缩略图
"""
    print(usage)


def show_config_info():
    """显示当前配置信息"""
    print("=== 当前配置信息 ===")
    print(f"数据目录: {config.cache_dir}")
    print(f"最大线程数: {config.max_workers}")
    print(f"最大重试次数: {config.max_retries}")
    print(f"缓存有效期: {config.cache_ttl/3600:.1f}小时")

    # 显示检查站点配置
    show_check_sites()


def show_check_sites():
    """显示当前配置的检查站点"""
    check_sites = sorted(config.check_sites, key=lambda x: x["priority"])

    if not check_sites:
        print("⚠️ 未配置任何检查站点，将使用默认站点")
        return

    print("\n=== 视频检查站点 (按优先级排序) ===")
    for idx, site in enumerate(check_sites, 1):
        site_name = site.get("name", site["url"].split("/")[2])
        print(f"{idx}. 站点: {site_name}")
        print(f"   网址模板: {site['url']}")
        print(f"   优先级: {site['priority']}")


def extract_writer_info():
    """提取热门作者列表

    从FC2PPVDB获取热门作者列表并保存到文件

    返回:
        bool: 操作是否成功
    """
    extractor = WriterExtractor()

    print("开始获取热门作者列表...")
    writer_data = extractor.extract_all_writers()
    if writer_data:
        print(f"✅ 已获取 {len(writer_data)} 个热门作者信息")
        return True
    else:
        print("❌ 无法获取热门作者列表")
        return False


def check_videos(
    target_id, is_actress=False, threads=None, with_magnet=True, download_images=True
):
    """通用视频分析函数

    获取指定ID的所有视频并检查其流出状态，同时获取磁力链接和缩略图

    参数:
        target_id: 作者ID或女优ID
        is_actress: 是否为女优ID
        threads: 并行线程数
        with_magnet: 是否获取磁力链接
        download_images: 是否下载缩略图

    返回:
        bool: 操作是否成功
    """
    # 根据类型确定显示文本
    entity_type = "女优" if is_actress else "作者"

    try:
        # 创建分析器
        analyzer = FC2Analyzer(
            target_id,
            is_actress=is_actress,
            with_magnet=with_magnet,
            download_images=download_images,
            quiet_mode=False,
        )

        # 设置并行线程数，优先使用传入参数，其次使用配置，最后是默认值
        max_workers = threads if threads is not None else config.max_workers
        # 确保线程数在合理范围内
        max_workers = max(1, min(max_workers, 50))  # 至少1个线程，最多50个线程

        # 设置请求超时
        timeout = config.timeout  # 从配置获取超时时间，默认15秒

        # 获取名称
        try:
            author_name = analyzer.fetch_author_name()
            if author_name:
                print(f"✅ {entity_type}名称: {author_name}")
        except ConnectionError as e:
            logger.error(f"获取{entity_type}名称时连接错误: {e}")
            print(f"⚠️ 获取{entity_type}名称时连接错误: {e}")
            author_name = None
        except Timeout as e:
            logger.error(f"获取{entity_type}名称时连接超时: {e}")
            print(f"⚠️ 获取{entity_type}名称时连接超时: {e}")
            author_name = None
        except HTTPError as e:
            logger.error(f"获取{entity_type}名称时HTTP错误: {e.code} - {e.reason}")
            print(f"⚠️ 获取{entity_type}名称时HTTP错误: {e.code} - {e.reason}")
            author_name = None

        # 获取视频列表
        try:
            videos = analyzer.fetch_video_ids()
            if not videos:
                logger.warning(f"未找到{entity_type} {target_id} 的视频")
                print(f"❌ 未找到{entity_type} {target_id} 的视频")
                return False
        except ConnectionError as e:
            logger.error(f"获取视频列表时连接错误: {e}")
            print(f"❌ 获取视频列表时连接错误: {e}")
            return False
        except Timeout as e:
            logger.error(f"获取视频列表时连接超时: {e}")
            print(f"❌ 获取视频列表时连接超时: {e}")
            return False
        except HTTPError as e:
            logger.error(f"获取视频列表时HTTP错误: {e.code} - {e.reason}")
            print(f"❌ 获取视频列表时HTTP错误: {e.code} - {e.reason}")
            return False
        except JSONDecodeError as e:
            logger.error(f"解析视频数据时格式错误: {e}")
            print(f"❌ 解析视频数据时格式错误: {e}")
            return False

        # 显示进度信息
        total_videos = len(videos)
        print(f"总共找到 {total_videos} 个视频，开始分析...")

        # 分析视频时明确指定线程数和超时设置
        try:
            # 注意：analyze_videos方法不接受max_workers参数
            # 线程数由FC2Analyzer构造函数或内部配置控制
            results, stats = analyzer.analyze_videos(videos)
        except Exception as e:
            logger.error(f"分析视频时出错: {type(e).__name__}: {e}")
            print(f"❌ 分析视频时出错: {e}")
            return False

        try:
            # 确保目录存在
            try:
                os.makedirs(config.result_dir, exist_ok=True)
            except PermissionError as e:
                logger.error(f"创建结果目录时权限不足: {e}")
                print(f"❌ 创建结果目录时权限不足: {e}")
                return False
            except OSError as e:
                logger.error(f"创建结果目录时系统错误: {e}")
                print(f"❌ 创建结果目录时系统错误: {e}")
                return False

            # 生成自定义的保存路径
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 检查名称是否包含非法字符
            has_special_chars = False
            if author_name:
                has_special_chars = any(
                    c in author_name
                    for c in ["\\", "/", "*", "?", ":", '"', "<", ">", "|"]
                )

            if has_special_chars or not author_name:
                # 如果包含特殊字符或名称为空，只使用ID
                print(f"⚠️ {entity_type}名称包含特殊字符或为空，仅使用ID作为文件名")
                save_path = os.path.join(
                    config.result_dir,
                    f"{target_id}_{timestamp}.txt",
                )
            else:
                # 清理名称，确保安全
                cleaned_name = re.sub(r'[\\/*?:"<>|]', "_", author_name).strip()
                save_path = os.path.join(
                    config.result_dir,
                    f"{target_id}_{cleaned_name}_{timestamp}.txt",
                )

            # 打印基本的统计信息
            total = len(results)
            leaked = sum(1 for r in results if is_leaked(r))
            leak_ratio = (leaked / total) * 100 if total > 0 else 0

            # 写入结果摘要
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(
                        f"{entity_type}: {target_id} [{author_name or 'Unknown'}]\n"
                    )
                    f.write(f"总视频数: {total}\n")
                    f.write(f"已流出数: {leaked}\n")
                    f.write(f"流出比例: {leak_ratio:.2f}%\n\n")

                    # 写入基本的视频信息
                    f.write("视频列表:\n")
                    for r in results:
                        video_id = r.get("video_id", r.get("id", "unknown"))
                        status = "已流出" if is_leaked(r) else "未流出"
                        title = r.get("title", f"FC2-PPV-{video_id}")

                        # 添加磁力链接信息（如果有）
                        magnet_info = ""
                        if with_magnet and r.get("has_magnet", False):
                            magnet_info = f" [有磁链]"

                        # 添加图片信息（如果有）
                        image_info = ""
                        if download_images and r.get("image_downloaded", False):
                            image_info = f" [有图片]"

                        f.write(
                            f"{video_id} - {status}{magnet_info}{image_info} - {title}\n"
                        )

                print(f"✅ 结果已保存到: {save_path}")
            except PermissionError as e:
                logger.error(f"写入结果文件时权限不足: {e}")
                print(f"❌ 写入结果文件时权限不足: {e}")
            except IOError as e:
                logger.error(f"写入结果文件时I/O错误: {e}")
                print(f"❌ 写入结果文件时I/O错误: {e}")

            # 显示详细统计信息
            analyzer.display_results(results, stats)

            # 调用generate_reports方法生成分类报告
            try:
                reports = analyzer.generate_reports(target_id, results, author_name)
                if reports:
                    print(f"✅ 成功为{entity_type} {target_id} 生成 {len(reports)} 个分类报告")
                    for report_type, report_path in reports.items():
                        print(f"  - {report_type}: {report_path}")
            except Exception as e:
                logger.error(f"生成分类报告时出错: {type(e).__name__}: {e}")
                print(f"⚠️ 生成分类报告时出错: {e}")

        except Exception as e:
            logger.error(f"保存结果时出错: {type(e).__name__}: {e}\n{traceback.format_exc()}")
            print(f"⚠️ 保存结果时出错: {e}")
            return False

        print(f"总视频数: {total}")
        print(f"已流出数: {leaked}")
        print(f"流出比例: {leak_ratio:.2f}%")

        return True
    except KeyboardInterrupt:
        logger.info("用户中断了操作")
        print("\n⚠️ 操作已中断")
        return False
    except ssl.SSLError as e:
        logger.error(f"SSL连接错误: {e}")
        print(f"❌ SSL连接错误: {e}")
        return False
    except Exception as e:
        logger.error(
            f"分析{entity_type}视频时出错: {type(e).__name__}: {e}\n{traceback.format_exc()}"
        )
        print(f"❌ 分析{entity_type}视频时出错: {type(e).__name__}: {e}")
        return False


def process_multiple_ids(
    ids, is_actress=False, threads=None, with_magnet=True, download_images=True
):
    """批量处理多个作者或女优

    依次分析多个ID的视频，并生成汇总报告

    参数:
        ids: ID列表或逗号分隔的字符串
        is_actress: 是否为女优ID
        threads: 并行线程数
        with_magnet: 是否获取磁力链接
        download_images: 是否下载缩略图

    返回:
        bool: 操作是否成功
    """
    # 确定处理的实体类型
    entity_type = "女优" if is_actress else "作者"
    id_field = "actress_id" if is_actress else "writer_id"
    name_field = "actress_name" if is_actress else "writer_name"

    # 解析ID
    if isinstance(ids, str):
        id_list = ids.split(",")
    else:
        id_list = ids

    # 去除空白项和重复项
    id_list = [item.strip() for item in id_list if item.strip()]
    id_list = list(set(id_list))

    if not id_list:
        print(f"❌ 未提供有效的{entity_type}ID")
        return False

    # 设置并行线程数，优先使用传入参数，其次使用配置，最后是默认值
    max_workers = threads if threads is not None else config.max_workers
    # 确保线程数在合理范围内
    max_workers = max(1, min(max_workers, 50))  # 至少1个线程，最多50个线程

    total_ids = len(id_list)
    print(f"准备分析 {total_ids} 个{entity_type}")

    # 初始化UI管理器
    ui_manager = RichUIManager()
    ui_manager.set_multi_author_mode(total_ids)

    processed_items = []

    # 创建缓存目录
    cache_dir = os.path.join(config.cache_dir, "batch_process")
    os.makedirs(cache_dir, exist_ok=True)

    # 处理每个ID
    for idx, item_id in enumerate(id_list, 1):
        try:
            # 检查缓存是否存在且有效
            cache_file = os.path.join(
                cache_dir, f"{'actress' if is_actress else 'writer'}_{item_id}.json"
            )
            cache_valid = False

            # 如果之前有缓存，检查是否过期
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "rb") as f:
                        cache_data = json.load(f)
                    
                    # 计算缓存年龄
                    cache_time = datetime.strptime(cache_data["timestamp"], "%Y-%m-%d %H:%M:%S")
                    cache_age = (datetime.now() - cache_time).total_seconds()
                    
                    # 如果缓存年龄小于配置的缓存有效期，使用缓存
                    if cache_age < config.cache_ttl:
                        ui_manager.add_log(
                            f"使用缓存数据: {entity_type} {item_id}", False
                        )

                        # 使用缓存的结果
                        total_videos = cache_data.get("total_videos", 0)
                        leaked_count = cache_data.get("leaked_videos", 0)
                        author_name = cache_data.get(
                            name_field, f"{entity_type}_{item_id}"
                        )

                        ui_manager.update_author_progress(idx, item_id, author_name)
                        ui_manager.mark_author_completed(
                            item_id, total_videos, leaked_count, author_name
                        )

                        processed_items.append(cache_data)
                        cache_valid = True
                        continue
                except Exception as e:
                    ui_manager.add_log(f"读取缓存出错: {e}", True)
                    # 继续正常处理，忽略缓存错误

            # 如果没有有效缓存，正常处理
            if not cache_valid:
                # 更新进度
                ui_manager.update_author_progress(idx, item_id)

                # 创建分析器
                analyzer = FC2Analyzer(
                    item_id,
                    is_actress=is_actress,
                    with_magnet=with_magnet,
                    download_images=download_images,
                )

                # 获取名称
                author_name = analyzer.fetch_author_name()
                if author_name:
                    ui_manager.update_author_progress(idx, item_id, author_name)

                # 获取视频列表
                videos = analyzer.fetch_video_ids()
                if not videos:
                    ui_manager.add_log(f"未找到{entity_type} {item_id} 的视频", True)
                    ui_manager.mark_author_completed(item_id, 0, 0, author_name)
                    item_result = {
                        id_field: item_id,
                        name_field: author_name,
                        "results": [],
                        "status": "no_videos",
                    }
                    processed_items.append(item_result)
                    continue

                total_videos = len(videos)
                ui_manager.update_multi_author_total_videos(total_videos)

                # 分析视频，明确指定线程数
                results, stats = analyzer.analyze_videos(videos)

                # 生成分类报告
                reports = analyzer.generate_reports(item_id, results, author_name)
                if reports:
                    print(f"✅ 成功为{entity_type} {item_id} 生成 {len(reports)} 个分类报告")
                    for report_type, report_path in reports.items():
                        print(f"  - {report_type}: {report_path}")

                # 记录处理结果
                videos = analyzer.all_videos if hasattr(analyzer, "all_videos") else []
                results = analyzer.results if hasattr(analyzer, "results") else []

                leaked_count = sum(1 for r in results if is_leaked(r))

                # 添加更详细的统计信息到UI管理器
                if hasattr(ui_manager, "total_with_magnet"):
                    with_magnet_count = sum(
                        1
                        for r in results
                        if is_leaked(r) and r.get("has_magnet", False)
                    )
                    ui_manager.total_with_magnet = (
                        getattr(ui_manager, "total_with_magnet", 0) + with_magnet_count
                    )
                else:
                    with_magnet_count = sum(
                        1
                        for r in results
                        if is_leaked(r) and r.get("has_magnet", False)
                    )
                    ui_manager.total_with_magnet = with_magnet_count

                if hasattr(ui_manager, "total_image_downloaded"):
                    image_downloaded_count = sum(
                        1 for r in results if r.get("image_downloaded", False)
                    )
                    ui_manager.total_image_downloaded = (
                        getattr(ui_manager, "total_image_downloaded", 0)
                        + image_downloaded_count
                    )
                else:
                    image_downloaded_count = sum(
                        1 for r in results if r.get("image_downloaded", False)
                    )
                    ui_manager.total_image_downloaded = image_downloaded_count

                # 添加重试统计
                if (
                    isinstance(stats, dict)
                    and "magnet_retries" in stats
                    and "magnet_retry_success" in stats
                ):
                    ui_manager.magnet_retries = getattr(
                        ui_manager, "magnet_retries", 0
                    ) + stats.get("magnet_retries", 0)
                    ui_manager.magnet_retry_success = getattr(
                        ui_manager, "magnet_retry_success", 0
                    ) + stats.get("magnet_retry_success", 0)

                ui_manager.mark_author_completed(
                    item_id, total_videos, leaked_count, author_name
                )

                item_result = {
                    id_field: item_id,
                    name_field: author_name or f"{entity_type}_{item_id}",
                    "total_videos": len(videos),
                    "processed_videos": len(results),
                    "leaked_videos": leaked_count,
                    "with_magnet": with_magnet_count,
                    "image_downloaded": image_downloaded_count,
                    "leaked_ratio": leaked_count / max(len(results), 1) * 100,
                    "results": results,
                    "status": "success",
                }

                processed_items.append(item_result)

                # 保存结果到缓存
                try:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(item_result, f, ensure_ascii=False, indent=2)
                    ui_manager.add_log(f"已将{entity_type} {item_id} 的分析结果保存到缓存", False)
                except Exception as e:
                    ui_manager.add_log(f"保存缓存出错: {e}", True)

        except Exception as e:
            ui_manager.add_log(f"处理{entity_type} {item_id} 时出错: {e}", True)
            ui_manager.mark_author_completed(item_id, 0, 0, None)

            item_result = {
                id_field: item_id,
                name_field: None,
                "results": [],
                "status": "error",
                "error": str(e),
            }
            processed_items.append(item_result)

    # 完成所有处理
    ui_manager.finish()

    # 只有当处理多个ID时才生成汇总报告
    if len(id_list) > 1:
        # 生成汇总报告
        if is_actress:
            generate_multi_actress_report(processed_items)
        else:
            generate_multi_writer_report(processed_items)
    else:
        print(f"单{entity_type}分析完成，无需生成汇总报告")

    return True


def generate_multi_writer_report(processed_writers):
    """生成多作者汇总报告

    将多个作者的分析结果汇总到一个报告中

    参数:
        processed_writers: 处理过的作者列表
    """
    if not processed_writers:
        print("没有数据可以生成报告")
        return

    # 使用ReportGenerator生成汇总报告
    report_generator = ReportGenerator()
    report_path = report_generator.generate_multi_writer_report(processed_writers)

    if report_path:
        print(f"✅ 汇总报告已生成: {report_path}")
    else:
        print("❌ 汇总报告生成失败")


def generate_multi_actress_report(processed_actresses):
    """生成多女优汇总报告

    将多个女优的分析结果汇总到一个报告中

    参数:
        processed_actresses: 处理过的女优列表
    """
    if not processed_actresses:
        print("没有数据可以生成报告")
        return

    # 使用ReportGenerator生成汇总报告
    report_generator = ReportGenerator()
    report_path = report_generator.generate_multi_actress_report(processed_actresses)

    if report_path:
        print(f"✅ 汇总报告已生成: {report_path}")
    else:
        print("❌ 汇总报告生成失败")


def find_writer_by_video_id(
    video_id, threads=None, with_magnet=True, download_images=True
):
    """通过视频ID查找并分析作者

    通过在FC2PPVDB上查询视频信息，获取作者信息并分析其所有作品

    Args:
        video_id: 视频ID
        threads: 并行线程数
        with_magnet: 是否获取磁力链接
        download_images: 是否下载缩略图

    Returns:
        bool: 操作是否成功
    """
    print(f"开始通过视频ID {video_id} 查找作者信息...")

    try:
        # 设置请求超时
        timeout = config.timeout  # 从配置获取超时时间，默认15秒

        # 使用fc2_video_parser查找作者
        writer_id, writer_username = find_writer_by_video(video_id)

        if not writer_id:
            if writer_username:
                print(f"❌ 已找到作者用户名 {writer_username}，但无法获取其ID")
            else:
                print(f"❌ 无法通过视频ID {video_id} 找到作者信息")
            return False

        print(f"✅ 已找到作者: ID={writer_id}, 用户名={writer_username}")
        print(f"开始分析作者 {writer_id} 的所有视频...")

        # 使用找到的作者ID进行分析
        return check_videos(
            writer_id,
            is_actress=False,
            threads=threads,
            with_magnet=with_magnet,
            download_images=download_images,
        )
    except ConnectionError as e:
        logger.error(f"查找作者时连接错误: {e}")
        print(f"❌ 查找作者时连接错误: {e}")
        return False
    except Timeout as e:
        logger.error(f"查找作者时连接超时: {e}")
        print(f"❌ 查找作者时连接超时: {e}")
        return False
    except JSONDecodeError as e:
        logger.error(f"解析作者数据时格式错误: {e}")
        print(f"❌ 解析作者数据时格式错误: {e}")
        return False
    except ValueError as e:
        logger.error(f"查找作者参数错误: {e}")
        print(f"❌ 查找作者参数错误: {e}")
        return False
    except Exception as e:
        logger.error(f"查找作者时未知错误: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        print(f"❌ 查找作者时出错: {type(e).__name__}: {e}")
        return False


def main():
    """程序主入口"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="FC2流出检测器", add_help=False)
    parser.add_argument("-h", "--help", action="store_true", help="显示帮助信息")
    parser.add_argument("-c", "--config", action="store_true", help="显示配置信息")
    parser.add_argument("-s", "--sites", action="store_true", help="显示检查站点列表")
    parser.add_argument("-w", "--writer", type=str, help="分析作者ID的视频")
    parser.add_argument("-a", "--actress", type=str, help="分析女优ID的视频")
    parser.add_argument("-b", "--batch", type=str, help="批量处理多个作者ID（用英文逗号分隔）")
    parser.add_argument("-ba", "--batch-actress", type=str, help="批量处理多个女优ID（用英文逗号分隔）")
    parser.add_argument("-e", "--extract", action="store_true", help="提取热门作者列表")
    parser.add_argument("-v", "--video", type=str, help="通过视频ID查找并分析作者")
    parser.add_argument("-t", "--threads", type=int, help="指定并行线程数")
    parser.add_argument("--no-magnet", action="store_true", help="不获取磁力链接")
    parser.add_argument("--no-image", action="store_true", help="不下载视频缩略图")

    try:
        args, unknown = parser.parse_known_args()

        # 显示帮助信息
        if args.help or len(sys.argv) == 1:
            print_usage()
            return 0

        # 显示配置信息
        if args.config:
            show_config_info()
            return 0

        # 显示检查站点列表
        if args.sites:
            show_check_sites()
            return 0

        # 设置并行线程数，优先使用命令行参数，其次使用配置，最后是默认值
        threads = (
            args.threads if args.threads is not None else config.max_workers
        )
        # 确保线程数在合理范围内
        threads = max(1, min(threads, 50))  # 至少1个线程，最多50个线程

        # 如果设置了线程数参数，更新全局配置
        if args.threads is not None:
            config.max_workers = threads
            print(f"已设置并行线程数为: {threads}")

        # 提取热门作者列表
        if args.extract:
            success = extract_writer_info()
            return 0 if success else 1

        # 设置磁链和图片下载选项
        with_magnet = not args.no_magnet
        download_images = not args.no_image

        # 通过视频ID查找并分析作者
        if args.video:
            success = find_writer_by_video_id(
                args.video, threads, with_magnet, download_images
            )
            return 0 if success else 1

        # 根据命令行参数执行相应功能
        if args.writer:
            check_videos(
                args.writer,
                is_actress=False,
                threads=threads,
                with_magnet=with_magnet,
                download_images=download_images,
            )
        elif args.actress:
            check_videos(
                args.actress,
                is_actress=True,
                threads=threads,
                with_magnet=with_magnet,
                download_images=download_images,
            )
        elif args.batch:
            process_multiple_ids(
                args.batch,
                is_actress=False,
                threads=threads,
                with_magnet=with_magnet,
                download_images=download_images,
            )
        elif args.batch_actress:
            process_multiple_ids(
                args.batch_actress,
                is_actress=True,
                threads=threads,
                with_magnet=with_magnet,
                download_images=download_images,
            )
        else:
            print_usage()

        return 0
    except KeyboardInterrupt:
        print("\n⚠️ 程序已被用户中断")
        return 1
    except argparse.ArgumentError as e:
        print(f"❌ 命令行参数错误: {e}")
        print_usage()
        return 1
    except Exception as e:
        logger.critical(f"程序运行时出错: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        print(f"❌ 程序运行时出错: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
