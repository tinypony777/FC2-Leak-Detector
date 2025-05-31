"""
Jellyfin元数据生成器 - 将FC2视频分析结果转换为Jellyfin兼容的元数据格式

提供对分析结果的处理，生成Jellyfin可识别的NFO元数据文件和图像文件，
以便在Jellyfin媒体服务器中正确显示FC2视频信息。
"""

import os
import shutil
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
import re
import asyncio
import aiohttp
import time
import random
from bs4 import BeautifulSoup
from datetime import datetime

from config import config, BASE_CACHE_DIR
from src.utils.logger import get_logger
from src.utils.i18n import get_text as _

# 获取日志记录器
logger = get_logger("jellyfin_metadata")

class JellyfinMetadataGenerator:
    """将FC2视频信息转换为Jellyfin元数据格式"""
    
    def __init__(self, output_dir=None):
        """初始化元数据生成器
        
        Args:
            output_dir: 元数据输出目录，默认为data/jellyfin
        """
        self.output_dir = output_dir or os.path.join(BASE_CACHE_DIR, "jellyfin")
        os.makedirs(self.output_dir, exist_ok=True)
        
        logger.info(_("jellyfin.initialize").format(path=self.output_dir))
        
        # FC2PPVDB 网站的基础URL
        self.fc2ppvdb_base_url = "https://fc2ppvdb.com/articles"
        
        # 设置重试和退避机制参数
        self.max_retries = config.max_retries
        self.base_timeout = config.timeout
        self.min_wait_time = 5.0  # 最小等待时间（秒）
        self.max_wait_time = 30.0  # 最大等待时间（秒）

    async def fetch_page(self, url):
        """获取页面HTML内容，带重试和退避机制
        
        Args:
            url: 网页URL
            
        Returns:
            str: 页面HTML内容，失败返回None
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        
        for attempt in range(1, self.max_retries + 1):
            try:
                timeout = self.base_timeout * (1 + (attempt - 1) * 0.5)  # 递增超时时间
                
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(url, timeout=timeout) as response:
                        if response.status == 200:
                            return await response.text()
                        
                        # 处理常见错误状态码
                        if response.status == 429 or response.status >= 500:
                            # 服务器限流或服务器错误，使用指数退避
                            wait_time = min(self.max_wait_time, self.min_wait_time * (2 ** (attempt - 1)))
                            # 添加随机抖动以避免请求同步
                            wait_time = wait_time * (0.5 + random.random())
                            
                            logger.warning(_("logger.rate_limit").format(
                                status_code=response.status,
                                wait_time=wait_time
                            ))
                            
                            await asyncio.sleep(wait_time)
                            continue
                            
                        logger.warning(_("jellyfin.page_fetch_failed").format(status_code=response.status, url=url))
                        return None
                        
            except asyncio.TimeoutError:
                wait_time = min(self.max_wait_time, self.min_wait_time * (2 ** (attempt - 1)))
                logger.warning(f"请求超时，等待 {wait_time:.2f} 秒后重试 ({attempt}/{self.max_retries})")
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                wait_time = min(self.max_wait_time, self.min_wait_time * (2 ** (attempt - 1)))
                logger.error(f"获取页面异常: {str(e)}, URL: {url}")
                logger.warning(f"等待 {wait_time:.2f} 秒后重试 ({attempt}/{self.max_retries})")
                await asyncio.sleep(wait_time)
                
        logger.error(f"达到最大重试次数 ({self.max_retries})，获取页面失败: {url}")
        return None

    def parse_html(self, html_content, fc2_id):
        """解析HTML内容提取视频信息
        
        Args:
            html_content: HTML内容
            fc2_id: FC2视频ID
            
        Returns:
            dict: 解析得到的视频信息
        """
        if not html_content:
            return {}
            
        results = {}
        results['fc2_id'] = fc2_id
        
        # 提取标签 - 改进版本，更灵活的正则表达式匹配
        tags = []
        # 方法1：使用正则表达式
        tag_section_pattern = re.compile(r'<div[^>]*>(?:<ruby>)?タグ(?:<rt[^>]*>[^<]*</rt></ruby>)?[^:：]*[:：]\s*<span[^>]*>(.*?)</span>(?:</div>)?', re.DOTALL)
        tag_section_match = tag_section_pattern.search(html_content)
        if tag_section_match:
            tags_content = tag_section_match.group(1)
            tag_link_pattern = re.compile(r'<a[^>]*href="/tags/\?name=([^"&]+)[^"]*"[^>]*>([^<]+)</a>')
            tag_matches = tag_link_pattern.finditer(tags_content)
            for tag_match in tag_matches:
                tag_name = tag_match.group(2)
                tags.append(tag_name)
        
        # 方法2：如果正则表达式失败，尝试使用BeautifulSoup（作为备选方案）
        if not tags:
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                # 查找包含"タグ"的div
                for div in soup.find_all('div'):
                    if 'タグ' in div.text:
                        # 只查找href包含"/tags/?name="的链接
                        tag_links = [a for a in div.find_all('a') if 'href' in a.attrs and '/tags/' in a['href']]
                        for tag_link in tag_links:
                            tag_name = tag_link.text.strip()
                            if tag_name and tag_name not in tags:
                                tags.append(tag_name)
                        
                        # 如果找到了标签所在的div，就跳出循环
                        if tags:
                            break
            except Exception as e:
                logger.error(f"使用BeautifulSoup解析标签失败: {str(e)}")
        
        results['tags'] = tags
        
        # 提取马赛克状态
        mosaic_pattern = re.compile(r'<ruby>モザイク<rt[^>]*>[^<]*</rt></ruby>：<span[^>]*>([^<]+)</span>')
        mosaic_match = mosaic_pattern.search(html_content)
        if mosaic_match:
            results['mosaic_type'] = mosaic_match.group(1)
        
        # 提取发售日
        release_date_pattern = re.compile(r'販売日：<span[^>]*>([^<]+)</span>')
        release_date_match = release_date_pattern.search(html_content)
        if release_date_match:
            results['release_date'] = release_date_match.group(1)
        
        # 提取视频长度
        duration_pattern = re.compile(r'収録時間：<span[^>]*>([^<]+)</span>')
        duration_match = duration_pattern.search(html_content)
        if duration_match:
            results['duration'] = duration_match.group(1)
            
        # 获取标题
        title_pattern = re.compile(r'<h2[^>]*>.*?<a[^>]*>([^<]+)</a>', re.DOTALL)
        title_match = title_pattern.search(html_content)
        if title_match:
            results['title'] = title_match.group(1)
        
        return results

    async def enrich_video_info(self, video_info):
        """从FC2PPVDB获取额外的视频信息
        
        Args:
            video_info: 原始视频信息字典
            
        Returns:
            dict: 增强后的视频信息
        """
        video_id = video_info.get("video_id")
        if not video_id:
            logger.warning("无法获取额外信息：视频ID不存在")
            return video_info
            
        logger.info(_("jellyfin.fetch_extra_info").format(video_id=video_id))
        
        # 构造FC2PPVDB URL
        url = f"{self.fc2ppvdb_base_url}/{video_id}"
        
        # 获取页面内容
        html_content = await self.fetch_page(url)
        if not html_content:
            logger.warning(_("jellyfin.fetch_failed").format(url=url))
            return video_info
            
        # 解析页面内容
        extra_info = self.parse_html(html_content, video_id)
        if not extra_info:
            logger.warning(f"无法从FC2PPVDB页面解析额外信息: {url}")
            return video_info
            
        # 合并信息，优先使用原始信息
        enriched_info = {**extra_info, **video_info}
        
        # 标签特殊处理：合并标签
        if extra_info.get("tags") and video_info.get("tags"):
            all_tags = set(video_info["tags"]) | set(extra_info["tags"])
            enriched_info["tags"] = list(all_tags)
        
        logger.info(_("jellyfin.fetch_success").format(video_id=video_id))
        return enriched_info

    def is_leaked(self, video_info):
        """判断视频是否已泄露
        
        Args:
            video_info: 视频信息字典
                
        Returns:
            bool: 是否已泄露
        """
        # 如果leaked字段存在并且为True，直接返回True
        if video_info.get("leaked") is True:
            return True
        
        status = video_info.get("status")
        
        # 如果status是available或leaked，视为已泄露
        if status in ["available", "leaked", "已流出"]:
            return True
            
        # 如果status是布尔类型
        if isinstance(status, bool):
            return status
        
        # 默认为未泄露
        return False
    
    async def generate_metadata(self, video_info, image_path=None, author_info=None, actress_info=None, enrich_from_web=True):
        """为单个视频生成Jellyfin元数据
        
        Args:
            video_info: 视频信息字典
            image_path: 封面图片路径
            author_info: 作者信息字典
            actress_info: 女优信息字典
            enrich_from_web: 是否从网络获取额外信息
                
        Returns:
            str: 生成的NFO文件路径
        """
        # 确保视频ID存在
        if "video_id" not in video_info:
            logger.error("无法生成元数据：视频ID不存在")
            return None
        
        video_id = video_info.get("video_id")
        logger.info(_("jellyfin.generate_start").format(video_id=video_id))
        
        # 从网络获取额外信息
        if enrich_from_web:
            video_info = await self.enrich_video_info(video_info)
        
        # 创建XML根元素
        root = ET.Element("movie")
        
        # 添加基本信息
        title = video_info.get("title", f"FC2-PPV-{video_id}")
        ET.SubElement(root, "title").text = title
        ET.SubElement(root, "originaltitle").text = f"FC2-PPV-{video_id}"
        ET.SubElement(root, "sorttitle").text = f"FC2-PPV-{video_id}"
        
        # 添加视频ID作为uniqueid
        uniqueid = ET.SubElement(root, "uniqueid", type="fc2ppv")
        uniqueid.text = video_id
        
        # 添加发布日期
        release_date = video_info.get("release_date") or video_info.get("publish_date")
        if release_date:
            ET.SubElement(root, "premiered").text = release_date
            ET.SubElement(root, "releasedate").text = release_date
            
            # 提取年份
            try:
                year = release_date.split("-")[0]
                ET.SubElement(root, "year").text = year
            except (IndexError, AttributeError):
                pass
        
        # 添加运行时间
        if "duration" in video_info:
            # 尝试将时长转换为分钟数
            try:
                duration_str = video_info["duration"]
                if "分" in duration_str:
                    minutes = int(re.search(r'(\d+)分', duration_str).group(1))
                    ET.SubElement(root, "runtime").text = str(minutes)
            except (AttributeError, ValueError):
                pass
            
        # 添加是否流出的信息到情节介绍
        plot_text = ""
            
        # 添加其他视频信息到情节介绍
        if "description" in video_info and video_info["description"]:
            plot_text += f"{video_info['description']}"
            
        # 添加马赛克类型
        if "mosaic_type" in video_info:
            plot_text += f"\n马赛克类型: {video_info['mosaic_type']}"
            
        # 如果有磁力链接，添加到情节介绍
        magnets = video_info.get("magnets", []) or ([video_info.get("magnet")] if video_info.get("magnet") else [])
        if magnets:
            plot_text += "\n\n" + _("jellyfin.magnet_links").format() + "\n"
            for idx, magnet in enumerate(magnets, 1):
                if magnet:
                    plot_text += f"{idx}. {magnet}\n"
                    
        # 添加情节介绍
        ET.SubElement(root, "plot").text = plot_text.strip()
        ET.SubElement(root, "outline").text = title
        
        # 添加制作公司/作者信息
        if author_info and "name" in author_info:
            ET.SubElement(root, "studio").text = author_info["name"]
        elif "author_name" in video_info:
            ET.SubElement(root, "studio").text = video_info["author_name"]
            
        # 添加导演信息(使用作者名称)
        director = ET.SubElement(root, "director")
        if author_info and "name" in author_info:
            director.text = author_info["name"]
        elif "author_name" in video_info:
            director.text = video_info["author_name"]
        else:
            director.text = "Unknown"
        
        # 添加演员信息
        if actress_info and "name" in actress_info:
            actor = ET.SubElement(root, "actor")
            ET.SubElement(actor, "name").text = actress_info["name"]
        elif "actress_name" in video_info:
            actor = ET.SubElement(root, "actor")
            ET.SubElement(actor, "name").text = video_info["actress_name"]
        
        # 添加标签/分类
        ET.SubElement(root, "genre").text = "FC2"
        
        # 添加马赛克类型作为标签
        if "mosaic_type" in video_info:
            ET.SubElement(root, "genre").text = video_info["mosaic_type"]
            
        # 添加其他标签
        if video_info.get("tags"):
            for tag in video_info["tags"]:
                ET.SubElement(root, "genre").text = tag
                
        # 添加特殊标签
        ET.SubElement(root, "tag").text = "FC2"
        
        # 保存为美观格式的XML
        xml_str = minidom.parseString(ET.tostring(root, encoding='unicode')).toprettyxml(indent="  ")
        
        # 定义输出文件名，简化为只用视频ID
        output_filename = f"FC2-PPV-{video_id}"
        
        # 保存NFO文件
        nfo_path = os.path.join(self.output_dir, f"{output_filename}.nfo")
        try:
            with open(nfo_path, "w", encoding="utf-8") as f:
                f.write(xml_str)
            logger.info(_("jellyfin.save_metadata_success").format(path=nfo_path))
        except Exception as e:
            logger.error(_("jellyfin.save_metadata_failed").format(error=str(e)))
            return None
        
        # 处理图片
        poster_path = None
        if image_path and os.path.exists(image_path):
            try:
                # 获取图片扩展名
                image_ext = os.path.splitext(image_path)[1]
                if not image_ext:
                    image_ext = ".jpg"  # 默认使用jpg扩展名
                    
                # 设置目标路径，使用Jellyfin标准的-poster后缀
                poster_path = os.path.join(self.output_dir, f"{output_filename}-poster{image_ext}")
                
                # 复制图片
                shutil.copy(image_path, poster_path)
                logger.info(_("jellyfin.copy_poster_success").format(path=poster_path))
            except Exception as e:
                logger.error(_("jellyfin.copy_poster_failed").format(error=str(e)))
                poster_path = None
                
        return {
            "nfo_path": nfo_path,
            "poster_path": poster_path,
            "video_id": video_id
        }
    
    def find_image_path(self, video_id, video_info, author_info=None, actress_info=None):
        """查找视频的图片路径
        
        Args:
            video_id: 视频ID
            video_info: 视频信息字典
            author_info: 作者信息字典
            actress_info: 女优信息字典
                
        Returns:
            str: 图片路径，如果找不到则返回None
        """
        # 尝试不同的图片路径模式
        possible_paths = []
        
        # 1. 直接在img目录下查找
        possible_paths.append(os.path.join(config.image_dir, f"{video_id}.jpg"))
        possible_paths.append(os.path.join(config.image_dir, f"FC2-PPV-{video_id}.jpg"))
        
        # 2. 作者目录下查找
        if author_info and "id" in author_info:
            author_id = author_info["id"]
            author_name = author_info.get("name", "")
            
            if author_name:
                # 清理作者名称以用于路径
                author_name = self._clean_filename(author_name)
                
                # 形如: author_{id}_{name}
                author_dir = os.path.join(config.image_dir, f"author_{author_id}_{author_name}")
                possible_paths.append(os.path.join(author_dir, f"{video_id}.jpg"))
                
                # 形如: author_{id}_{name}/leaked/{id}.jpg
                possible_paths.append(os.path.join(author_dir, "leaked", f"{video_id}.jpg"))
                possible_paths.append(os.path.join(author_dir, "unleaked", f"{video_id}.jpg"))
            else:
                # 只有ID的情况
                author_dir = os.path.join(config.image_dir, f"author_{author_id}")
                possible_paths.append(os.path.join(author_dir, f"{video_id}.jpg"))
                possible_paths.append(os.path.join(author_dir, "leaked", f"{video_id}.jpg"))
                possible_paths.append(os.path.join(author_dir, "unleaked", f"{video_id}.jpg"))
        
        # 3. 女优目录下查找
        if actress_info and "id" in actress_info:
            actress_id = actress_info["id"]
            actress_name = actress_info.get("name", "")
            
            if actress_name:
                # 清理女优名称以用于路径
                actress_name = self._clean_filename(actress_name)
                
                # 形如: actress_{id}_{name}
                actress_dir = os.path.join(config.image_dir, f"actress_{actress_id}_{actress_name}")
                possible_paths.append(os.path.join(actress_dir, f"{video_id}.jpg"))
                
                # 形如: actress_{id}_{name}/leaked/{id}.jpg
                possible_paths.append(os.path.join(actress_dir, "leaked", f"{video_id}.jpg"))
                possible_paths.append(os.path.join(actress_dir, "unleaked", f"{video_id}.jpg"))
                
                # 特殊形式: actress_{id}_Actress_{id}
                actress_dir_special = os.path.join(config.image_dir, f"actress_{actress_id}_Actress_{actress_id}")
                possible_paths.append(os.path.join(actress_dir_special, f"{video_id}.jpg"))
                possible_paths.append(os.path.join(actress_dir_special, "leaked", f"{video_id}.jpg"))
                possible_paths.append(os.path.join(actress_dir_special, "unleaked", f"{video_id}.jpg"))
                
                # 特殊形式: 包含女优原始名称（可能包含空格）
                # 尝试直接搜索actress_{id}_*目录
                actress_dir_pattern = os.path.join(config.image_dir, f"actress_{actress_id}_*")
                try:
                    import glob
                    matched_dirs = glob.glob(actress_dir_pattern)
                    for matched_dir in matched_dirs:
                        if os.path.isdir(matched_dir):
                            # 添加主目录下图片路径
                            possible_paths.append(os.path.join(matched_dir, f"{video_id}.jpg"))
                            # 添加leaked目录下图片路径
                            possible_paths.append(os.path.join(matched_dir, "leaked", f"{video_id}.jpg"))
                            # 添加unleaked目录下图片路径
                            possible_paths.append(os.path.join(matched_dir, "unleaked", f"{video_id}.jpg"))
                except Exception as e:
                    logger.error(f"搜索女优目录模式时出错: {str(e)}")
            else:
                # 只有ID的情况
                actress_dir = os.path.join(config.image_dir, f"actress_{actress_id}")
                possible_paths.append(os.path.join(actress_dir, f"{video_id}.jpg"))
                possible_paths.append(os.path.join(actress_dir, "leaked", f"{video_id}.jpg"))
                possible_paths.append(os.path.join(actress_dir, "unleaked", f"{video_id}.jpg"))
                
                # 尝试通配符匹配所有可能的actress_{id}_*目录
                try:
                    import glob
                    actress_dir_pattern = os.path.join(config.image_dir, f"actress_{actress_id}_*")
                    matched_dirs = glob.glob(actress_dir_pattern)
                    for matched_dir in matched_dirs:
                        if os.path.isdir(matched_dir):
                            possible_paths.append(os.path.join(matched_dir, f"{video_id}.jpg"))
                            possible_paths.append(os.path.join(matched_dir, "leaked", f"{video_id}.jpg"))
                            possible_paths.append(os.path.join(matched_dir, "unleaked", f"{video_id}.jpg"))
                except Exception as e:
                    logger.error(f"搜索女优目录模式时出错: {str(e)}")
        
        # 4. 尝试在data/img下查找任何可能包含该视频ID的图片
        try:
            import glob
            video_pattern = os.path.join(config.image_dir, "**", f"{video_id}.jpg")
            matched_files = glob.glob(video_pattern, recursive=True)
            for matched_file in matched_files:
                if os.path.isfile(matched_file):
                    possible_paths.append(matched_file)
        except Exception as e:
            logger.error(f"递归搜索图片文件时出错: {str(e)}")
        
        # 检查所有可能的路径
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(_("jellyfin.found_image").format(video_id=video_id, path=path))
                return path
        
        # 如果没有找到图片，记录警告
        logger.warning(f"未找到视频 FC2-PPV-{video_id} 的图片")
        return None
    
    async def batch_generate_metadata(self, videos_info, author_info=None, actress_info=None, enrich_from_web=True):
        """批量生成多个视频的元数据
        
        Args:
            videos_info: 视频信息列表
            author_info: 作者信息字典
            actress_info: 女优信息字典
            enrich_from_web: 是否从网络获取额外信息
                
        Returns:
            list: 生成的元数据文件信息列表
        """
        if not videos_info:
            logger.warning("没有视频信息可用于生成元数据")
            return []
        
        # 过滤出已流出的视频
        leaked_videos = [video for video in videos_info if self.is_leaked(video)]
        
        # 如果没有已流出的视频，直接返回
        if not leaked_videos:
            logger.info(_("jellyfin.no_leaked_videos"))
            return []
            
        logger.info(_("jellyfin.start_batch").format(count=len(leaked_videos)))
        results = []
        
        # 使用限制数量的并发任务，避免被限流
        # 每批次处理的视频数量
        batch_size = 5
        total_batches = (len(leaked_videos) + batch_size - 1) // batch_size
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(leaked_videos))
            batch_videos = leaked_videos[start_idx:end_idx]
            
            logger.info(f"处理第 {batch_idx+1}/{total_batches} 批视频 ({len(batch_videos)}个)")
            
            # 创建并发任务
            tasks = []
            for video_info in batch_videos:
                video_id = video_info.get("video_id")
                if not video_id:
                    logger.warning("跳过无效的视频信息(缺少video_id)")
                    continue
                    
                # 查找对应的图片路径
                image_path = self.find_image_path(video_id, video_info, author_info, actress_info)
                
                # 创建生成元数据的任务
                task = self.generate_metadata(video_info, image_path, author_info, actress_info, enrich_from_web)
                tasks.append(task)
            
            # 等待本批次任务完成
            batch_results = await asyncio.gather(*tasks)
            
            # 过滤掉None结果
            valid_results = [result for result in batch_results if result]
            results.extend(valid_results)
            
            # 批次间休息一下，避免被限流
            if batch_idx < total_batches - 1:
                wait_time = self.min_wait_time
                logger.info(f"等待 {wait_time} 秒后处理下一批...")
                await asyncio.sleep(wait_time)
                
        logger.info(_("jellyfin.generate_complete").format(count=len(results)))
        return results
    
    def _clean_filename(self, name):
        """清理文件名，移除不允许的字符
        
        Args:
            name: 原始文件名
            
        Returns:
            str: 清理后的文件名
        """
        if not name:
            return "unknown"
            
        # 移除Windows文件系统不支持的字符
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in invalid_chars:
            name = name.replace(char, '_')
            
        # 移除前导和尾随空格
        name = name.strip()
        
        # 如果名称为空，使用默认名称
        if not name:
            return "unknown"
            
        return name 