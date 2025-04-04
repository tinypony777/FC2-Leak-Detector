"""
UI Manager for rich text interface
"""
import os
import sys
from datetime import datetime

# 确保虚拟环境路径被正确添加到sys.path中
try:
    # 获取当前脚本所在目录的父目录的父目录（项目根目录）
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

    # 检查是否存在虚拟环境目录
    venv_paths = [
        os.path.join(project_root, "env", "lib", "site-packages"),  # Windows venv
        os.path.join(project_root, "venv", "lib", "site-packages"),  # 另一种常见的venv
        os.path.join(project_root, ".venv", "lib", "site-packages"),  # 另一种常见的venv
    ]

    # 将存在的虚拟环境路径添加到sys.path
    for vp in venv_paths:
        if os.path.exists(vp) and vp not in sys.path:
            sys.path.insert(0, vp)
except Exception as e:
    pass

try:
    from rich import print as rprint
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
    from rich.table import Table
except ImportError as e:
    print(f"错误: 无法导入rich库: {e}")
    print("\n============== 重要提示 ==============")
    print("FC2流出检测器依赖于rich库来提供美观的界面和进度显示。")
    print("请使用以下命令安装rich库:")
    print("\npip install rich")
    print("\n如果你使用的是虚拟环境，请确保在虚拟环境中安装:")
    print("python -m pip install rich")
    print("\n安装完成后再次运行程序。")
    print("==================================")
    sys.exit(1)  # 退出程序


