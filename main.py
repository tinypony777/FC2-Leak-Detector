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
from datetime import datetime, timedelta
from json.decoder import JSONDecodeError
from urllib.error import HTTPError, URLError
import glob

from requests.exceptions import ConnectionError, RequestException, Timeout

from src.checkers.fc2analyzer import FC2Analyzer
from config import config
from src.utils.fc2_video_parser import find_writer_by_video
from src.utils.logger import get_logger
from src.utils.report_generator import ReportGenerator
from src.utils.ui_manager import RichUIManager
from src.writers.writer_extractor import WriterExtractor
from src.utils.i18n import get_text as _, switch_language, get_current_language, SUPPORTED_LANGUAGES
from src.utils.jellyfin_metadata_generator import JellyfinMetadataGenerator

# 获取主程序日志记录器
logger = get_logger("main")

def print_usage():
    """打印使用帮助信息"""
    # 获取当前语言
    current_lang = get_current_language()
    
    # 根据当前语言设置目标语言
    if current_lang == "zh":
        target_lang = "en"
    elif current_lang == "en":
        target_lang = "ja"
    else:  # current_lang == "ja" or any other
        target_lang = "zh"
    
    usage = f"""
{_('usage_title', '使用方法')}: python run.py [选项]

{_('usage_options', '选项')}:
  -h, --help                {_('usage_help', '显示此帮助信息')}
  -w ID, --writer ID        {_('usage_writer', '分析作者ID的视频')}
  -a ID, --actress ID       {_('usage_actress', '分析女优ID的视频')}
  -b IDs, --batch IDs       {_('usage_batch', '批量处理多个作者ID (用英文逗号分隔)')}
  -ba IDs, --batch-actress IDs  {_('usage_batch_actress', '批量处理多个女优ID (用英文逗号分隔)')}
  -v ID, --video ID         {_('usage_video', '通过视频ID查找并分析作者')}
  -t NUM, --threads NUM     {_('usage_threads', '指定并行线程数 (默认30)')}
  --jellyfin                {_('usage_jellyfin', '生成Jellyfin兼容的元数据；可单独使用，会查找48小时内的分析结果')}
  --no-magnet               {_('usage_no_magnet', '不获取磁力链接')}
  --no-image                {_('usage_no_image', '不下载视频缩略图')}
  -l LANG, --lang LANG      {_('usage_lang', '设置界面语言 (支持: zh, en, ja)')}
  -c, --config              {_('usage_config', '显示配置信息')}
  -s, --sites               {_('usage_sites', '显示检查站点列表')}
  -e, --extract             {_('usage_extract', '提取热门作者列表')}
  --clear-cache             {_('usage_clear_cache', '清除所有缓存数据')}

{_('usage_examples', '示例')}:
  python run.py -w 5656               # {_('example_writer', '分析作者ID 5656 的视频')}
  python run.py -a 5711               # {_('example_actress', '分析女优ID 5711 的视频')}
  python run.py -b 5656,3524,4461     # {_('example_batch', '批量处理多个作者')}
  python run.py -ba 5711,3986,4219    # {_('example_batch_actress', '批量处理多个女优')}
  python run.py -v 1248860            # {_('example_video', '通过视频ID查找并分析作者')}
  python run.py -w 5656 -t 10         # {_('example_threads', '使用10个线程分析作者视频')}
  python run.py -w 5656 --jellyfin    # {_('example_jellyfin', '分析作者视频并生成Jellyfin元数据')}
  python run.py --jellyfin            # {_('example_jellyfin', '使用最近的分析结果生成Jellyfin元数据')}
  python run.py -a 5711 --no-magnet   # {_('example_no_magnet', '分析女优视频但不获取磁力链接')}
  python run.py -w 5656 --no-image    # {_('example_no_image', '分析作者视频但不下载缩略图')}
  python run.py -l {target_lang}               # {_('example_lang', '使用英文界面')}
  python run.py -c                    # {_('example_config', '显示配置信息')}
  python run.py -e                    # {_('example_extract', '提取热门作者列表')}
  python run.py --clear-cache         # {_('example_clear_cache', '清除所有缓存数据')}


{_('advanced_usage', '高级用法')}:
  # {_('advanced_example1', '使用20个线程分析作者视频，生成Jellyfin元数据，并使用英文界面')}
  python run.py -w 5656 -t 20 --jellyfin -l en
  
  # {_('advanced_example2', '批量分析多个作者，使用最大50个线程，不下载缩略图但获取磁力链接，并生成Jellyfin元数据')}
  python run.py -b 5656,3524,4461,7890,6543,2109 -t 50 --no-image --jellyfin
"""
    print(usage)


