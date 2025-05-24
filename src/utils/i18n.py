"""
FC2 视频分析器 - 国际化支持模块

此模块提供多语言支持功能，使程序能够根据用户设置显示不同语言的界面。
目前支持中文、英文和日文三种语言。
"""

import json
import locale
import os

from loguru import logger

# 默认语言
DEFAULT_LANGUAGE = "zh"

# 支持的语言列表
SUPPORTED_LANGUAGES = ["zh", "en", "ja"]

# 当前语言
current_language = None

# 翻译字典
translations = {}


def load_language_file(lang_code):
    """
    加载指定语言的翻译文件

    参数:
        lang_code: 语言代码，如'zh', 'en', 'ja'

    返回:
        dict: 翻译字典，如果加载失败则返回空字典
    """
    try:
        # 获取语言文件路径
        lang_file = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ),
            "i18n",
            f"{lang_code}.json",
        )

        # 检查文件是否存在
        if not os.path.exists(lang_file):
            logger.warning(f"语言文件不存在: {lang_file}")
            return {}

        # 加载语言文件
        with open(lang_file, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        logger.error(f"加载语言文件失败: {e}")
        return {}


def initialize(language=None):
    """
    初始化国际化模块

    参数:
        language: 指定语言代码，如果为None则尝试自动检测系统语言

    返回:
        str: 当前使用的语言代码
    """
    global current_language, translations

    # 如果未指定语言，尝试获取系统语言
    if language is None:
        try:
            system_locale, _ = locale.getdefaultlocale()
            if system_locale:
                system_lang = system_locale.split("_")[0].lower()
                if system_lang in SUPPORTED_LANGUAGES:
                    language = system_lang
        except Exception as e:
            logger.warning(f"获取系统语言失败: {e}")

    # 如果仍然没有确定语言，使用默认语言
    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE

    # 加载语言文件
    translations = load_language_file(language)
    current_language = language

    logger.info(f"已加载语言: {language}")
    return current_language


def get_text(key, default=None):
    """
    获取指定键的翻译文本

    参数:
        key: 翻译键
        default: 如果翻译不存在，返回的默认值

    返回:
        str: 翻译文本，如果不存在则返回default值
    """
    # 确保已初始化
    if current_language is None:
        initialize()

    # 获取翻译
    return translations.get(key, default if default is not None else key)


def get_current_language():
    """
    获取当前使用的语言代码

    返回:
        str: 当前语言代码
    """
    # 确保已初始化
    if current_language is None:
        initialize()

    return current_language


def switch_language(language):
    """
    切换到指定语言

    参数:
        language: 目标语言代码

    返回:
        bool: 是否成功切换
    """
    global current_language, translations

    # 检查是否支持目标语言
    if language not in SUPPORTED_LANGUAGES:
        logger.warning(f"不支持的语言: {language}")
        return False

    # 如果已经是当前语言，无需切换
    if language == current_language:
        return True

    # 加载新语言文件
    new_translations = load_language_file(language)
    if not new_translations:
        logger.error(f"切换语言失败: 无法加载语言文件 {language}")
        return False

    # 更新全局变量
    translations = new_translations
    current_language = language

    logger.info(f"已切换语言: {language}")
    return True


# 简写函数 - 更简洁的调用方式
_ = get_text
