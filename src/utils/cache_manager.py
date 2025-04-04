"""
缓存管理模块 - 提供高效的数据缓存服务

负责管理视频状态、磁力链接和缩略图的缓存，支持自动过期和多级存储
"""
import json
import os
import time
from datetime import datetime, timedelta

from config import config


class CacheManager:
    """缓存管理器类，提供类方法和实例方法两种使用方式"""

    # 添加类变量用于单例模式
    cache_dir = config.cache_dir

    def __init__(self, cache_dir=None):
        """初始化缓存管理器 - 向后兼容的实例方法

        Args:
            cache_dir: 缓存目录，默认为配置中的cache_dir
        """
        self.cache_dir = str(cache_dir) if cache_dir else config.cache_dir
        self.video_status_cache = {}
        self.magnet_cache = {}
        self.thumbnail_cache = set()
        self.cache_expiry = config.cache_ttl // 86400  # 缓存过期天数 (从秒转换为天)

        # 创建缓存目录
        os.makedirs(self.cache_dir, exist_ok=True)

        # 创建子目录
        self.video_status_cache_file = os.path.join(self.cache_dir, "video_status.json")
        self.magnet_cache_file = os.path.join(self.cache_dir, "magnets.json")
        self.thumbnail_dir = os.path.join(self.cache_dir, "thumbnails")
        os.makedirs(self.thumbnail_dir, exist_ok=True)

        # 加载缓存
        self._load_caches()

    @classmethod
    def load(cls, writerid, is_actress=False):
        """类方法加载作者视频缓存，与fc2_main.py兼容

        Args:
            writerid: 作者ID
            is_actress: 是否为女优ID

        Returns:
            list: 作者视频列表，如果不存在则返回None
        """
        cache_dir = config.cache_dir

        # 使用正确的前缀
        prefix = "actress" if is_actress else "author"
        cache_file = os.path.join(cache_dir, f"{prefix}_{writerid}.json")

        if not os.path.exists(cache_file):
            return None

        try:
            # 读取文件内容并处理可能的BOM标记
            with open(cache_file, "rb") as f:
                content = f.read()

            # 检查并去除UTF-8 BOM标记 (EF BB BF)
            if content.startswith(b"\xef\xbb\xbf"):
                content = content[3:]
                print("⚠️ 检测到UTF-8 BOM标记，已自动移除")

            # 解析JSON
            data = json.loads(content.decode("utf-8"))

            # 检查缓存是否过期
            cache_time = datetime.strptime(data["timestamp"], "%Y-%m-%d %H:%M:%S")
            cache_ttl = config.cache_ttl  # 默认48小时
            if (datetime.now() - cache_time).total_seconds() > cache_ttl:
                print(
                    f"⚠️ 缓存已过期（{(datetime.now() - cache_time).seconds // 3600:.0f}小时）"
                )
                return None

            # 验证缓存数据格式
            videos = data.get("videos", [])
            if not isinstance(videos, list):
                print("❌ 缓存数据格式错误：videos不是列表类型")
                return None

            for idx, video in enumerate(videos):
                if not isinstance(video, dict):
                    print(f"❌ 缓存数据格式错误：第{idx+1}个视频不是字典类型")
                    return None
                if "video_id" not in video:
                    print(f"❌ 缓存数据格式错误：第{idx+1}个视频缺少video_id字段")
                    return None

            print(f"✅ 从缓存读取视频数据：{len(videos)}个")
            return videos

        except Exception as e:
            print(f"❌ 缓存加载失败: {str(e)}")
            return None

    @classmethod
    def save(cls, writerid, videos, is_actress=False):
        """类方法保存作者视频缓存，与fc2_main.py兼容

        Args:
            writerid: 作者ID
            videos: 视频列表或状态数据
            is_actress: 是否为女优ID

        Returns:
            bool: 是否成功保存
        """
        cache_dir = config.cache_dir
        os.makedirs(cache_dir, exist_ok=True)

        try:
            # 检查是否是视频状态数据
            if isinstance(videos, dict) and "status" in videos:
                # 保存视频状态
                cache_data = {
                    "writerid": writerid,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": videos["status"],
                    "site": videos.get("site"),
                    "status_code": videos.get("status_code"),
                    "timestamp": time.time(),
                }
                # 使用正确的前缀
                prefix = "actress" if is_actress else "author"
                cache_file = os.path.join(
                    cache_dir, f"{prefix}_video_status_{writerid}.json"
                )
            else:
                # 保存视频列表
                if not isinstance(videos, list):
                    print(f"❌ 缓存数据格式错误：videos必须是列表类型")
                    return False

                # 验证每个视频数据的格式
                for idx, video in enumerate(videos):
                    if not isinstance(video, dict):
                        print(f"❌ 缓存数据格式错误：第{idx+1}个视频不是字典类型")
                        return False
                    if "video_id" not in video:
                        print(f"❌ 缓存数据格式错误：第{idx+1}个视频缺少video_id字段")
                        return False

                cache_data = {
                    "writerid": writerid,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "videos": videos,
                }
                # 使用正确的前缀
                prefix = "actress" if is_actress else "author"
                cache_file = os.path.join(cache_dir, f"{prefix}_{writerid}.json")

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            print(f"💾 已缓存数据到 {cache_file}")
            return True

        except Exception as e:
            print(f"❌ 缓存保存失败: {str(e)}")
            return False

    @classmethod
    def save_batch_results(cls, writerid, results, batch_num, author_name=None):
        """保存批次处理结果 - fc2_main.py功能

        Args:
            writerid: 作者ID
            results: 结果列表
            batch_num: 批次编号
            author_name: 作者名称

        Returns:
            str: 保存的文件路径
        """
        result_dir = config.result_dir
        os.makedirs(result_dir, exist_ok=True)

        # 准备文件名前缀
        file_prefix = f"{writerid}"
        if author_name:
            file_prefix = f"{writerid} [{author_name}]"

        filename = os.path.join(result_dir, f"{file_prefix}_批次{batch_num}_临时结果.json")

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "writerid": writerid,
                        "batch": batch_num,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "results": results,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            print(f"💾 已保存批次{batch_num}处理结果 ({len(results)}个视频)")
            return filename
        except Exception as e:
            print(f"❌ 批次结果保存失败: {str(e)}")
            return None

    @classmethod
    def load_process_status(cls, writerid):
        """从本地缓存加载处理进度状态 - fc2_main.py功能

        Args:
            writerid: 作者ID或视频ID

        Returns:
            dict: 处理状态字典
        """
        cache_dir = config.cache_dir
        status_file = os.path.join(cache_dir, f"process_status_{writerid}.json")

        if not os.path.exists(status_file):
            return {"processed": [], "latest_batch": None}

        try:
            with open(status_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ 进度状态加载失败: {str(e)}")
            return {"processed": [], "latest_batch": None}

    @classmethod
    def save_process_status(cls, writerid, processed_ids, batch_id=None):
        """保存处理进度状态到本地缓存 - fc2_main.py功能

        Args:
            writerid: 作者ID
            processed_ids: 已处理的视频ID列表
            batch_id: 批次ID

        Returns:
            bool: 是否成功保存
        """
        cache_dir = config.cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        status_file = os.path.join(cache_dir, f"process_status_{writerid}.json")

        try:
            status = {
                "processed": processed_ids,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "latest_batch": batch_id,
            }

            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(status, f, ensure_ascii=False, indent=2)

            print(f"💾 已保存处理进度 ({len(processed_ids)}个视频)")
            return True
        except Exception as e:
            print(f"❌ 进度状态保存失败: {str(e)}")
            return False

    def set_magnet(self, video_id, magnet_link):
        """设置视频的磁力链接 - 实例方法"""
        if not video_id or not magnet_link:
            return False

        self.magnet_cache[video_id] = magnet_link

        # 保存到文件
        try:
            with open(self.magnet_cache_file, "w", encoding="utf-8") as f:
                json.dump(self.magnet_cache, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存磁力链接缓存失败: {str(e)}")
            return False

    def has_thumbnail(self, video_id):
        """检查是否已缓存缩略图 - 实例方法"""
        if not video_id:
            return False

        # 检查内存缓存
        if video_id in self.thumbnail_cache:
            return True

        # 检查文件系统
        return os.path.exists(os.path.join(self.thumbnail_dir, f"{video_id}.jpg"))

    def get_thumbnail_path(self, video_id):
        """获取缩略图路径 - 实例方法"""
        if not video_id:
            return None

        path = os.path.join(self.thumbnail_dir, f"{video_id}.jpg")

        if os.path.exists(path):
            self.thumbnail_cache.add(video_id)
            return path

        return None

    def set_thumbnail(self, video_id, image_data):
        """保存缩略图 - 实例方法"""
        if not video_id or not image_data:
            return None

        save_path = os.path.join(self.thumbnail_dir, f"{video_id}.jpg")

        try:
            with open(save_path, "wb") as f:
                f.write(image_data)

            self.thumbnail_cache.add(video_id)
            return save_path

        except Exception as e:
            print(f"保存缩略图失败: {str(e)}")
            return None

    @classmethod
    def is_cache_expired(cls, cache_file, expiry_days=7):
        """检查缓存文件是否过期

        Args:
            cache_file: 缓存文件路径或名称
            expiry_days: 过期天数，默认7天

        Returns:
            bool: 是否已过期
        """
        # 如果是相对路径，拼接缓存目录
        if not os.path.isabs(cache_file):
            cache_dir = config.cache_dir
            cache_file = os.path.join(cache_dir, cache_file)

        if not os.path.exists(cache_file):
            return True

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 检查时间戳格式
            if "timestamp" in data:
                # 如果是数字格式(Unix时间戳)
                if isinstance(data["timestamp"], (int, float)):
                    cache_time = data["timestamp"]
                    current_time = time.time()
                    # 超过expiry_days天则过期
                    return (current_time - cache_time) > (expiry_days * 86400)
                # 如果是字符串格式(日期时间)
                elif isinstance(data["timestamp"], str):
                    try:
                        cache_time = datetime.strptime(
                            data["timestamp"], "%Y-%m-%d %H:%M:%S"
                        )
                        # 超过expiry_days天则过期
                        return (datetime.now() - cache_time) > timedelta(
                            days=expiry_days
                        )
                    except:
                        return True

            # 如果是测试数据文件，不视为过期
            if len(data) > 0 and isinstance(data, list) and "video_id" in data[0]:
                return False

            # 如果没有时间戳或解析失败，视为过期
            return True

        except Exception as e:
            print(f"检查缓存过期失败: {str(e)}")
            return True

    @classmethod
    def clear_cache(cls, cache_type=None):
        """清除缓存

        Args:
            cache_type: 缓存类型，如果为None则清除所有缓存

        Returns:
            bool: 是否成功清除
        """
        cache_dir = cls.cache_dir

        try:
            # 确保目录存在
            if not os.path.exists(cache_dir):
                return True

            # 根据类型清除不同的缓存
            if cache_type == "video_status":
                pattern = "*_status_*.json"
            elif cache_type == "author":
                pattern = "author_*.json"
            elif cache_type == "actress":
                pattern = "actress_*.json"
            elif cache_type == "magnet":
                pattern = "*magnets*.json"
            else:
                # 清除所有JSON缓存文件
                for filename in os.listdir(cache_dir):
                    if filename.endswith(".json") and (
                        filename.startswith("author_")
                        or filename.startswith("actress_")
                    ):
                        os.remove(os.path.join(cache_dir, filename))
                return True

            # 根据模式删除文件
            import fnmatch

            for filename in os.listdir(cache_dir):
                if fnmatch.fnmatch(filename, pattern):
                    os.remove(os.path.join(cache_dir, filename))

            return True

        except Exception as e:
            print(f"清除缓存失败: {str(e)}")
            return False

    @classmethod
    def clear_all_caches(cls):
        """清除所有缓存文件的别名方法"""
        cache_dir = config.cache_dir

        try:
            # 确保目录存在
            if not os.path.exists(cache_dir):
                return True

            # 清除所有JSON文件
            for filename in os.listdir(cache_dir):
                if filename.endswith(".json"):
                    os.remove(os.path.join(cache_dir, filename))
            return True

        except Exception as e:
            print(f"清除缓存失败: {str(e)}")
            return False

    def _load_caches(self):
        """加载缓存文件到内存 - 私有方法"""
        # 加载视频状态缓存
        if os.path.exists(self.video_status_cache_file):
            try:
                with open(self.video_status_cache_file, "r", encoding="utf-8") as f:
                    self.video_status_cache = json.load(f)
            except:
                self.video_status_cache = {}

        # 加载磁力链接缓存
        if os.path.exists(self.magnet_cache_file):
            try:
                with open(self.magnet_cache_file, "r", encoding="utf-8") as f:
                    self.magnet_cache = json.load(f)
            except:
                self.magnet_cache = {}