def show_config_info():
    """显示当前配置信息"""
    print(f"=== {_('config.config_info_title', '当前配置信息')} ===")
    print(f"{_('config.config_data_dir', '数据目录')}: {config.cache_dir}")
    print(f"{_('config.config_max_workers', '最大线程数')}: {config.max_workers}")
    print(f"{_('config.config_max_retries', '最大重试次数')}: {config.max_retries}")
    print(f"{_('config.config_cache_ttl', '缓存有效期')}: {config.cache_ttl/3600:.1f} {_('config.config_hours', '小时')}")
    print(f"{_('config.config_language', '当前语言')}: {get_current_language()}")

    # 显示检查站点配置
    show_check_sites()


def show_check_sites():
    """显示当前配置的检查站点"""
    check_sites = sorted(config.check_sites, key=lambda x: x["priority"])

    if not check_sites:
        print(f"⚠️ {_('sites_none', '未配置任何检查站点，将使用默认站点')}")
        return

    print(f"\n=== {_('sites_title', '视频检查站点 (按优先级排序)')} ===")
    for idx, site in enumerate(check_sites, 1):
        site_name = site.get("name", site["url"].split("/")[2])
        print(f"{idx}. {_('sites_name', '站点')}: {site_name}")
        print(f"   {_('sites_url', '网址模板')}: {site['url']}")
        print(f"   {_('sites_priority', '优先级')}: {site['priority']}")


def extract_writer_info():
    """提取热门作者列表

    从FC2PPVDB获取热门作者列表并保存到文件

    返回:
        bool: 操作是否成功
    """
    extractor = WriterExtractor()

    print(_("extract_writers.start", "开始获取热门作者列表..."))
    writer_data = extractor.extract_all_writers()
    if writer_data:
        print(f"✅ {_('extract_writers.success', '已获取 {count} 个热门作者信息').format(count=len(writer_data))}")
        return True
    else:
        print(f"❌ {_('extract_writers.failure', '无法获取热门作者列表')}")
        return False


def is_leaked(result):
    """
    判断视频是否已泄露
    
    参数:
        result: 视频结果对象
        
    返回:
        bool: 是否已泄露
    """
    # 如果leaked字段存在并且为True，直接返回True
    if result.get("leaked") is True:
        return True
    
    status = result.get("status")
    
    # 如果status是available，则视为已泄露
    if status == "available":
        return True
        
    # 如果status是布尔类型
    if isinstance(status, bool):
        return status
        
    # 如果status是字符串且为leaked、yes或true
    if isinstance(status, str) and status.lower() in ["leaked", "yes", "true"]:
        return True
        
    # 默认为未泄露
    return False


