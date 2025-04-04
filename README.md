# FC2流出检测器 | FC2 Leak Detector

[简体中文](#简体中文) | [English](#english)

## 简体中文

FC2流出检查器是一款专业的内容状态分析工具，基于fc2ppvdb.com的数据库构建。用户只需提供演员ID或作者ID，即可快速获取其作品的完整流出状态报告，同时自动整合高质量预览图和磁力链接资源。工具内置强大的统计分析功能，为用户提供直观详细的数据可视化结果。采用轻量级命令行界面设计，操作简单直观，同时提供丰富的自定义配置选项，满足不同场景下的分析需求。

### 项目声明

**重要：请在使用本工具前仔细阅读以下声明**

1. **项目目的**：本项目是一个技术研究工具，仅用于学术研究、数据分析和技术学习。主要目的是展示如何使用Python进行网络数据分析、多线程处理和结构化数据提取等技术实现。

2. **合法使用**：用户必须在遵守所在地区法律法规的前提下使用本工具。本工具不提供、不存储、不分发任何版权内容，仅提供指向公开索引的元数据信息。

3. **用户责任**：使用者应对自己的行为负责。作者和贡献者不对使用本工具导致的任何法律问题或损失承担责任。使用本工具即表示您已了解并同意承担使用过程中的全部责任。

4. **版权尊重**：本工具仅用于检查内容状态，不鼓励用户获取或分享侵犯版权的内容。请尊重内容创作者的权利，支持正版内容。

5. **数据来源**：本工具使用公开API获取数据，不破解、不绕过任何网站的访问限制。工具中的所有链接均来自公开渠道，不包含任何私密或未经授权的数据源。

6. **许可证**：本项目采用GNU通用公共许可证v3（GNU GPL v3）发布，这意味着您可以自由使用、修改和分发本软件，但需遵循GPL协议的相关规定。详细信息请参阅项目根目录下的LICENSE文件。

### 主要功能

- **视频流出状态检查** - 快速确认视频是否已经在其他网站流出
- **作者/女优作品分析** - 分析特定作者或女优的所有视频状态
- **批量处理** - 同时处理多个作者或女优ID
- **磁力链接搜索** - 自动搜索并提取视频的磁力链接
- **图片下载** - 自动下载视频缩略图
- **详细报告生成** - 生成全面的分析报告，支持文本和JSON格式
- **高效缓存机制** - 智能缓存减少重复请求

### 安装指南

#### 系统要求

- Python 3.8 或更高版本
- 支持的操作系统: Windows, macOS, Linux

#### 步骤一: 获取代码

```bash
git clone https://github.com/soundstarrain/FC2-Leak-Detector.git
cd FC2-Leak-Detector
```

#### 步骤二: 安装依赖

```bash
pip install -r requirements.txt
```

### 使用方法

#### 命令行参数

```bash
python run.py [选项]

选项:
  -h, --help                显示帮助信息
  -c, --config              显示当前配置
  -s, --sites               显示检查站点列表
  -w ID, --writer ID        分析作者ID的视频
  -a ID, --actress ID       分析女优ID的视频
  -b IDS, --batch IDS       批量处理多个作者ID (用逗号分隔)
  -ba IDS, --batch-actress  批量处理多个女优ID (用逗号分隔)
  -e, --extract             提取热门作者列表
  -t NUM, --threads NUM     设置并行线程数 (默认值见配置)
  --no-magnet               不获取磁力链接
  --no-image                不下载视频缩略图
```

#### 示例

```bash
# 分析单个作者的作品
python run.py -w 5656

# 分析单个女优的作品
python run.py -a 5711

# 批量分析多个作者
python run.py -b 5656,3524,4461

# 批量分析多个女优
python run.py -ba 5711,3986,4219

# 提取热门作者列表
python run.py -e

# 使用10个线程分析作者视频
python run.py -w 5656 -t 10

# 分析女优视频但不获取磁力链接
python run.py -a 5711 --no-magnet

# 分析作者视频但不下载缩略图
python run.py -w 5656 --no-image
```

### 配置说明

配置系统已更新为基于类的配置模式，使用`config.py`中的`Config`类管理所有配置项：

| 配置类别 | 参数 | 说明 | 默认值 |
|--------|------|------|--------|
| **网络请求** | max_workers | 最大并行线程数 | 30 |
| | timeout | 请求超时时间(秒) | 15 |
| | max_retries | 最大重试次数 | 4 |
| | page_interval | 分页请求间隔时间范围(秒) | (0.5, 1.2) |
| | request_interval | 普通请求间隔时间范围(秒) | (0.5, 1.0) |
| | retry_base | 重试间隔基数 | 2.0 |
| **缓存设置** | cache_ttl | 缓存有效期(秒) | 172800 (48小时) |
| **存储路径** | cache_dir | 作者和女优ID缓存目录 | data/id_cache |
| | image_dir | 视频缩略图存储目录 | data/img |
| | result_dir | 分析结果存储目录 | data/results |
| | magnet_dir | 磁链信息存储目录 | data/magnets |
| | log_dir | 日志文件存储目录 | data/logs |
| **输出设置** | save_format | 保存格式 | ["text", "json"] |
| | report_batch_size | 报告中每批显示的视频数量 | 100 |
| **高级设置** | log_level | 日志级别 | INFO |
| | enable_proxy | 是否启用代理 | false |
| | user_agents | 浏览器标识轮换列表 | [多种用户代理] |

### 目录结构

```
FC2-Leak-Detector/
├── src/                 # 源代码目录
│   ├── checkers/        # 视频检查模块
│   ├── writers/         # 作者信息模块
│   ├── utils/           # 工具模块
│   └── __init__.py      # 包初始化文件
├── data/                # 数据存储目录(自动创建)
│   ├── id_cache/        # ID缓存目录
│   ├── results/         # 结果保存目录
│   ├── img/             # 图片保存目录
│   ├── magnets/         # 磁链缓存目录
│   └── logs/            # 日志目录
├── i18n/                # 国际化语言文件
│   ├── en.json          # 英文语言文件
│   └── zh.json          # 中文语言文件
├── .github/             # GitHub配置
│   └── workflows/       # GitHub工作流
├── run.py               # 程序启动入口
├── main.py              # 主程序代码
├── config.py            # 配置文件
├── requirements.txt     # 基本依赖列表
├── requirements-dev.txt # 开发环境依赖
├── pyproject.toml       # 项目配置文件
├── .gitignore           # Git忽略文件
├── .editorconfig        # 编辑器配置
├── .pre-commit-config.yaml # 预提交钩子配置
├── CHANGELOG.md         # 更新日志
├── CONTRIBUTING.md      # 贡献指南
├── LICENSE              # 许可证文件
└── README.md            # 说明文档
```

### 常见问题

#### 如何找到作者ID或女优ID?

女优ID可以从fc2ppvdb.com网站的URL中找到。例如:
- 女优页面URL: `.../actress/6789` 中的 `6789` 即为女优ID
作者ID由于没有明文在网页中显示，用户可以选取任意一个该作者的FC2视频ID采用-v id的命令行格式直接获取该作者的视频，无需提供具体id

#### 分析速度很慢怎么办?

- 增加并行线程数 (`-t` 参数或修改配置文件中的`max_workers`值)
- 减少分析视频数量
- 确保网络连接稳定
- 禁用磁链搜索和图片下载 (`--no-magnet --no-image` 参数)

#### 为什么有些视频显示"检查失败"?

检查失败可能由以下原因导致:
- 网络连接问题
- 检查站点暂时不可用
- 请求被目标站点拒绝
- 视频ID格式不正确

#### 如何清除缓存?

手动删除 `data` 目录下的相应缓存文件夹，或使用以下命令:

```bash
python run.py --clear-cache
```

### 注意事项

1. 本工具仅用于学术研究和个人学习，请勿用于任何商业或非法用途
2. 请勿频繁大量请求，以免IP被封禁
3. 遵守相关法律法规，尊重内容版权
4. 不要分享或传播通过本工具获取的任何可能侵犯版权的内容
5. **特别提示：中国大陆用户需确保网络环境可正常访问国际互联网，以便连接本工具依赖的各项在线服务**

## English

FC2 Leak Detector is a professional content status analysis tool built on the fc2ppvdb.com database. Users only need to provide an actress ID or author ID to quickly obtain a complete status report of their works, while automatically integrating high-quality preview images and magnet link resources. The tool has built-in powerful statistical analysis functions, providing users with intuitive and detailed data visualization results. Designed with a lightweight command-line interface, it is simple and intuitive to operate, while providing rich customization options to meet analysis needs in different scenarios.

### Project Disclaimer

**Important: Please read the following disclaimer carefully before using this tool**

1. **Project Purpose**: This project is a technical research tool intended solely for academic research, data analysis, and technical learning. Its primary purpose is to demonstrate how to implement technologies such as network data analysis, multi-threading, and structured data extraction using Python.

2. **Legal Use**: Users must comply with all applicable laws and regulations in their jurisdiction when using this tool. This tool does not provide, store, or distribute any copyrighted content, but only offers metadata information pointing to publicly indexed resources.

3. **User Responsibility**: Users are responsible for their own actions. The authors and contributors are not liable for any legal issues or damages resulting from the use of this tool. By using this tool, you acknowledge and agree to assume full responsibility for your actions.

4. **Copyright Respect**: This tool is intended only for checking content status and does not encourage users to obtain or share copyright-infringing content. Please respect the rights of content creators and support official content.

5. **Data Sources**: This tool uses publicly available APIs to obtain data and does not crack or bypass any website's access restrictions. All links in the tool come from public channels and do not contain any private or unauthorized data sources.

6. **License**: This project is released under the GNU General Public License v3 (GNU GPL v3), which means you are free to use, modify, and distribute this software, subject to the terms of the GPL. Please refer to the LICENSE file in the project root directory for detailed information.

### Key Features

- **Video Status Check** - Quickly confirm if videos have been leaked on other websites
- **Author/Actress Works Analysis** - Analyze the status of all videos by specific authors or actresses
- **Batch Processing** - Process multiple author or actress IDs simultaneously
- **Magnet Link Search** - Automatically search and extract video magnet links
- **Image Download** - Automatically download video thumbnails
- **Detailed Report Generation** - Generate comprehensive analysis reports, supporting text and JSON formats
- **Efficient Caching** - Smart caching to reduce duplicate requests

### Installation Guide

#### System Requirements

- Python 3.8 or higher
- Supported Operating Systems: Windows, macOS, Linux

#### Step 1: Get the Code

```bash
git clone https://github.com/soundstarrain/FC2-Leak-Detector.git
cd FC2-Leak-Detector
```

#### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Usage

#### Command Line Arguments

```bash
python run.py [options]

Options:
  -h, --help                Show help information
  -c, --config              Show current configuration
  -s, --sites               Show check site list
  -w ID, --writer ID        Analyze videos by author ID
  -a ID, --actress ID       Analyze videos by actress ID
  -b IDS, --batch IDS       Batch process multiple author IDs (comma separated)
  -ba IDS, --batch-actress  Batch process multiple actress IDs (comma separated)
  -e, --extract             Extract popular author list
  -t NUM, --threads NUM     Set parallel thread count (default in config)
  --no-magnet               Don't fetch magnet links
  --no-image                Don't download video thumbnails
```

#### Examples

```bash
# Analyze a single author's works
python run.py -w 5656

# Analyze a single actress's works
python run.py -a 5711

# Batch analyze multiple authors
python run.py -b 5656,3524,4461

# Batch analyze multiple actresses
python run.py -ba 5711,3986,4219

# Extract popular author list
python run.py -e

# Analyze author videos with 10 threads
python run.py -w 5656 -t 10

# Analyze actress videos without magnet links
python run.py -a 5711 --no-magnet

# Analyze author videos without thumbnails
python run.py -w 5656 --no-image
```

### Configuration

The configuration system has been updated to a class-based model using the `Config` class in `config.py`:

| Category | Parameter | Description | Default Value |
|--------|------|------|--------|
| **Network Settings** | max_workers | Maximum parallel threads | 30 |
| | timeout | Request timeout (seconds) | 15 |
| | max_retries | Maximum retry attempts | 4 |
| | page_interval | Page request interval range (seconds) | (0.5, 1.2) |
| | request_interval | Normal request interval range (seconds) | (0.5, 1.0) |
| | retry_base | Retry interval base | 2.0 |
| **Cache Settings** | cache_ttl | Cache validity period (seconds) | 172800 (48 hours) |
| **Storage Paths** | cache_dir | ID cache directory | data/id_cache |
| | image_dir | Images save directory | data/img |
| | result_dir | Results save directory | data/results |
| | magnet_dir | Magnet cache directory | data/magnets |
| | log_dir | Log directory | data/logs |
| **Output Settings** | save_format | Save format | ["text", "json"] |
| | report_batch_size | Videos per batch in reports | 100 |
| **Advanced Settings** | log_level | Log level | INFO |
| | enable_proxy | Whether to use a proxy | false |
| | user_agents | Browser user agent rotation list | [various agents] |

### Directory Structure

```
FC2-Leak-Detector/
├── src/                 # Source code directory
│   ├── checkers/        # Video check modules
│   ├── writers/         # Author information modules
│   ├── utils/           # Utility modules
│   └── __init__.py      # Package initialization file
├── data/                # Data storage directory (auto-created)
│   ├── id_cache/        # ID cache directory
│   ├── results/         # Results save directory
│   ├── img/             # Images save directory
│   ├── magnets/         # Magnet cache directory
│   └── logs/            # Log directory
├── i18n/                # Internationalization language files
│   ├── en.json          # English language file
│   └── zh.json          # Chinese language file
├── .github/             # GitHub configuration
│   └── workflows/       # GitHub workflows
├── run.py               # Program entry point
├── main.py              # Main program code
├── config.py            # Configuration file
├── requirements.txt     # Basic dependency list
├── requirements-dev.txt # Development dependencies
├── pyproject.toml       # Project configuration file
├── .gitignore           # Git ignore file
├── .editorconfig        # Editor configuration
├── .pre-commit-config.yaml # Pre-commit hook configuration
├── CHANGELOG.md         # Update log
├── CONTRIBUTING.md      # Contribution guidelines
├── LICENSE              # License file
└── README.md            # Documentation
```

### FAQ

#### How to Find Author ID or Actress ID?

Actress ID can be found in the URL of fc2ppvdb.com website. For example:
- Actress page URL: `.../actress/6789` where `6789` is the actress ID
Author ID is not explicitly displayed on the webpage. Users can select any FC2 video ID from that author and use the -v id command line format to directly get videos from that author without providing a specific id.

#### What If Analysis is Slow?

- Increase parallel thread count (`-t` parameter or modify `max_workers` in config)
- Reduce the number of videos to analyze
- Ensure network connection is stable
- Disable magnet search and image download (`--no-magnet --no-image` parameters)

#### Why Do Some Videos Show "Check Failed"?

Check failures may be caused by:
- Network connection issues
- Check site temporarily unavailable
- Request rejected by target site
- Incorrect video ID format

#### How to Clear Cache?

Manually delete respective cache folders in the `data` directory, or use:

```bash
python run.py --clear-cache
```

### Notes

1. This tool is for academic research and personal learning only, not for any commercial or illegal purposes
2. Avoid frequent mass requests to prevent IP blocking
3. Comply with relevant laws and regulations, respect content copyright
4. Do not share or distribute any potentially copyright-infringing content obtained through this tool
5. **Important Note: Users in mainland China need to ensure proper access to the global internet to connect with online services required by this tool**