class RichUIManager:
    """管理富文本界面的类"""

    def __init__(self):
        """初始化UI管理器"""
        self.console = Console()
        self.progress = None
        self.task_id = None
        self.multi_author_mode = False
        self.multi_author_total = 0
        self.multi_author_task = None
        self.logs = []

    def update_progress(self, advance=1):
        """更新进度

        Args:
            advance: 增加的进度数
        """
        try:
            # 尝试更新进度条
            if self.progress and self.task_id is not None:
                self.progress.update(self.task_id, advance=advance)
        except Exception as e:
            # 如果更新失败，记录错误并尝试重新创建进度条
            print(f"进度条更新失败: {e}")
            # 如果任务已完成但进度条未关闭，则尝试停止
            try:
                if self.progress:
                    self.progress.stop()
            except:
                pass

    def set_multi_author_mode(self, total_authors):
        """设置多作者模式

        Args:
            total_authors: 总作者数
        """
        self.multi_author_mode = True
        self.multi_author_total = total_authors
        self.authors_data = {}  # 存储各作者的数据

        # 创建表格
        table = Table(title=f"FC2 多作者分析 (共{total_authors}个)")
        table.add_column("序号", justify="right", style="cyan", width=5)
        table.add_column("作者ID", style="green", width=10)
        table.add_column("作者名称", style="yellow", width=15)
        table.add_column("总视频数", justify="right", style="blue", width=10)
        table.add_column("已流出", justify="right", style="red", width=10)
        table.add_column("流出比例", justify="right", style="magenta", width=10)
        table.add_column("状态", style="bold", width=10)

        # 初始化每个作者的行
        for i in range(1, total_authors + 1):
            table.add_row(f"{i}", "等待中...", "", "", "", "", "等待中")
            self.authors_data[i] = {
                "idx": i,
                "id": None,
                "name": None,
                "total": 0,
                "leaked": 0,
                "status": "等待中",
            }

        self.console.print(table)
        self.authors_table = table

        # 创建进度条
        self.progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[bold green]{task.completed}/{task.total}"),
            TextColumn("[bold yellow]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
        )

        self.multi_author_task = self.progress.add_task(
            f"[bold]总进度 (0/{total_authors})", total=total_authors, completed=0
        )
        self.current_video_task = None
        self.progress.start()

        # 显示总计数据
        self.total_processed_authors = 0
        self.total_videos = 0
        self.total_leaked = 0

        # 日志区域
        self.console.print(Panel("日志信息", title="处理日志", border_style="blue"))

    def update_multi_author_total_videos(self, total_videos):
        """更新多作者模式下的总视频数

        Args:
            total_videos: 总视频数
        """
        if not self.multi_author_mode:
            print(f"当前作者共有 {total_videos} 个视频")
            return

        # 为当前作者创建视频处理进度条
        if self.current_video_task is None:
            self.current_video_task = self.progress.add_task(
                f"[bold yellow]处理视频 (0/{total_videos})", total=total_videos, completed=0
            )
        else:
            # 重置现有任务
            self.progress.update(
                self.current_video_task,
                total=total_videos,
                completed=0,
                description=f"[bold yellow]处理视频 (0/{total_videos})",
            )

        self.console.print(f"当前作者共有 {total_videos} 个视频")

    def update_author_progress(self, author_idx, author_id, author_name=None):
        """更新作者进度

        Args:
            author_idx: 作者索引
            author_id: 作者ID
            author_name: 作者名称
        """
        if not self.multi_author_mode:
            if author_name:
                print(
                    f"处理作者 ({author_idx}/{self.multi_author_total}): {author_id} [{author_name}]"
                )
            else:
                print(f"处理作者 ({author_idx}/{self.multi_author_total}): {author_id}")
            return

        # 更新作者数据
        if author_idx in self.authors_data:
            self.authors_data[author_idx]["id"] = author_id
            if author_name:
                self.authors_data[author_idx]["name"] = author_name
            self.authors_data[author_idx]["status"] = "处理中"

        # 更新表格
        name_display = f"{author_name}" if author_name else ""
        self.console.print(
            f"开始处理作者 ({author_idx}/{self.multi_author_total}): {author_id}"
            + (f" [{name_display}]" if name_display else "")
        )

        # 更新任务描述
        if self.multi_author_task is not None:
            self.progress.update(
                self.multi_author_task,
                description=f"[bold]总进度 ({self.total_processed_authors}/{self.multi_author_total})",
            )

    def update_status(self, status_data):
        """更新状态信息

        Args:
            status_data: 状态数据字典
        """
        # 更新状态面板
        status_table = Table(show_header=False, box=None)
        status_table.add_column("名称", style="bold")
        status_table.add_column("值", style="yellow")

        status_table.add_row("总视频数", str(status_data.get("total", 0)))
        status_table.add_row("已处理", str(status_data.get("processed", 0)))
        status_table.add_row("进度", f"{status_data.get('percentage', 0):.1f}%")
        status_table.add_row("已流出", str(status_data.get("leaked", 0)))
        status_table.add_row("流出比例", f"{status_data.get('leak_ratio', 0):.2f}%")

        self.console.print(Panel(status_table, title="处理状态", border_style="green"))

    def mark_author_completed(self, author_id, total, leaked, author_name=None):
        """标记作者处理完成

        Args:
            author_id: 作者ID
            total: 总视频数
            leaked: 已流出视频数
            author_name: 作者名称
        """
        if not self.multi_author_mode:
            leak_ratio = (leaked / max(total, 1)) * 100
            name_display = f" [{author_name}]" if author_name else ""
            print(
                f"作者 {author_id}{name_display} 处理完成: {leaked}/{total} ({leak_ratio:.2f}%)"
            )
            return

        # 计算流出比例
        leak_ratio = (leaked / max(total, 1)) * 100

        # 更新作者数据
        for idx, author_data in self.authors_data.items():
            if author_data["id"] == author_id:
                author_data["total"] = total
                author_data["leaked"] = leaked
                author_data["name"] = author_name or author_data["name"]
                author_data["status"] = "已完成"
                break

        # 更新总体统计
        self.total_processed_authors += 1
        self.total_videos += total
        self.total_leaked += leaked

        # 更新UI显示
        name_display = f" [{author_name}]" if author_name else ""
        self.console.print(
            f"[bold green]作者 {author_id}{name_display} 处理完成: {leaked}/{total} ({leak_ratio:.2f}%)[/bold green]"
        )

        # 更新进度条
        if self.multi_author_task is not None:
            self.progress.update(
                self.multi_author_task,
                advance=1,
                description=f"[bold]总进度 ({self.total_processed_authors}/{self.multi_author_total})",
            )

        # 如果有当前视频任务，则重置
        if self.current_video_task is not None:
            self.progress.update(
                self.current_video_task, completed=0, total=0, visible=False
            )
            self.current_video_task = None

        # 显示当前总体进度
        if self.total_videos > 0:
            total_ratio = (self.total_leaked / self.total_videos) * 100
            self.console.print(
                f"当前总进度: 共处理 {self.total_processed_authors}/{self.multi_author_total} 个作者, "
                f"总视频 {self.total_videos} 个, 流出 {self.total_leaked} 个 ({total_ratio:.2f}%)"
            )

        # 更新日志
        self.add_log(
            f"完成作者 {author_id} {name_display} 的处理: "
            f"总视频 {total}, 流出 {leaked} ({leak_ratio:.2f}%)",
            False,
        )

    def add_log(self, message, is_error=False):
        """添加日志

        Args:
            message: 日志消息
            is_error: 是否是错误日志
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {"timestamp": timestamp, "message": message, "is_error": is_error}

        self.logs.append(log_entry)

        # 使用rich打印日志
        if is_error:
            self.console.print(
                f"[bold red][错误][/bold red] [dim]{timestamp}[/dim] - {message}"
            )
        else:
            self.console.print(
                f"[bold green][信息][/bold green] [dim]{timestamp}[/dim] - {message}"
            )

    def finish(self):
        """完成处理"""
        if self.progress:
            self.progress.stop()

        if self.multi_author_mode and self.total_videos > 0:
            # 显示最终统计信息
            total_ratio = (self.total_leaked / self.total_videos) * 100

            # 创建统计表格
            stats_table = Table(title="处理统计")
            stats_table.add_column("项目", style="cyan")
            stats_table.add_column("数值", style="green")

            stats_table.add_row("总作者数", str(self.multi_author_total))
            stats_table.add_row("成功处理作者数", str(self.total_processed_authors))
            stats_table.add_row("总视频数", str(self.total_videos))
            stats_table.add_row("总流出数", str(self.total_leaked))
            stats_table.add_row("总流出比例", f"{total_ratio:.2f}%")

            # 添加更详细的统计信息
            if hasattr(self, "total_with_magnet"):
                stats_table.add_row("有磁力链接数", str(self.total_with_magnet))
                magnet_ratio = (
                    self.total_with_magnet / max(self.total_leaked, 1)
                ) * 100
                stats_table.add_row("磁链获取率", f"{magnet_ratio:.2f}%")

            if hasattr(self, "total_image_downloaded"):
                stats_table.add_row("已下载图片数", str(self.total_image_downloaded))
                image_ratio = (self.total_image_downloaded / self.total_videos) * 100
                stats_table.add_row("图片下载率", f"{image_ratio:.2f}%")

            if hasattr(self, "magnet_retries") and hasattr(
                self, "magnet_retry_success"
            ):
                retry_success_ratio = 0
                if self.magnet_retries > 0:
                    retry_success_ratio = (
                        self.magnet_retry_success / self.magnet_retries
                    ) * 100
                stats_table.add_row("磁链重试次数", str(self.magnet_retries))
                stats_table.add_row("磁链重试成功数", str(self.magnet_retry_success))
                stats_table.add_row("磁链重试成功率", f"{retry_success_ratio:.2f}%")

            self.console.print(stats_table)

        self.console.print("[bold green]处理完成！[/bold green]")

    def setup_videos_progress(self, total_videos):
        """设置视频进度显示

        Args:
            total_videos: 视频总数
        """
        # 创建进度显示
        from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn

        self.progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("{task.fields[status]}"),
        )
        self.task = self.progress.add_task(
            f"处理 {total_videos} 个视频", total=total_videos, status="准备中..."
        )
        self.progress.start()
