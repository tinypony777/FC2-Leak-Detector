"""
FC2ビデオアナライザー - 国際化サポートモジュール

ユーザー設定に基づいて表示言語を切り替える多言語機能を提供します。
現在は中国語・英語・日本語に対応しています。
"""

import json
import locale
import os
import logging
from pathlib import Path

from loguru import logger

# 默认语言
DEFAULT_LANGUAGE = "zh"

# 支持的语言列表
SUPPORTED_LANGUAGES = ["zh", "en", "ja"]

# 当前语言
current_language = None

# 翻译字典
translations = {}

# 获取i18n目录路径
I18N_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "i18n",
)

# 用户偏好文件
USER_PREFS_FILE = os.path.join(I18N_DIR, "preference.json")

# 确保i18n目录存在
os.makedirs(I18N_DIR, exist_ok=True)


def load_language_file(lang_code):
    """
    指定された言語コードのファイルを読み込む

    Args:
        lang_code: "zh"、"en"、"ja" などの言語コード

    Returns:
        dict: 翻訳辞書。失敗した場合は None
    """
    try:
        # 获取语言文件路径
        lang_file = os.path.join(I18N_DIR, f"{lang_code}.json")
        
        # 检查文件是否存在
        if not os.path.exists(lang_file):
            logger.warning(f"语言文件不存在: {lang_file}")
            return None
            
        # 读取语言文件
        with open(lang_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"语言文件格式错误: {lang_code}.json - {e}")
        return None
    except Exception as e:
        logger.error(f"加载语言文件失败: {e}")
        return None


def save_language_preference(language):
    """
    ユーザーの言語設定を保存する

    Args:
        language: 言語コード

    Returns:
        bool: 保存に成功したかどうか
    """
    try:
        with open(USER_PREFS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"language": language}, f)
        logger.debug(f"已保存语言偏好: {language}")
        return True
    except Exception as e:
        logger.error(f"保存语言偏好失败: {e}")
        return False


def load_language_preference():
    """
    ユーザーの言語設定を読み込む

    Returns:
        str: 言語コード。未設定または失敗時は None
    """
    try:
        if os.path.exists(USER_PREFS_FILE):
            with open(USER_PREFS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                language = data.get("language")
                logger.debug(f"已加载语言偏好: {language}")
                return language
    except Exception as e:
        logger.debug(f"加载语言偏好失败: {e}")
    return None


def check_translation_completeness():
    """
    すべての言語ファイルが揃っているか確認する

    Returns:
        dict: 各言語で欠けているキー {lang: [missing_keys]}
    """
    try:
        # 加载所有语言文件
        lang_files = {}
        for lang in SUPPORTED_LANGUAGES:
            lang_data = load_language_file(lang)
            if lang_data:
                lang_files[lang] = lang_data
        
        # 收集所有键
        all_keys = set()
        for lang, data in lang_files.items():
            keys = set(_extract_all_keys(data))
            all_keys.update(keys)
        
        # 检查每个语言文件是否包含所有键
        missing_keys = {}
        for lang, data in lang_files.items():
            lang_keys = set(_extract_all_keys(data))
            missing = all_keys - lang_keys
            if missing:
                missing_keys[lang] = list(missing)
        
        return missing_keys
    except Exception as e:
        logger.error(f"检查翻译完整性失败: {e}")
        return {}


def _extract_all_keys(data, prefix=""):
    """
    翻訳辞書から再帰的に全てのキーを取得する

    Args:
        data: 翻訳辞書
        prefix: キーの接頭辞

    Returns:
        list: すべてのキー
    """
    keys = []
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys.extend(_extract_all_keys(value, full_key))
        else:
            keys.append(full_key)
    return keys


def initialize(language=None):
    """
    国際化モジュールを初期化する

    Args:
        language: 指定する言語コード。None の場合はシステム言語を自動検出

    Returns:
        str: 使用中の言語コード
    """
    global current_language, translations

    # 首先尝试加载用户偏好的语言
    if language is None:
        lang_pref = load_language_preference()
        if lang_pref:
            language = lang_pref

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

    # 如果加载失败，尝试加载默认语言
    if not translations and language != DEFAULT_LANGUAGE:
        logger.warning(f"加载语言 {language} 失败，尝试加载默认语言 {DEFAULT_LANGUAGE}")
        translations = load_language_file(DEFAULT_LANGUAGE)
        current_language = DEFAULT_LANGUAGE
    
    # 如果还是加载失败，使用空字典
    if not translations:
        logger.error(f"加载默认语言 {DEFAULT_LANGUAGE} 失败，使用空翻译字典")
        translations = {}

    logger.info(f"已加载语言: {current_language}")
    return current_language


def get_text(key, default=None):
    """
    获取指定键的翻译文本，支持嵌套对象的点表示法

    参数:
        key: 翻译键，如'config.max_workers'或'main_menu.title'
        default: 如果翻译不存在，返回的默认值

    返回:
        str: 翻译文本，如果不存在则返回default值
    """
    # 确保已初始化
    if current_language is None:
        initialize()

    # 处理嵌套键
    if '.' in key:
        parts = key.split('.')
        current = translations
        
        # 逐级查找嵌套对象
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                # 如果任何一级查找失败，记录日志并返回默认值
                if default is None:
                    logger.debug(f"翻译键不存在: {key} (语言: {current_language})")
                return default if default is not None else key
        
        return current
    else:
        # 直接查找键
        result = translations.get(key)
        if result is None:
            if default is None:
                logger.debug(f"翻译键不存在: {key} (语言: {current_language})")
            return default if default is not None else key
        return result


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
    
    # 保存用户语言偏好
    save_language_preference(language)

    logger.info(f"已切换语言: {language}")
    return True


# 简写函数 - 更简洁的调用方式
_ = get_text

# 在模块加载时检查翻译完整性(仅在调试模式下)
if os.environ.get("FC2_DEBUG") == "1":
    missing_keys = check_translation_completeness()
    if missing_keys:
        logger.warning("翻译文件不完整:")
        for lang, keys in missing_keys.items():
            logger.warning(f"  {lang}: 缺少 {len(keys)} 个键")
            if len(keys) <= 10:
                for key in keys:
                    logger.warning(f"    - {key}")
            else:
                for key in keys[:10]:
                    logger.warning(f"    - {key}")
                logger.warning(f"    ... 以及其他 {len(keys) - 10} 个键")
