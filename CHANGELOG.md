# 更新日志 / Changelog / 更新履歴

本文档记录FC2视频分析器的所有重要变更。

格式基于[Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循[语义化版本规范](https://semver.org/lang/zh-CN/)。

## 选择语言 | Language | 言語

- [简体中文](#简体中文)
- [English](#english)
- [日本語](#日本語)

## 开发计划说明

**注意**：本项目的未来开发计划（包括GUI客户端、网页端支持、数据库存储等功能）将在另一个尚未公开的项目中继续进行。当新项目公开时，我们会在此处更新相关信息。

# 简体中文

## [1.2.1] - 2025-05-31

### 新增
- 改进了Jellyfin元数据生成功能，添加了可点击的链接和按钮
- 添加了MissAV和123AV观看链接到NFO文件中

### 修复
- 修复了女优被错误分类到作者目录的问题
- 优化了海报文件结构以提高Jellyfin兼容性

### 文档
- 添加了关于Jellyfin元数据占位MP4文件的说明
- 更新了使用说明，包括预告片按钮和磁力链接的使用方法

## [1.2.0] - 2025-05-31

### 新增

- 添加Jellyfin媒体服务器元数据生成功能
  - 支持将FC2视频分析结果转换为Jellyfin兼容的NFO文件
  - 自动生成视频海报图片（基于缩略图）
  - 添加--jellyfin命令行参数，使其成为可选功能
  - 元数据包含视频基本信息、视频标签、磁力链接和作者信息
- 优化文件结构，使海报图片与视频文件在同一目录，符合Jellyfin标准

### 变更

- 移除冗余代码和未使用的方法
- 优化配置项和日志输出

### 修复

- 修复各种问题并改进配置

## [1.1.1] - 2025-05-31

### 修复

- 优化清除缓存功能，添加对正在使用的日志文件的处理
- 简化日志格式，移除模块名、函数名和行号，提高日志可读性
- 修复占位符替换问题，通过简化步骤名称格式解决日志中的未格式化占位符
- 优化日志系统架构，使用标准的Python日志处理机制
- 添加精确到秒的时间戳到日志文件名，提高日志文件唯一性
- 更新配置和日志器，使用可配置的日志参数增强灵活性
- 优化日志文件组织结构，更好地分类不同类型的日志
- 移除调试打印语句，清理代码
- 修复批处理中的重复缓存创建问题

## [1.1.0] - 2025-05-25

### 新增

- 增强的日语翻译支持，完善了日语界面
- 添加更多翻译键，确保多语言功能完整

### 变更

- 优化国际化架构，完善i18n文件结构
- 统一所有语言文件的翻译键，确保一致性
- 更新pyproject.toml，从setuptools迁移到hatchling构建系统
- 完善构建配置和工作流，确保正确的项目元数据
- 添加wheel包定义配置，改进包分发机制
- 更新README，提供更清晰的安装和使用说明
- 更新README中的语言切换示例，使多语言使用更直观

### 修复

- 修复硬编码中文消息问题，使用i18n翻译函数替代
- 解决了英语、日语翻译文件中缺失的键
- 解决嵌套花括号格式问题，优化翻译字符串
- 修复分析结果中流出视频数统计错误的问题
- 修复日志和磁链文件保存问题，优化多种类型爬取时的数据保存
- 更新setup.py包配置并移除README中不必要的引用

## [1.0.0] - 2025-04-04

### 新增

- 首次公开发布
- 支持通过作者ID获取视频列表
- 支持通过女优ID获取视频列表
- 支持通过视频ID查找并分析作者功能 (`-v ID` 参数)
- 检查视频流出状态
- 基本的统计功能
- 命令行界面
- 优化的线程池管理提高并行处理效率
- 增强的错误处理与重试机制
- 磁力链接自动提取与验证
- 完善的国际化支持 (中文和英文)
- 智能缓存系统减少重复请求
- 详细的统计分析与可视化报告
- 视频缩略图自动下载与管理

### 变更

- 重构代码结构，提高可维护性
- 优化网络请求策略，减少被封风险
- 改进命令行界面，提供更直观的用户体验
- 更严格的类型检查与代码质量控制

### 修复

- 修复女优ID解析错误问题
- 修复特殊字符导致的文件保存失败
- 解决大批量请求时的内存泄漏问题
- 修复磁力链接提取过程中的解析错误

### 移除

- 移除过时的视频检查站点
- 删除冗余的日志输出

# English

## Development Plan Note

**Note**: Future development plans for this project (including GUI client, web support, database storage, etc.) will be continued in another yet-to-be-disclosed project. We will update this information when the new project is made public.

## [1.2.1] - 2025-05-31

### Added
- Improved Jellyfin metadata generation with clickable links and buttons
- Added MissAV and 123AV watch links to NFO files

### Fixed
- Fixed actress misclassification in author directories
- Optimized poster file structure for better Jellyfin compatibility

### Documentation
- Added information about Jellyfin metadata placeholder MP4 files
- Updated usage instructions for trailer buttons and magnet links

## [1.2.0] - 2025-05-31

### Added

- Added Jellyfin media server metadata generation functionality
  - Support for converting FC2 video analysis results to Jellyfin-compatible NFO files
  - Automatic generation of video poster images (based on thumbnails)
  - Added --jellyfin command line parameter as an optional feature
  - Metadata includes video basic information, video tags, magnet links, and author information
- Optimized file structure to place poster images in the same directory as video files, complying with Jellyfin standards

### Changed

- Removed redundant code and unused methods
- Optimized configuration items and log output

### Fixed

- Fixed various issues and improved configuration

## [1.1.1] - 2025-05-31

### Fixed

- Optimized cache clearing function, added handling for log files currently in use
- Simplified log format by removing module name, function name, and line number for better readability
- Fixed placeholder replacement issue by simplifying step name format for unformatted placeholders in logs
- Optimized logging system architecture using standard Python logging mechanisms
- Added precise timestamp to log filenames for improved uniqueness
- Updated configuration and loggers to use configurable logging parameters for enhanced flexibility
- Optimized log file organization structure for better categorization of different log types
- Removed debug print statements for cleaner code
- Fixed duplicate cache creation issue in batch processing

## [1.1.0] - 2025-05-25

### Added

- Enhanced Japanese translation support with improved Japanese interface
- Added more translation keys to ensure complete multilingual functionality

### Changed

- Optimized internationalization architecture and improved i18n file structure
- Unified translation keys across all language files for consistency
- Updated pyproject.toml, migrated from setuptools to hatchling build system
- Improved build configuration and workflows to ensure correct project metadata
- Added wheel package definition configuration for improved package distribution
- Updated README with clearer installation and usage instructions
- Updated language switching examples in README for more intuitive multilingual usage

### Fixed

- Fixed hardcoded Chinese message issues by replacing with i18n translation functions
- Resolved missing keys in English and Japanese translation files
- Fixed nested curly braces format issues for optimized translation strings
- Fixed leaked video count statistics errors in analysis results
- Fixed log and magnet file saving issues for optimized data saving across different types of crawls
- Updated setup.py package configuration and removed unnecessary references in README

## [1.0.0] - 2025-04-04

### Added

- First public release
- Support for retrieving video lists by author ID
- Support for retrieving video lists by actress ID
- Support for finding and analyzing authors via video ID (`-v ID` parameter)
- Video leak status checking
- Basic statistics functionality
- Command-line interface
- Optimized thread pool management for improved parallel processing efficiency
- Enhanced error handling and retry mechanisms
- Automatic magnet link extraction and verification
- Comprehensive internationalization support (Chinese and English)
- Intelligent caching system to reduce duplicate requests
- Detailed statistical analysis and visualization reports
- Automatic thumbnail downloading and management

### Changed

- Refactored code structure for improved maintainability
- Optimized network request strategies to reduce blocking risks
- Improved command-line interface for a more intuitive user experience
- Stricter type checking and code quality control

### Fixed

- Fixed actress ID parsing errors
- Fixed file saving failures caused by special characters
- Resolved memory leaks during large batch requests
- Fixed parsing errors in magnet link extraction

### Removed

- Removed outdated video checking sites
- Deleted redundant log outputs

# 日本語

## 開発計画について

**注意**: 本プロジェクトの将来の開発計画（GUIクライアント、ウェブサポート、データベースストレージなど）は、まだ公開されていない別のプロジェクトで継続される予定です。新しいプロジェクトが公開された際には、ここで情報を更新します。

## [1.2.1] - 2025-05-31

### 追加
- Jellyfin メタデータ生成機能をクリック可能なリンクとボタンで改善
- NFO ファイルに MissAV と 123AV の視聴リンクを追加

### 修正
- 作者ディレクトリへの女優の誤分類を修正
- Jellyfin との互換性向上のためにポスターファイル構造を最適化

### ドキュメント
- Jellyfin メタデータのプレースホルダー MP4 ファイルに関する情報を追加
- プレビューボタンとマグネットリンクの使用方法に関する説明を更新

## [1.2.0] - 2025-05-31

### 追加

- Jellyfin メディアサーバーのメタデータ生成機能を追加
  - FC2 ビデオ分析結果を Jellyfin 互換の NFO ファイルに変換するサポート
  - ビデオポスター画像の自動生成（サムネイルに基づく）
  - オプション機能として --jellyfin コマンドラインパラメータを追加
  - メタデータにはビデオの基本情報、ビデオタグ、マグネットリンク、作者情報が含まれる
- Jellyfin 標準に準拠するため、ポスター画像をビデオファイルと同じディレクトリに配置するよう最適化

### 変更

- 冗長なコードと未使用のメソッドを削除
- 設定項目とログ出力を最適化

### 修正

- さまざまな問題を修正し、構成を改善

## [1.1.1] - 2025-05-31

### 修正

- キャッシュクリア機能を最適化し、使用中のログファイルの処理を追加
- モジュール名、関数名、行番号を削除してログ形式を簡素化し、読みやすさを向上
- ステップ名の形式を簡素化することでログ内のフォーマットされていないプレースホルダの問題を修正
- 標準的なPythonロギングメカニズムを使用してログシステムアーキテクチャを最適化
- ログファイル名に秒単位のタイムスタンプを追加して一意性を向上
- 構成とロガーを更新し、柔軟性を高めるために設定可能なロギングパラメータを使用
- 異なるタイプのログをより適切に分類するためにログファイルの組織構造を最適化
- デバッグ用のprint文を削除してコードをクリーンアップ
- バッチ処理における重複キャッシュ作成の問題を修正

## [1.1.0] - 2025-05-25

### 追加

- 日本語インターフェースを改善した強化された日本語翻訳サポート
- 多言語機能を完全にするためのより多くの翻訳キーを追加

### 変更

- 国際化アーキテクチャを最適化し、i18nファイル構造を改善
- 一貫性のためにすべての言語ファイルで翻訳キーを統一
- pyproject.tomlを更新し、setuptools からhatchlingビルドシステムに移行
- 正しいプロジェクトメタデータを確保するためのビルド構成とワークフローを改善
- パッケージ配布を改善するためのホイールパッケージ定義設定を追加
- より明確なインストールと使用方法の説明でREADMEを更新
- より直感的な多言語使用のためにREADMEの言語切り替え例を更新

### 修正

- ハードコードされた中国語メッセージの問題をi18n翻訳関数に置き換えて修正
- 英語と日本語の翻訳ファイルで不足しているキーを解決
- 最適化された翻訳文字列のためのネストされた波括弧のフォーマットの問題を修正
- 分析結果での流出ビデオ数の統計エラーを修正
- 異なるタイプのクロールでデータ保存を最適化するためのログとマグネットファイルの保存問題を修正
- setup.pyパッケージ構成を更新し、READMEから不要な参照を削除

## [1.0.0] - 2025-04-04

### 追加

- 最初の公開リリース
- 作者IDによるビデオリスト取得のサポート
- 女優IDによるビデオリスト取得のサポート
- ビデオID（`-v ID`パラメータ）による作者の検索と分析のサポート
- ビデオの流出状態チェック
- 基本的な統計機能
- コマンドラインインターフェース
- 並列処理効率を向上させるための最適化されたスレッドプール管理
- 強化されたエラー処理と再試行メカニズム
- マグネットリンクの自動抽出と検証
- 包括的な国際化サポート（中国語と英語）
- 重複リクエストを削減するためのインテリジェントなキャッシングシステム
- 詳細な統計分析と視覚化レポート
- サムネイルの自動ダウンロードと管理

### 変更

- 保守性向上のためのコード構造のリファクタリング
- ブロックリスクを減らすためのネットワークリクエスト戦略の最適化
- より直感的なユーザーエクスペリエンスのためのコマンドラインインターフェースの改善
- より厳格な型チェックとコード品質管理

### 修正

- 女優ID解析エラーの修正
- 特殊文字によるファイル保存の失敗を修正
- 大量のバッチリクエスト時のメモリリークを解決
- マグネットリンク抽出時の解析エラーを修正

### 削除

- 古いビデオチェックサイトを削除
- 冗長なログ出力を削除
