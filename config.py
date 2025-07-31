"""
FC2ビデオアナライザー - 設定モジュール

プログラムのすべての設定項目を機能別に整理しています。
必要に応じて調整して動作を最適化できます。
"""
import os
import platform
from typing import Any, Dict, List, Tuple, Union, Optional

# -----------------------------------------------
# パス設定
# -----------------------------------------------

# プロジェクトのルートディレクトリを取得
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# データ保存用の基礎ディレクトリ - デフォルトはプロジェクト直下のdataフォルダーを使用
BASE_CACHE_DIR = os.path.join(ROOT_DIR, "data")


class Config:
    """設定クラス。すべての設定項目を管理します"""
    
    _instance = None
    
    def __new__(cls):
        """シングルトンパターンでインスタンスを一つに保つ"""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """設定項目を初期化。最初の生成時にのみ実行されます"""
        # _initialized を前に設定し、メンバー参照の問題を回避
        if not hasattr(self, "_initialized"):
            self._initialized = False
            
        if self._initialized:
            return
            
        self._initialized = True
        
        # -------------------------
        # 基本情報
        # -------------------------
        self.version = "1.2.2"  # プログラムのバージョン
        
        # -------------------------
        # ネットワーク関連設定
        # -------------------------
        # リクエスト間隔設定 - 短時間でのアクセス集中を避ける
        self.page_interval = (0.5, 1.2)  # ページ取得間隔(秒)
        self.request_interval = (0.5, 1.0)  # 通常リクエストの間隔(秒)
        self.request_limit_count = 20  # 一定回数のリクエスト後に待機
        # 並列数とタイムアウト
        self.max_workers = 30  # 最大スレッド数 (増やすと速度向上するが制限リスクも増える)
        self.timeout = 15  # リクエストタイムアウト(秒)。ネット環境に応じて調整
        # リトライ設定
        self.max_retries = 4  # 最大リトライ回数
        self.retry_base = 2.0  # リトライ間隔の基準値
        
        # -------------------------
        # キャッシュ設定
        # -------------------------
        self.cache_ttl = 172800  # キャッシュの有効期間(秒)。初期値は48時間
        
        # -------------------------
        # データ保存ディレクトリ設定
        # -------------------------
        # 基本となるキャッシュおよびデータのディレクトリ
        self.cache_dir = os.path.join(BASE_CACHE_DIR, "id_cache")  # 作者・女優IDのキャッシュ
        self.image_dir = os.path.join(BASE_CACHE_DIR, "img")  # サムネイル保存先
        self.result_dir = os.path.join(BASE_CACHE_DIR, "results")  # 解析結果保存先
        self.magnet_dir = os.path.join(BASE_CACHE_DIR, "magnets")  # マグネットリンク保存先
        
        # ログディレクトリ設定
        self.log_dir = os.path.join(BASE_CACHE_DIR, "logs")  # メインログ
        self.log_app_dir = os.path.join(self.log_dir, "app")  # アプリケーションログ
        self.log_analysis_dir = os.path.join(self.log_dir, "analysis")  # 解析結果ログ
        self.log_error_dir = os.path.join(self.log_dir, "errors")  # エラーログ
        
        # ログファイル保持設定
        self.log_backup_count = 30  # ログを保持する日数
        self.log_rotation = "midnight"  # ローテーションタイミング: midnight(毎日), W0-W6(週次), h(毎時)
        
        # レポート設定
        self.summary_report = os.path.join(
            BASE_CACHE_DIR, "fc2_multi_author_summary.txt"
        )  # 複数作者の集計レポート
        
        # -------------------------
        # 動画確認サイト設定
        # -------------------------
        self.check_sites = [
            {
                "name": "24AV",
                "url": "https://24av.net/en/dm1/v/fc2-ppv-{vid}",
                "priority": 2,
                "status_codes": [200],
            },
        ]
        
        # -------------------------
        # API設定
        # -------------------------
        self.fc2ppvdb_api_base = "https://fc2ppvdb.com"  # FC2PPVDB APIの基底URL
        self.video_api_path = "/writers/writer-articles"  # 動画一覧APIのパス
        self.author_api_path = "/writers/"  # 作者情報取得APIのパス
        
        # -------------------------
        # -------------------------
        # マグネット検索設定
        # -------------------------
        # 以下は公開インデックスサイトを参照する例示設定です。
        # 著作権を侵害するコンテンツの取得や共有を推奨するものではありません。
        # 利用は各地域の法律を遵守してください。
        self.magnet_search_base = "https://sukebei.nyaa.si/"  # 検索サイトの基底URL
        self.magnet_search_path = "?f=0&c=2_2&q=FC2-PPV-{vid}"  # 検索パスのテンプレート
        
        # -------------------------
        # UI設定
        # -------------------------
        self.ui_refresh_interval = 0.5  # 画面更新間隔(秒)
        self.progress_color = "green"  # プログレスバーの色 (green, blue, yellow, red, cyan, magenta)
        self.error_color = "red"  # エラーメッセージの色
        
        # -------------------------
        # -------------------------
        # 出力設定
        # -------------------------
        self.save_format = ["text", "json"]  # 保存形式: "text"、"json" または併用
        self.report_batch_size = 100  # レポート1ページに表示する動画数
        
        # -------------------------
        # -------------------------
        # ログ設定
        # -------------------------
        self.log_level = "INFO"  # ログレベル: DEBUG, INFO, WARNING, ERROR, CRITICAL
        
        # ログファイル名の書式
        self.log_date_format = "%Y%m%d"  # 日付のみのフォーマット(例:20250531)
        self.log_datetime_format = "%Y%m%d_%H%M%S"  # 日時を含むフォーマット(例:20250531_040816)
        self.log_timestamp_format = "%Y-%m-%d %H:%M:%S"  # ログ出力時刻のフォーマット
        
        # ログファイル名オプション
        self.log_use_datetime = True  # ファイル名に日時を含めるか
        
        # ログの重複フィルタ設定
        self.log_enable_duplicate_filter = True  # 同一内容を重複記録しない
        
        # コンソールログ設定
        self.log_enable_console = True  # コンソールにログを表示するか
        self.log_console_format = "%(levelname)s - %(message)s"  # コンソール用フォーマット
        
        # ファイルログ設定
        self.log_file_format = "%(asctime)s - %(levelname)s - %(message)s"  # ファイル用フォーマット
        self.log_error_format = "%(asctime)s - %(levelname)s - %(message)s"  # エラーログ用フォーマット
        self.log_analysis_format = "%(asctime)s - %(message)s"  # 解析ログ用フォーマット
        
        # -------------------------
        # 高度なネットワーク設定
        # -------------------------
        self.enable_proxy = False  # プロキシを使用するか
        self.proxy = {  # enable_proxy が True の場合に有効
            "http": "",  # HTTP プロキシ
            "https": "",  # HTTPS プロキシ
        }

        # User-Agent をローテーションしてアクセス制限を回避
        self.user_agents = [
            # Windows Chrome
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            # macOS Safari
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
            # Windows Firefox
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
            # Linux Chrome
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.6494.65 Safari/537.36",
            # Windows Edge
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
            # Mobile User Agents
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.6558.50 Mobile Safari/537.36",
        ]
        
        # 基本ヘッダー
        self.base_headers = {
            "User-Agent": self.user_agents[0],
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "DNT": "1",  # Do Not Track
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
        }
        
        # API用ヘッダー
        self.api_headers = {
            "User-Agent": self.user_agents[0],
            "accept": "*/*",
            "sec-fetch-site": "same-origin",
            "x-requested-with": "XMLHttpRequest",
            "referer": "https://fc2ppvdb.com/",
        }
        
        # システム環境情報を取得
        self.system_info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "python_version": platform.python_version(),
        }
        
        # OSに合わせてファイルパスの長さ制限を設定
        if self.system_info["os"] == "Windows":
            self.file_path_max_length = 260  # Windowsの制限
        elif self.system_info["os"] == "Darwin":  # macOS
            self.file_path_max_length = 1024
        else:  # Linuxなど
            self.file_path_max_length = 4096
            
        # 必要なディレクトリを作成
        self._create_directories()
    
    def _create_directories(self):
        """必要なディレクトリを作成する"""
        directories = [
            # データディレクトリ
            self.cache_dir,
            self.result_dir,
            self.image_dir,
            self.magnet_dir,
            # ログディレクトリ構造
            self.log_dir,
            self.log_app_dir,      # 应用程序日志
            self.log_analysis_dir, # 分析结果日志
            self.log_error_dir,    # 错误日志
            # 基础数据目录
            BASE_CACHE_DIR
        ]
        
        for directory in directories:
            try:
                os.makedirs(directory, exist_ok=True)
            except Exception as e:
                print(f"警告: ディレクトリ {directory} を作成できません: {e}")
                
        # 空ディレクトリもGitで管理するため.gitkeepを作成
        for directory in directories:
            gitkeep_file = os.path.join(directory, ".gitkeep")
            if not os.path.exists(gitkeep_file):
                try:
                    with open(gitkeep_file, "w") as f:
                        pass  # 空ファイル作成
                except Exception:
                    pass  # 失敗しても無視
    
    def get(self, key: str, default: Any = None) -> Any:
        """設定値を取得する。dict風アクセス用"""
        return getattr(self, key, default)
    
    def set(self, key: str, value: Any) -> None:
        """設定値をセット"""
        setattr(self, key, value)
    
    def update(self, config_dict: Dict[str, Any]) -> None:
        """辞書から複数の設定を更新"""
        for key, value in config_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式に変換"""
        result = {}
        for key in dir(self):
            if not key.startswith('_') and not callable(getattr(self, key)):
                result[key] = getattr(self, key)
        return result
    
    def __getitem__(self, key: str) -> Any:
        """辞書風アクセスをサポート"""
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"設定項目 '{key}' は存在しません")
    
    def __setitem__(self, key: str, value: Any) -> None:
        """辞書風に設定値をセット"""
        setattr(self, key, value)


# グローバル設定インスタンスを生成
config = Config()

