"""
报告生成模块 - 分析结果处理与输出格式化工具

提供多种格式的分析结果报告生成功能，支持文本和JSON输出格式，
可生成统计摘要、分类报告和详细数据报告
"""
import datetime
import json
import os

from config import config
from src.utils.i18n import get_text as _  # 添加国际化支持


class ReportGenerator:
    """报告生成器类"""

    def __init__(self, save_dir=None):
        """初始化报告生成器

        Args:
            save_dir: 保存目录，默认为配置中的report_dir
        """
        self.save_dir = save_dir or config.result_dir
        os.makedirs(self.save_dir, exist_ok=True)

    @classmethod
    def generate_full_report(cls, writer_id, results, writer_name=None):
        """类方法生成作者完整报告，与fc2_main.py兼容

        Args:
            writer_id: 作者ID
            results: 分析结果列表
            writer_name: 作者名称，可选

        Returns:
            dict: 报告结果，包含保存的文件路径和统计信息
        """
        if not results:
            return {"stats": {}, "saved_files": {}}

        # 准备文件名前缀 - 总是使用ID_作者名格式
        file_prefix = f"{writer_id}"
        if writer_name:
            file_prefix = f"{writer_id}_{writer_name}"

        # 创建报告目录
        save_dir = config.result_dir
        os.makedirs(save_dir, exist_ok=True)

        # 生成文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{file_prefix}_总报告.txt"
        filepath = os.path.join(save_dir, filename)

        # 分类处理 - 统一格式处理
        leaked = []
        unleaked = []
        error = []
        unknown = []

        for result in results:
            # 兼容不同格式的状态字段
            status = result.get("status")
            if status in ["leaked", "已流出"]:
                leaked.append(result)
            elif status in ["not_leaked", "未流出"]:
                unleaked.append(result)
            elif status in ["error", "错误"]:
                error.append(result)
            else:
                unknown.append(result)

        # 进一步细分已泄漏视频
        has_magnet = [r for r in leaked if r.get("magnets") or r.get("magnet")]
        no_magnet = [r for r in leaked if not (r.get("magnets") or r.get("magnet"))]

        # 保存分类报告
        saved_files = {}

        if has_magnet:
            has_magnet_file = cls._save_category(
                file_prefix, "已流出_有磁链", has_magnet, save_dir
            )
            saved_files["leaked_with_magnet"] = has_magnet_file

        if no_magnet:
            no_magnet_file = cls._save_category(
                file_prefix, "已流出_无磁链", no_magnet, save_dir
            )
            saved_files["leaked_without_magnet"] = no_magnet_file

        if unleaked:
            unleaked_file = cls._save_category(file_prefix, "未流出", unleaked, save_dir)
            saved_files["unleaked"] = unleaked_file

        if error:
            error_file = cls._save_category(file_prefix, "错误", error, save_dir)
            saved_files["error"] = error_file

        if unknown:
            unknown_file = cls._save_category(file_prefix, "未知", unknown, save_dir)
            saved_files["unknown"] = unknown_file

        if leaked:
            leaked_summary = cls._save_leaked_summary(file_prefix, leaked, save_dir)
            saved_files["leaked_summary"] = leaked_summary

        # 生成统计信息
        stats = {
            "total": len(results),
            "leaked": len(leaked),
            "unleaked": len(unleaked),
            "error": len(error),
            "unknown": len(unknown),
            "with_magnet": len(has_magnet),
            "without_magnet": len(no_magnet),
        }

        # 生成总报告
        report_content = [
            f"作者ID: {writer_id}",
            f"作者名称: {writer_name or '未知'}",
            f"总视频数: {len(results)}",
            f"已流出视频: {len(leaked)} (含磁链: {len(has_magnet)} / 无磁链: {len(no_magnet)})",
            f"未流出视频: {len(unleaked)}",
            f"错误视频数: {len(error)}",
            f"未知状态数: {len(unknown)}",
            f"\n报告生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "\n详细报告请查看分类文件",
        ]

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(report_content))
            print(f"✅ 报告生成完成: {filepath}")
            saved_files["full_report"] = filepath
        except Exception as e:
            print(f"❌ 报告生成失败: {str(e)}")

        # 同时保存JSON格式的完整报告
        json_filepath = os.path.join(save_dir, f"{file_prefix}_完整报告.json")
        try:
            with open(json_filepath, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "writerid": writer_id,
                        "author_name": writer_name,
                        "timestamp": datetime.datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "stats": stats,
                        "results": results,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            saved_files["json_report"] = json_filepath
        except Exception as e:
            print(f"❌ 保存JSON报告失败: {str(e)}")

        print(f"\n📊 分析结果: 总计 {stats['total']} 个视频")
        print(f"✅ 已泄漏: {stats['leaked']} 个 (含磁链: {stats['with_magnet']})")
        print(f"❌ 未泄漏: {stats['unleaked']} 个")
        print(f"⚠️ 检查失败: {stats['error']} 个")
        print(f"❓ 状态未知: {stats['unknown']} 个")

        return {"stats": stats, "saved_files": saved_files}

    @classmethod
    def _save_category(cls, file_prefix, category, data, save_dir):
        """保存分类报告

        Args:
            file_prefix: 文件前缀
            category: 分类名称
            data: 数据列表
            save_dir: 保存目录

        Returns:
            str: 保存的文件路径
        """
        if not data:
            return None

        content = [f"=== {category} ({len(data)}个) ==="]
        for idx, item in enumerate(data, 1):
            line = f"{idx}. {item.get('video_id', 'unknown')} | {item.get('title', '未知标题')}"
            # 兼容两种磁力链接格式
            magnets = (
                item.get("magnets") or [item.get("magnet")]
                if item.get("magnet")
                else []
            )
            if magnets:
                line += "\n" + "\n".join([f"    • {m}" for m in magnets if m])
            content.append(line)

        filename = os.path.join(save_dir, f"{file_prefix}_{category}.txt")
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("\n".join(content))
            print(f"✅ 已生成分类报告: {filename}")
            return filename
        except Exception as e:
            print(f"❌ 分类报告生成失败: {str(e)}")
            return None

    @classmethod
    def _save_leaked_summary(cls, file_prefix, leaked_videos, save_dir):
        """保存已流出视频总表

        Args:
            file_prefix: 文件前缀
            leaked_videos: 已流出视频列表
            save_dir: 保存目录

        Returns:
            str: 保存的文件路径
        """
        if not leaked_videos:
            return None

        # 文本总表
        filename = os.path.join(save_dir, f"{file_prefix}_已流出视频总表.txt")
        content = [f"=== 已流出视频总表 ({len(leaked_videos)}个) ==="]

        for idx, video in enumerate(leaked_videos, 1):
            content.append(
                f"{idx}. {video.get('video_id', '')} | {video.get('title', '未知标题')}"
            )

        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("\n".join(content))
            print(f"✅ 已生成流出视频总表: {filename}")
        except Exception as e:
            print(f"❌ 流出视频总表生成失败: {str(e)}")

        # 磁力链接文件
        magnet_file = os.path.join(save_dir, f"{file_prefix}_磁力链接.txt")
        magnet_content = [
            f"# 生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# 总计 {len(leaked_videos)} 个视频\n",
        ]

        for video in leaked_videos:
            title = video.get("title", "未知标题")
            # 兼容两种磁力链接格式
            magnets = (
                video.get("magnets") or [video.get("magnet")]
                if video.get("magnet")
                else []
            )

            if magnets:
                magnet_content.append(f"# {video.get('video_id', '')} | {title}")
                magnet_content.extend([m for m in magnets if m])
                magnet_content.append("")  # 空行分隔
            else:
                magnet_content.append(f"# {video.get('video_id', '')} | {title}")
                magnet_content.append("# [未获取到磁力链接]")
                magnet_content.append("")  # 空行分隔

        try:
            with open(magnet_file, "w", encoding="utf-8") as f:
                f.write("\n".join(magnet_content))
            print(f"✅ 已生成磁力链接文件: {magnet_file}")
            return magnet_file
        except Exception as e:
            print(f"❌ 磁力链接文件生成失败: {str(e)}")
            return None

    @staticmethod
    def clean_filename(name):
        """清理文件名中的非法字符

        Args:
            name: 原始文件名

        Returns:
            str: 清理后的文件名
        """
        # 替换Windows文件系统不允许的字符
        invalid_chars = r'<>:"/\|?*'
        for char in invalid_chars:
            name = name.replace(char, "_")

        # 限制长度
        if len(name) > 200:
            name = name[:197] + "..."

        return name

    def generate_multi_writer_report(self, writers_data):
        """生成多作者汇总报告

        Args:
            writers_data: 多个作者的数据列表，每个元素是包含作者信息和结果的字典

        Returns:
            str: 保存的文件路径
        """
        if not writers_data:
            return None

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"multi_writer_report_{timestamp}"  # 移除.json后缀
        filepath = os.path.join(self.save_dir, filename)

        total_videos = 0
        total_leaked = 0
        total_with_magnet = 0
        total_image_downloaded = 0

        writers_summary = []

        for writer_data in writers_data:
            writer_id = writer_data.get("writer_id")
            writer_name = writer_data.get("writer_name", "未知")
            results = writer_data.get("results", [])
            status = writer_data.get("status")

            if status != "success" or not results:
                continue

            writer_total = len(results)
            # 修复：使用正确的键匹配流出视频状态
            writer_leaked = sum(
                1 for r in results if r.get("leaked", False) or r.get("status") == "已流出"
            )
            writer_with_magnet = sum(
                1
                for r in results
                if (r.get("leaked", False) or r.get("status") == "已流出")
                and (r.get("has_magnet", False) or r.get("magnet", []))
            )
            writer_image_downloaded = sum(
                1 for r in results if r.get("image_downloaded", False)
            )

            total_videos += writer_total
            total_leaked += writer_leaked
            total_with_magnet += writer_with_magnet
            total_image_downloaded += writer_image_downloaded

            writers_summary.append(
                {
                    "writer_id": writer_id,
                    "writer_name": writer_name,
                    "total_videos": writer_total,
                    "leaked_videos": writer_leaked,
                    "with_magnet": writer_with_magnet,
                    "image_downloaded": writer_image_downloaded,
                    "leak_ratio": round(writer_leaked / max(writer_total, 1) * 100, 2),
                }
            )

        # 按流出率排序
        writers_summary.sort(key=lambda x: x["leak_ratio"], reverse=True)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("=== FC2 多作者分析汇总报告 ===\n")
                f.write(
                    f"生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                f.write(f"总作者数: {len(writers_data)}\n")
                f.write(f"成功处理作者数: {len(writers_summary)}\n")
                f.write(f"总视频数: {total_videos}\n")
                f.write(f"总流出数: {total_leaked}\n")
                f.write(f"总流出比例: {total_leaked / max(total_videos, 1) * 100:.2f}%\n\n")

                # 添加更详细的统计信息
                f.write(f"有磁力链接数: {total_with_magnet}\n")
                f.write(
                    f"磁链获取率: {(total_with_magnet / max(total_leaked, 1) * 100):.2f}%\n"
                )
                f.write(f"已下载图片数: {total_image_downloaded}\n")
                f.write(
                    f"图片下载率: {(total_image_downloaded / max(total_videos, 1) * 100):.2f}%\n\n"
                )

                # 写入作者流出比例排名
                f.write("=== 作者流出比例排名 ===\n\n")
                for idx, writer in enumerate(writers_summary, 1):
                    name_display = (
                        f" [{writer['writer_name']}]" if writer["writer_name"] else ""
                    )
                    f.write(
                        f"{idx}. {writer['writer_id']}{name_display}: {writer['leaked_videos']}/{writer['total_videos']} ({writer['leak_ratio']:.2f}%)\n"
                    )
                    f.write(
                        f"   - 有磁链: {writer['with_magnet']}, 有图片: {writer['image_downloaded']}\n"
                    )

                # 详细作者报告
                f.write("\n=== 作者详细信息 ===\n\n")
                for writer in writers_summary:
                    f.write(f"作者ID: {writer['writer_id']}\n")
                    f.write(f"作者名称: {writer['writer_name']}\n")
                    f.write(f"总视频数: {writer['total_videos']}\n")
                    f.write(f"已流出视频数: {writer['leaked_videos']}\n")
                    f.write(f"有磁力链接数: {writer['with_magnet']}\n")
                    f.write(f"有图片数: {writer['image_downloaded']}\n")
                    f.write(f"流出比例: {writer['leak_ratio']}%\n")
                    f.write("------------------------------\n")

                # 添加更完整的总结统计
                f.write("\n=== 总结统计 ===\n\n")
                f.write("【视频流出情况】\n")
                f.write(f"总作者数: {len(writers_summary)} 个\n")
                f.write(f"总视频数: {total_videos} 个\n")
                f.write(f"已流出视频: {total_leaked} 个\n")
                f.write(f"未流出视频: {total_videos - total_leaked} 个\n")
                f.write(f"总流出比例: {total_leaked / max(total_videos, 1) * 100:.2f}%\n\n")

                f.write("【磁力链接情况】\n")
                f.write(f"已获取磁链数: {total_with_magnet} 个\n")
                f.write(
                    f"磁链获取率(相对流出): {(total_with_magnet / max(total_leaked, 1) * 100):.2f}%\n"
                )
                f.write(
                    f"磁链获取率(相对总数): {(total_with_magnet / max(total_videos, 1) * 100):.2f}%\n\n"
                )

                f.write("【图片下载情况】\n")
                f.write(f"已下载图片数: {total_image_downloaded} 个\n")
                f.write(
                    f"图片下载率: {(total_image_downloaded / max(total_videos, 1) * 100):.2f}%\n\n"
                )

                # 计算流出率最高和最低的作者
                if writers_summary:
                    highest_leak = writers_summary[0]  # 已按流出率排序，第一个就是最高的
                    lowest_leak = sorted(
                        writers_summary, key=lambda x: x["leak_ratio"]
                    )[
                        0
                    ]  # 获取最低的

                    f.write("【作者数据记录】\n")
                    f.write(
                        f"流出率最高: {highest_leak['writer_name']} "
                        f"({highest_leak['leak_ratio']:.2f}%, "
                        f"{highest_leak['leaked_videos']}/{highest_leak['total_videos']})\n"
                    )
                    f.write(
                        f"流出率最低: {lowest_leak['writer_name']} "
                        f"({lowest_leak['leak_ratio']:.2f}%, "
                        f"{lowest_leak['leaked_videos']}/{lowest_leak['total_videos']})\n"
                    )

                    # 找出视频数量最多的作者
                    most_videos = max(writers_summary, key=lambda x: x["total_videos"])
                    f.write(
                        f"视频数量最多: {most_videos['writer_name']} "
                        f"({most_videos['total_videos']} 个视频, "
                        f"流出率 {most_videos['leak_ratio']:.2f}%)\n"
                    )

                f.write(
                    "\n=== 报告生成时间: {0} ===\n".format(
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                )

            # 添加JSON输出
            json_filepath = os.path.join(self.save_dir, f"{filename}.json")
            with open(json_filepath, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "timestamp": datetime.datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "total_writers": len(writers_summary),
                        "total_videos": total_videos,
                        "total_leaked": total_leaked,
                        "avg_leak_ratio": total_leaked / max(total_videos, 1) * 100,
                        "total_with_magnet": total_with_magnet,
                        "magnet_ratio": (
                            total_with_magnet / max(total_leaked, 1) * 100
                        ),
                        "total_image_downloaded": total_image_downloaded,
                        "image_ratio": (
                            total_image_downloaded / max(total_videos, 1) * 100
                        ),
                        "writers_data": writers_summary,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            print(f"\n✅ 多作者汇总报告已生成: {filepath}")
            print(f"✅ JSON格式汇总报告已生成: {json_filepath}")

            return filepath

        except Exception as e:
            print(f"保存多作者报告失败: {e}")
            return None

    def generate_multi_actress_report(self, actresses_data):
        """生成多个女优的汇总报告

        将多个女优的分析结果汇总到一个报告中，并生成统计图表

        Args:
            actresses_data: 包含多个女优信息的列表

        Returns:
            str: 汇总报告路径
        """
        if not actresses_data:
            print("没有数据可以生成汇总报告")
            return None

        try:
            # 整理数据 - 删除空结果的女优
            valid_data = [
                a
                for a in actresses_data
                if a.get("status") != "no_videos" and a.get("total_videos", 0) > 0
            ]

            if not valid_data:
                print("没有有效的女优数据可以生成汇总报告")
                return None

            # 确保保存目录存在
            os.makedirs(self.save_dir, exist_ok=True)

            # 生成汇总文件名
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_prefix = f"多女优汇总_{timestamp}"

            # 生成总报告路径
            filepath = os.path.join(self.save_dir, f"{file_prefix}_汇总报告.txt")

            # 计算总体统计信息
            total_actresses = len(valid_data)
            total_videos = sum(a.get("total_videos", 0) for a in valid_data)
            total_leaked = sum(a.get("leaked_videos", 0) for a in valid_data)
            total_with_magnet = sum(a.get("with_magnet", 0) for a in valid_data)
            total_image_downloaded = sum(
                a.get("image_downloaded", 0) for a in valid_data
            )
            leak_ratio = (total_leaked / max(total_videos, 1)) * 100

            # 按流出比例排序
            sorted_data = sorted(
                valid_data, key=lambda x: x.get("leaked_ratio", 0), reverse=True
            )

            # 生成文本报告
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("=== FC2 多女优分析汇总报告 ===\n")
                f.write(
                    f"生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                f.write(f"总女优数: {total_actresses}\n")
                f.write(f"总视频数: {total_videos}\n")
                f.write(f"总流出数: {total_leaked}\n")
                f.write(f"总流出比例: {leak_ratio:.2f}%\n\n")

                # 添加详细的统计信息
                f.write(f"有磁力链接数: {total_with_magnet}\n")
                f.write(
                    f"磁链获取率: {(total_with_magnet / max(total_leaked, 1) * 100):.2f}%\n"
                )
                f.write(f"已下载图片数: {total_image_downloaded}\n")
                f.write(
                    f"图片下载率: {(total_image_downloaded / max(total_videos, 1) * 100):.2f}%\n\n"
                )

                # 写入女优排名
                f.write("=== 女优流出比例排名 ===\n\n")
                for idx, actress in enumerate(sorted_data, 1):
                    name = actress.get(
                        "actress_name", f"女优_{actress.get('actress_id', 'Unknown')}"
                    )
                    total = actress.get("total_videos", 0)
                    leaked = actress.get("leaked_videos", 0)
                    ratio = actress.get("leaked_ratio", 0)
                    actress_id = actress.get("actress_id", "Unknown")
                    with_magnet = actress.get("with_magnet", 0)
                    with_image = actress.get("image_downloaded", 0)

                    f.write(
                        f"{idx}. {actress_id} [{name}]: {leaked}/{total} ({ratio:.2f}%)\n"
                    )
                    f.write(f"   - 有磁链: {with_magnet}, 有图片: {with_image}\n")

                # 详细女优信息
                f.write("\n=== 女优详细信息 ===\n\n")
                for actress in sorted_data:
                    f.write(f"女优ID: {actress.get('actress_id', 'Unknown')}\n")
                    f.write(f"女优名称: {actress.get('actress_name', 'Unknown')}\n")
                    f.write(f"总视频数: {actress.get('total_videos', 0)}\n")
                    f.write(f"已流出视频数: {actress.get('leaked_videos', 0)}\n")
                    f.write(f"有磁力链接数: {actress.get('with_magnet', 0)}\n")
                    f.write(f"有图片数: {actress.get('image_downloaded', 0)}\n")
                    f.write(f"流出比例: {actress.get('leaked_ratio', 0):.2f}%\n")
                    f.write("------------------------------\n")

                # 添加更完整的总结统计
                f.write("\n=== 总结统计 ===\n\n")
                f.write("【视频流出情况】\n")
                f.write(f"总女优数: {total_actresses} 个\n")
                f.write(f"总视频数: {total_videos} 个\n")
                f.write(f"已流出视频: {total_leaked} 个\n")
                f.write(f"未流出视频: {total_videos - total_leaked} 个\n")
                f.write(f"总流出比例: {leak_ratio:.2f}%\n\n")

                f.write("【磁力链接情况】\n")
                f.write(f"已获取磁链数: {total_with_magnet} 个\n")
                f.write(
                    f"磁链获取率(相对流出): {(total_with_magnet / max(total_leaked, 1) * 100):.2f}%\n"
                )
                f.write(
                    f"磁链获取率(相对总数): {(total_with_magnet / max(total_videos, 1) * 100):.2f}%\n\n"
                )

                f.write("【图片下载情况】\n")
                f.write(f"已下载图片数: {total_image_downloaded} 个\n")
                f.write(
                    f"图片下载率: {(total_image_downloaded / max(total_videos, 1) * 100):.2f}%\n\n"
                )

                # 计算流出率最高和最低的女优
                if sorted_data:
                    highest_leak = sorted_data[0]  # 已按流出率排序，第一个就是最高的
                    lowest_leak = sorted(
                        sorted_data, key=lambda x: x.get("leaked_ratio", 0)
                    )[
                        0
                    ]  # 获取最低的

                    f.write("【女优数据记录】\n")
                    f.write(
                        f"流出率最高: {highest_leak.get('actress_name', '')} "
                        f"({highest_leak.get('leaked_ratio', 0):.2f}%, "
                        f"{highest_leak.get('leaked_videos', 0)}/{highest_leak.get('total_videos', 0)})\n"
                    )
                    f.write(
                        f"流出率最低: {lowest_leak.get('actress_name', '')} "
                        f"({lowest_leak.get('leaked_ratio', 0):.2f}%, "
                        f"{lowest_leak.get('leaked_videos', 0)}/{lowest_leak.get('total_videos', 0)})\n"
                    )

                    # 找出视频数量最多的女优
                    most_videos = max(
                        sorted_data, key=lambda x: x.get("total_videos", 0)
                    )
                    f.write(
                        f"视频数量最多: {most_videos.get('actress_name', '')} "
                        f"({most_videos.get('total_videos', 0)} 个视频, "
                        f"流出率 {most_videos.get('leaked_ratio', 0):.2f}%)\n"
                    )

                f.write(
                    "\n=== 报告生成时间: {0} ===\n".format(
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                )

            # 保存JSON格式报告
            json_filepath = os.path.join(self.save_dir, f"{file_prefix}_汇总报告.json")
            with open(json_filepath, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "timestamp": datetime.datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "total_actresses": total_actresses,
                        "total_videos": total_videos,
                        "total_leaked": total_leaked,
                        "avg_leak_ratio": leak_ratio,
                        "total_with_magnet": total_with_magnet,
                        "magnet_ratio": (
                            total_with_magnet / max(total_leaked, 1) * 100
                        ),
                        "total_image_downloaded": total_image_downloaded,
                        "image_ratio": (
                            total_image_downloaded / max(total_videos, 1) * 100
                        ),
                        "actresses_data": valid_data,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            print(f"\n✅ 多女优汇总报告已生成: {filepath}")
            print(f"✅ JSON格式汇总报告已生成: {json_filepath}")

            return filepath
        except Exception as e:
            print(f"❌ 生成多女优汇总报告时出错: {str(e)}")
            return None