def check_videos(
    target_id, is_actress=False, threads=None, with_magnet=True, download_images=True, generate_jellyfin=False
):
    """通用视频分析函数

    获取指定ID的所有视频并检查其流出状态，同时获取磁力链接和缩略图

    参数:
        target_id: 作者ID或女优ID
        is_actress: 是否为女优ID
        threads: 并行线程数
        with_magnet: 是否获取磁力链接
        download_images: 是否下载缩略图
        generate_jellyfin: 是否生成Jellyfin元数据

    返回:
        bool: 操作是否成功
    """
    # 根据类型确定显示文本
    entity_type = _("check_videos.entity_type_actress", "女优") if is_actress else _("check_videos.entity_type_writer", "作者")

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
                print(f"✅ {_('check_videos.author_name_success', '{entity_type}名称: {name}').format(entity_type=entity_type, name=author_name)}")
        except ConnectionError as e:
            logger.error(f"获取{entity_type}名称时连接错误: {e}")
            print(f"⚠️ {_('check_videos.author_name_error_connection', '获取{entity_type}名称时连接错误: {error}').format(entity_type=entity_type, error=e)}")
            author_name = None
        except Timeout as e:
            logger.error(f"获取{entity_type}名称时连接超时: {e}")
            print(f"⚠️ {_('check_videos.author_name_error_timeout', '获取{entity_type}名称时连接超时: {error}').format(entity_type=entity_type, error=e)}")
            author_name = None
        except HTTPError as e:
            logger.error(f"获取{entity_type}名称时HTTP错误: {e.code} - {e.reason}")
            print(f"⚠️ {_('check_videos.author_name_error_http', '获取{entity_type}名称时HTTP错误: {code} - {reason}').format(entity_type=entity_type, code=e.code, reason=e.reason)}")
            author_name = None

        # 获取视频列表
        try:
            videos = analyzer.fetch_video_ids()
            if not videos:
                logger.warning(f"未找到{entity_type} {target_id} 的视频")
                print(f"❌ {_('check_videos.videos_not_found', '未找到{entity_type} {id} 的视频').format(entity_type=entity_type, id=target_id)}")
                return False
        except ConnectionError as e:
            logger.error(f"获取视频列表时连接错误: {e}")
            print(f"❌ {_('check_videos.videos_error_connection', '获取视频列表时连接错误: {error}').format(error=e)}")
            return False
        except Timeout as e:
            logger.error(f"获取视频列表时连接超时: {e}")
            print(f"❌ {_('check_videos.videos_error_timeout', '获取视频列表时连接超时: {error}').format(error=e)}")
            return False
        except HTTPError as e:
            logger.error(f"获取视频列表时HTTP错误: {e.code} - {e.reason}")
            print(f"❌ {_('check_videos.videos_error_http', '获取视频列表时HTTP错误: {code} - {reason}').format(code=e.code, reason=e.reason)}")
            return False
        except JSONDecodeError as e:
            logger.error(f"解析视频数据时格式错误: {e}")
            print(f"❌ {_('check_videos.videos_error_json', '解析视频数据时格式错误: {error}').format(error=e)}")
            return False

        # 显示进度信息
        total_videos = len(videos)
        print(_("check_videos.videos_found", "总共找到 {count} 个视频，开始分析...").format(count=total_videos))

        # 分析视频时明确指定线程数和超时设置
        try:
            # 注意：analyze_videos方法不接受max_workers参数
            # 线程数由FC2Analyzer构造函数或内部配置控制
            results, stats = analyzer.analyze_videos(videos)
        except Exception as e:
            logger.error(f"分析视频时出错: {type(e).__name__}: {e}")
            print(f"❌ {_('check_videos.analyze_error', '分析视频时出错: {error}').format(error=e)}")
            return False

        # 保存分析结果
        try:
            analyzer.save_results()
        except Exception as e:
            logger.error(f"保存分析结果时出错: {type(e).__name__}: {e}")
            print(f"❌ 保存分析结果时出错: {e}")

        try:
            # 确保目录存在
            try:
                os.makedirs(config.result_dir, exist_ok=True)
            except PermissionError as e:
                logger.error(f"创建结果目录时权限不足: {e}")
                print(f"❌ {_('check_videos.dir_error_permission', '创建结果目录时权限不足: {error}').format(error=e)}")
                return False
            except OSError as e:
                logger.error(f"创建结果目录时系统错误: {e}")
                print(f"❌ {_('check_videos.dir_error_system', '创建结果目录时系统错误: {error}').format(error=e)}")
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
                print(f"⚠️ {_('check_videos.name_special_chars', '{entity_type}名称包含特殊字符或为空，仅使用ID作为文件名').format(entity_type=entity_type)}")
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

                print(f"✅ {_('check_videos.result_saved', '结果已保存到: {path}').format(path=save_path)}")
            except PermissionError as e:
                logger.error(f"写入结果文件时权限不足: {e}")
                print(f"❌ {_('check_videos.write_error_permission', '写入结果文件时权限不足: {error}').format(error=e)}")
            except IOError as e:
                logger.error(f"写入结果文件时I/O错误: {e}")
                print(f"❌ {_('check_videos.write_error_io', '写入结果文件时I/O错误: {error}').format(error=e)}")

            # 显示详细统计信息
            analyzer.display_results(results, stats)

            # 调用generate_reports方法生成分类报告
            try:
                reports = analyzer.generate_reports(target_id, results, author_name)
                if reports:
                    print(f"✅ {_('check_videos.report_success', '成功为{entity_type} {id} 生成 {count} 个分类报告').format(entity_type=entity_type, id=target_id, count=len(reports))}")
                    for report_type, report_path in reports.items():
                        print(f"  - {report_type}: {report_path}")
            except Exception as e:
                logger.error(f"生成分类报告时出错: {type(e).__name__}: {e}")
                print(f"⚠️ {_('check_videos.report_error', '生成分类报告时出错: {error}').format(error=e)}")

        except Exception as e:
            logger.error(f"保存结果时出错: {type(e).__name__}: {e}\n{traceback.format_exc()}")
            print(f"⚠️ 保存结果时出错: {e}")
            return False

        print(_("check_videos.total_videos", "总视频数: {count}").format(count=total))
        print(_("check_videos.leaked_videos", "已流出数: {count}").format(count=leaked))
        print(_("check_videos.leaked_ratio", "流出比例: {ratio}%").format(ratio=f"{leak_ratio:.2f}"))

        # 在函数结尾部分添加Jellyfin元数据生成代码
        if generate_jellyfin and results:
            try:
                print("\n=== Jellyfin元数据 ===")
                jellyfin_generator = JellyfinMetadataGenerator()
                
                # 从视频结果中提取已流出的视频
                leaked_videos = [v for v in results if v.get("status") in ["leaked", "available", "已流出"]]
                
                if not leaked_videos:
                    print("❌ 没有已流出的视频，跳过生成Jellyfin元数据")
                    return results
                
                # 创建作者信息字典
                author_info = {
                    "id": target_id,
                    "name": author_name
                }
                
                # 异步调用批量生成元数据
                import asyncio
                # 使用asyncio.run运行异步函数
                metadata_results = asyncio.run(jellyfin_generator.batch_generate_metadata(
                    leaked_videos,
                    author_info=author_info,
                    enrich_from_web=True  # 始终从网络获取额外信息，包括标签
                ))
                
                if metadata_results:
                    print(f"✅ 成功生成 {len(metadata_results)} 个Jellyfin元数据文件")
                else:
                    print("❌ 未生成任何Jellyfin元数据文件")
                
            except Exception as e:
                print(f"❌ 生成Jellyfin元数据时出错: {str(e)}")

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
    ids, is_actress=False, threads=None, with_magnet=True, download_images=True, generate_jellyfin=False
):
    """批量处理多个作者或女优

    依次分析多个ID的视频，并生成汇总报告

    参数:
        ids: ID列表或逗号分隔的字符串
        is_actress: 是否为女优ID
        threads: 并行线程数
        with_magnet: 是否获取磁力链接
        download_images: 是否下载缩略图
        generate_jellyfin: 是否生成Jellyfin元数据

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

    # 处理每个ID
    for idx, item_id in enumerate(id_list, 1):
        try:
            # 检查缓存是否存在且有效
            cache_file = os.path.join(
                config.cache_dir, f"{'actress' if is_actress else 'author'}_{item_id}.json"
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

                # 保存结果
                try:
                    analyzer.save_results()
                except Exception as e:
                    ui_manager.add_log(f"保存分析结果时出错: {e}", True)
                    logger.error(f"保存分析结果时出错: {type(e).__name__}: {e}")

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

    # 在函数末尾添加Jellyfin元数据生成逻辑
    if generate_jellyfin and processed_items:
        try:
            print("\n=== Jellyfin元数据 ===")
            jellyfin_generator = JellyfinMetadataGenerator()
            total_metadata_count = 0
            
            for item in processed_items:
                entity_id = item.get(id_field)
                videos_info = item.get("results", [])
                entity_name = item.get(name_field)
                
                if videos_info:
                    entity_info = {"id": entity_id, "name": entity_name} if entity_name else {"id": entity_id}
                    import asyncio
                    metadata_files = asyncio.run(jellyfin_generator.batch_generate_metadata(
                        videos_info,
                        author_info=entity_info if not is_actress else None,
                        actress_info=entity_info if is_actress else None
                    ))
                    total_metadata_count += len(metadata_files)
            
            if total_metadata_count > 0:
                print(f"✅ {_('jellyfin.metadata_generated_batch', '总共为 {count} 个视频生成Jellyfin元数据').format(count=total_metadata_count)}")
                print(f"📁 {_('jellyfin.metadata_location', '元数据保存位置: {path}').format(path=jellyfin_generator.output_dir)}")
            else:
                print(f"⚠️ {_('jellyfin.no_metadata_generated', '没有成功生成Jellyfin元数据')}")
        except Exception as e:
            logger.error(f"批量生成Jellyfin元数据时出错: {str(e)}")
            print(f"❌ {_('jellyfin.metadata_error_batch', '批量生成Jellyfin元数据时出错: {error}').format(error=str(e))}")

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
    video_id, threads=None, with_magnet=True, download_images=True, generate_jellyfin=False
):
    """通过视频ID查找并分析作者

    通过在FC2PPVDB上查询视频信息，获取作者信息并分析其所有作品

    Args:
        video_id: 视频ID
        threads: 并行线程数
        with_magnet: 是否获取磁力链接
        download_images: 是否下载缩略图
        generate_jellyfin: 是否生成Jellyfin元数据

    Returns:
        bool: 操作是否成功
    """
    print(_("find_writer.start", "开始通过视频ID {id} 查找作者信息...").format(id=video_id))

    try:
        # 设置请求超时
        timeout = config.timeout  # 从配置获取超时时间，默认15秒

        # 使用fc2_video_parser查找作者
        writer_id, writer_username = find_writer_by_video(video_id)

        if not writer_id:
            if writer_username:
                print(_("find_writer.found_username_no_id", "已找到作者用户名 {username}，但无法获取其ID").format(username=writer_username))
            else:
                print(_("find_writer.not_found", "无法通过视频ID {id} 找到作者信息").format(id=video_id))
            return False

        print(_("find_writer.found", "已找到作者: ID={id}, 用户名={username}").format(id=writer_id, username=writer_username))
        print(_("find_writer.analyze_start", "开始分析作者 {id} 的所有视频...").format(id=writer_id))

        # 使用找到的作者ID进行分析
        return check_videos(
            writer_id,
            is_actress=False,
            threads=threads,
            with_magnet=with_magnet,
            download_images=download_images,
            generate_jellyfin=generate_jellyfin
        )
    except ConnectionError as e:
        logger.error(f"查找作者时连接错误: {e}")
        print(_("find_writer.error_connection", "查找作者时连接错误: {error}").format(error=e))
        return False
    except Timeout as e:
        logger.error(f"查找作者时连接超时: {e}")
        print(_("find_writer.error_timeout", "查找作者时连接超时: {error}").format(error=e))
        return False
    except JSONDecodeError as e:
        logger.error(f"解析作者数据时格式错误: {e}")
        print(_("find_writer.error_json", "解析作者数据时格式错误: {error}").format(error=e))
        return False
    except ValueError as e:
        logger.error(f"查找作者参数错误: {e}")
        print(_("find_writer.error_value", "查找作者参数错误: {error}").format(error=e))
        return False
    except Exception as e:
        logger.error(f"查找作者时未知错误: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        print(_("find_writer.error_unknown", "查找作者时出错: {error}").format(error=f"{type(e).__name__}: {e}"))
        return False


def generate_jellyfin_only():
    """
    独立执行Jellyfin元数据生成，基于已有的缓存结果文件
    
    在没有指定-a/-w/-b/-ba/-v参数的情况下，但指定了--jellyfin参数时执行此函数
    查找最近48小时内的分析结果文件，询问用户是否基于该结果生成元数据
    
    Returns:
        bool: 成功返回True，失败返回False
    """
    try:
        # 获取当前时间
        now = datetime.now()
        # 计算48小时前的时间戳
        cache_threshold = now - timedelta(seconds=config.cache_ttl)
        
        # 查找results目录中的所有总报告文件
        report_files = glob.glob(os.path.join(config.result_dir, "*_总报告.txt"))
        
        # 如果没有找到任何报告文件
        if not report_files:
            print(f"❌ {_('jellyfin_only.no_reports', '未找到任何分析结果文件，请先使用-a/-w/-b/-ba/-v参数进行分析')}")
            return False
            
        # 按最后修改时间排序，最新的在前面
        report_files.sort(key=os.path.getmtime, reverse=True)
        
        # 查找48小时内的报告文件
        valid_reports = []
        for report_file in report_files:
            # 获取文件的最后修改时间
            file_mtime = datetime.fromtimestamp(os.path.getmtime(report_file))
            
            # 如果文件在48小时内修改过
            if file_mtime >= cache_threshold:
                # 文件名模式：id_name_总报告.txt
                filename = os.path.basename(report_file)
                
                # 提取entity_id和entity_name
                report_data = {'file_path': report_file, 'mtime': file_mtime}
                
                # 读取文件内容提取信息
                with open(report_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                    # 解析第一行获取类型和ID
                    if lines and len(lines) > 0:
                        first_line = lines[0].strip()
                        # 格式："作者ID: 1476" 或 "女优ID: 5711"
                        id_match = re.match(r'(作者|女优)ID: (\d+)', first_line)
                        if id_match:
                            report_data['entity_type'] = id_match.group(1)  # 作者 或 女优
                            report_data['entity_id'] = id_match.group(2)
                    
                    # 解析第二行获取名称
                    if len(lines) > 1:
                        second_line = lines[1].strip()
                        # 格式："作者名称: ぱすも" 或 "女优名称: みお 女優"
                        name_match = re.match(r'(作者|女优)名称: (.+?)(?:分析时间:|$)', second_line)
                        if name_match:
                            report_data['entity_name'] = name_match.group(2).strip()
                    
                    # 检查分析时间
                    time_match = None
                    for line in lines[:3]:  # 只检查前几行
                        if '分析时间:' in line:
                            time_match = re.search(r'分析时间: (\d{8}_\d{6})', line)
                            if time_match:
                                report_data['timestamp'] = time_match.group(1)
                                break
                
                # 如果成功提取到ID和类型，则添加到有效报告列表
                if 'entity_id' in report_data and 'entity_type' in report_data:
                    valid_reports.append(report_data)
        
        # 如果没有找到任何有效的报告文件
        if not valid_reports:
            print(f"❌ {_('jellyfin_only.no_recent_reports', '未找到48小时内的分析结果文件，请先使用-a/-w/-b/-ba/-v参数进行分析')}")
            return False
        
        # 显示找到的报告文件列表
        print(f"\n{_('jellyfin_only.found_reports', '找到以下{count}个48小时内的分析结果:').format(count=len(valid_reports))}")
        for i, report in enumerate(valid_reports, 1):
            entity_type = _('analyzer.entity_type_actress', '女优') if report['entity_type'] == '女优' else _('analyzer.entity_type_writer', '作者')
            entity_id = report['entity_id']
            entity_name = report.get('entity_name', _('jellyfin_only.unknown_name', '未知'))
            file_time = report['mtime'].strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"{i}. {entity_type}ID: {entity_id}, {_('jellyfin_only.entity_name', '名称')}: {entity_name}, {_('jellyfin_only.analysis_time', '分析时间')}: {file_time}")
        
        # 询问用户选择使用哪个报告文件
        choice = input(f"\n{_('jellyfin_only.select_report', '请输入要使用的报告序号(直接回车取消)')}: ")
        if not choice.strip():
            print(_('jellyfin_only.operation_cancelled', '已取消操作'))
            return False
        
        try:
            choice_idx = int(choice) - 1
            if choice_idx < 0 or choice_idx >= len(valid_reports):
                print(f"❌ {_('jellyfin_only.invalid_number', '无效的序号')}")
                return False
                
            selected_report = valid_reports[choice_idx]
            entity_type_display = _('analyzer.entity_type_actress', '女优') if selected_report['entity_type'] == '女优' else _('analyzer.entity_type_writer', '作者')
            print(f"\n{_('jellyfin_only.selected_report', '已选择')}: {entity_type_display}ID: {selected_report['entity_id']}, {_('jellyfin_only.entity_name', '名称')}: {selected_report.get('entity_name', _('jellyfin_only.unknown_name', '未知'))}")
            
            # 询问用户是否确认
            confirm = input(f"{_('jellyfin_only.confirm_selection', '是否确认使用此报告生成Jellyfin元数据? (y/n)')}: ")
            if confirm.lower() != 'y':
                print(_('jellyfin_only.operation_cancelled', '已取消操作'))
                return False
            
            # 根据类型确定是作者还是女优
            is_actress = selected_report['entity_type'] == '女优'
            entity_id = selected_report['entity_id']
            entity_name = selected_report.get('entity_name', '')
            
            # 创建实体信息对象
            entity_info = {
                "id": entity_id,
                "name": entity_name
            }
            
            # 尝试读取缓存数据
            cache_file = os.path.join(
                config.cache_dir, f"{'actress' if is_actress else 'author'}_{entity_id}.json"
            )
            
            videos_info = []
            used_cache = False
            
            # 如果缓存文件存在
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cache_data = json.load(f)
                    
                    # 检查缓存有效期
                    cache_time = datetime.strptime(cache_data["timestamp"], "%Y-%m-%d %H:%M:%S")
                    cache_age = (datetime.now() - cache_time).total_seconds()
                    
                    if cache_age < config.cache_ttl:
                        videos_info = cache_data.get("results", [])
                        
                        # 检查缓存中的视频信息是否有效
                        if videos_info and isinstance(videos_info, list) and all("video_id" in v for v in videos_info):
                            print(f"🔄 {_('jellyfin_only.using_cache', '使用缓存数据')}")
                            used_cache = True
                        else:
                            print(f"⚠️ {_('jellyfin_only.invalid_cache', '缓存数据无效或不完整')}")
                            videos_info = []
                    else:
                        print(f"⚠️ {_('jellyfin_only.cache_expired', '缓存数据已过期')}")
                except Exception as e:
                    logger.error(f"读取缓存出错: {e}")
                    print(f"⚠️ {_('jellyfin_only.cache_error', '读取缓存出错')}: {e}")
                    videos_info = []
            
            # 如果没有从缓存获取到有效的视频信息，则从报告文件解析
            if not videos_info:
                print(f"🔍 {_('jellyfin_only.parsing_report', '从报告文件解析视频信息...')}")
                
                # 读取报告文件并解析已流出视频列表
                try:
                    with open(selected_report['file_path'], 'r', encoding='utf-8') as f:
                        report_content = f.read()
                    
                    # 查找已流出视频列表部分
                    leaked_section_match = re.search(r'===\s*已流出视频列表\s*===\s*(.*?)(?:===\s*未流出视频列表\s*===|\Z)', report_content, re.DOTALL)
                    
                    if leaked_section_match:
                        leaked_section = leaked_section_match.group(1).strip()
                        
                        # 尝试不同的正则表达式匹配视频条目
                        video_entries = re.findall(r'(\d+).\s*\[(\d+)\].*?(\[有磁链\]|\[无磁链\])?\s*(.*?)(?=\d+\.\s*\[|\Z)', leaked_section, re.DOTALL)
                        
                        # 如果上面的正则表达式没有匹配到，尝试另一种格式
                        if not video_entries:
                            video_entries = re.findall(r'(\d+).\s*\[(\d+)\](.*)', leaked_section.split('\n'))
                            
                        # 处理匹配到的视频条目
                        for entry in video_entries:
                            if len(entry) == 4:  # 第一种正则表达式
                                video_id = entry[1]
                                title_part = entry[3]
                            elif len(entry) == 3:  # 第二种正则表达式
                                video_id = entry[1]
                                title_part = entry[2]
                            else:
                                continue
                                
                            # 提取视频标题 (移除前面的[有磁链]/[无磁链]部分)
                            title_match = re.search(r'(?:\[有磁链\]|\[无磁链\])?\s*(.*)', title_part)
                            title = title_match.group(1).strip() if title_match else f"FC2-PPV-{video_id}"
                            
                            # 创建视频信息对象
                            video_info = {
                                "video_id": video_id,
                                "title": title,
                                "status": "available",
                                "leaked": True
                            }
                            
                            videos_info.append(video_info)
                except Exception as e:
                    logger.error(f"解析报告文件出错: {e}")
                    print(f"❌ {_('jellyfin_only.parse_error', '解析报告文件出错')}: {e}")
                    traceback.print_exc()  # 打印完整的错误堆栈跟踪
                    
                    # 如果报告文件解析失败，尝试读取已流出视频总表文件
                    try:
                        leaked_summary_file = selected_report['file_path'].replace('_总报告.txt', '_已流出视频总表.txt')
                        
                        if os.path.exists(leaked_summary_file):
                            print(f"🔍 {_('jellyfin_only.parsing_summary', '尝试从已流出视频总表文件解析...')}")
                            
                            with open(leaked_summary_file, 'r', encoding='utf-8') as f:
                                lines = f.readlines()
                                
                                for line in lines:
                                    # 格式: FC2-PPV-1234567 | 视频标题
                                    match = re.match(r'FC2-PPV-(\d+) \| (.+)', line.strip())
                                    if match:
                                        video_id = match.group(1)
                                        title = match.group(2)
                                        
                                        video_info = {
                                            "video_id": video_id,
                                            "title": title,
                                            "status": "available",
                                            "leaked": True
                                        }
                                        
                                        videos_info.append(video_info)
                        else:
                            print(f"❌ {_('jellyfin_only.summary_not_found', '未找到已流出视频总表文件')}")
                    except Exception as e2:
                        logger.error(f"解析已流出视频总表文件出错: {e2}")
                        print(f"❌ {_('jellyfin_only.summary_parse_error', '解析已流出视频总表文件出错')}: {e2}")
            
            # 检查是否有视频信息
            if not videos_info:
                print(f"❌ {_('jellyfin_only.no_videos_found', '未找到任何视频信息')}")
                return False
            
            # 筛选已流出的视频
            leaked_videos = [v for v in videos_info if v.get("status") == "available" or v.get("leaked") == True]
            
            if not leaked_videos:
                print(f"❌ {_('jellyfin.no_leaked_videos', '没有已流出的视频，跳过生成Jellyfin元数据')}")
                return False
            
            print(f"✅ {_('jellyfin_only.found_videos', '找到 {count} 个视频，其中 {leaked} 个已流出').format(count=len(videos_info), leaked=len(leaked_videos))}")
            
            # 生成Jellyfin元数据
            print(f"\n=== {_('jellyfin_only.jellyfin_metadata', 'Jellyfin元数据')} ===")
            jellyfin_generator = JellyfinMetadataGenerator()
            
            # 使用asyncio运行异步方法
            import asyncio
            metadata_results = asyncio.run(jellyfin_generator.batch_generate_metadata(
                leaked_videos,
                author_info=entity_info if not is_actress else None,
                actress_info=entity_info if is_actress else None,
                enrich_from_web=True  # 始终从网络获取额外信息，包括标签
            ))
            
            if metadata_results:
                print(f"✅ {_('jellyfin_only.generation_success', '成功生成 {count} 个Jellyfin元数据文件').format(count=len(metadata_results))}")
                print(f"📁 {_('jellyfin.metadata_location', '元数据保存位置: {path}').format(path=jellyfin_generator.output_dir)}")
                return True
            else:
                print(f"❌ {_('jellyfin_only.generation_failed', '未生成任何Jellyfin元数据文件')}")
                return False
                
        except ValueError:
            print(f"❌ {_('jellyfin_only.invalid_input', '无效的输入')}")
            return False
            
    except Exception as e:
        logger.error(f"生成Jellyfin元数据时出错: {str(e)}\n{traceback.format_exc()}")
        print(f"❌ {_('jellyfin_only.error', '生成Jellyfin元数据时出错')}: {str(e)}")
        return False


def main():
    """程序主入口"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description=_("app_description", "FC2流出检测器"), add_help=False)
    parser.add_argument("-h", "--help", action="store_true", help=_("usage_help", "显示帮助信息"))
    parser.add_argument("-w", "--writer", type=str, help=_("usage_writer", "分析作者ID的视频"))
    parser.add_argument("-a", "--actress", type=str, help=_("usage_actress", "分析女优ID的视频"))
    parser.add_argument("-b", "--batch", type=str, help=_("usage_batch", "批量处理多个作者ID（用英文逗号分隔）"))
    parser.add_argument("-ba", "--batch-actress", type=str, help=_("usage_batch_actress", "批量处理多个女优ID（用英文逗号分隔）"))
    parser.add_argument("-v", "--video", type=str, help=_("usage_video", "通过视频ID查找并分析作者"))
    parser.add_argument("-t", "--threads", type=int, help=_("usage_threads", "指定并行线程数"))
    parser.add_argument("--jellyfin", action="store_true", help=_("usage_jellyfin", "生成Jellyfin兼容的元数据；可单独使用，会查找48小时内的分析结果"))
    parser.add_argument("--no-magnet", action="store_true", help=_("usage_no_magnet", "不获取磁力链接"))
    parser.add_argument("--no-image", action="store_true", help=_("usage_no_image", "不下载视频缩略图"))
    parser.add_argument("-l", "--lang", type=str, help=_("usage_lang", "设置界面语言 (支持: zh, en, ja)"))
    parser.add_argument("-c", "--config", action="store_true", help=_("usage_config", "显示配置信息"))
    parser.add_argument("-s", "--sites", action="store_true", help=_("usage_sites", "显示检查站点列表"))
    parser.add_argument("-e", "--extract", action="store_true", help=_("usage_extract", "提取热门作者列表"))
    parser.add_argument("--clear-cache", action="store_true", help=_("usage_clear_cache", "清除所有缓存数据"))

    try:
        args = parser.parse_args()

        # 显示帮助信息
        if args.help:
            print_usage()
            return 0

        # 设置语言
        if args.lang:
            if args.lang in SUPPORTED_LANGUAGES:
                switch_language(args.lang)
                print(f"🌐 {_('main.language_switched', '已切换语言为: {lang}').format(lang=args.lang)}")
            else:
                print(f"❌ {_('main.unsupported_language', '不支持的语言: {lang}').format(lang=args.lang)}")
                return 1

        # 显示配置信息
        if args.config:
            display_config()
            return 0

        # 显示检查站点列表
        if args.sites:
            display_sites()
            return 0

        # 清除缓存
        if args.clear_cache:
            clear_cache()
            return 0

        # 设置线程数
        threads = args.threads if args.threads else config.max_workers

        # 提取热门作者列表
        if args.extract:
            success = extract_writer_info()
            return 0 if success else 1

        # 设置磁链和图片下载选项
        with_magnet = not args.no_magnet
        download_images = not args.no_image
        generate_jellyfin = args.jellyfin

        # 通过视频ID查找并分析作者
        if args.video:
            success = find_writer_by_video_id(
                args.video, threads, with_magnet, download_images, generate_jellyfin
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
                generate_jellyfin=generate_jellyfin
            )
        elif args.actress:
            check_videos(
                args.actress,
                is_actress=True,
                threads=threads,
                with_magnet=with_magnet,
                download_images=download_images,
                generate_jellyfin=generate_jellyfin
            )
        elif args.batch:
            process_multiple_ids(
                args.batch,
                is_actress=False,
                threads=threads,
                with_magnet=with_magnet,
                download_images=download_images,
                generate_jellyfin=generate_jellyfin
            )
        elif args.batch_actress:
            process_multiple_ids(
                args.batch_actress,
                is_actress=True,
                threads=threads,
                with_magnet=with_magnet,
                download_images=download_images,
                generate_jellyfin=generate_jellyfin
            )
        # 添加只有--jellyfin参数的情况
        elif generate_jellyfin:
            # 直接调用独立的Jellyfin元数据生成函数
            generate_jellyfin_only()
        else:
            print_usage()

        return 0

    except KeyboardInterrupt:
        print("\n🛑 用户中断了操作")
        return 130  # 标准Unix中断退出码
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}\n{traceback.format_exc()}")
        print(f"❌ 程序执行出错: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
