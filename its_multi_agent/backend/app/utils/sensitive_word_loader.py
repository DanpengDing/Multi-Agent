"""
敏感词加载器模块。

支持从 JSON 文件加载敏感词库，提供热更新能力。
"""
import json
import threading
from pathlib import Path
from typing import TypedDict


class SensitiveWordLoader:
    """敏感词加载器，支持热更新。"""

    def __init__(self, json_path: str):
        """
        初始化加载器。

        Args:
            json_path: sensitive_words.json 文件路径
        """
        self._path = Path(json_path)
        self._common_words: set[str] = set()
        self._business_words: set[str] = set()
        self._last_mtime: float = 0
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        """从 JSON 文件加载敏感词。"""
        if not self._path.exists():
            self._common_words = set()
            self._business_words = set()
            return

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)

            common_list = data.get("common", [])
            business_list = data.get("business", [])

            with self._lock:
                self._common_words = set(common_list)
                self._business_words = set(business_list)

            self._last_mtime = self._path.stat().st_mtime
        except (json.JSONDecodeError, IOError) as e:
            print(f"加载敏感词文件失败: {e}")
            with self._lock:
                self._common_words = set()
                self._business_words = set()

    def get_common_words(self) -> set[str]:
        """获取通用敏感词集合。"""
        with self._lock:
            return self._common_words.copy()

    def get_business_words(self) -> set[str]:
        """获取业务敏感词集合。"""
        with self._lock:
            return self._business_words.copy()

    def check_and_reload(self) -> bool:
        """
        检查文件是否变化，如变化则重新加载。

        Returns:
            True if reloaded, False otherwise
        """
        try:
            current_mtime = self._path.stat().st_mtime
            if current_mtime > self._last_mtime:
                self._load()
                return True
        except OSError:
            pass
        return False


# 全局加载器实例（延迟初始化）
_loader: "SensitiveWordLoader | None" = None


def get_word_loader() -> SensitiveWordLoader:
    """获取全局敏感词加载器。"""
    global _loader
    if _loader is None:
        base_dir = Path(__file__).resolve().parent.parent
        json_path = base_dir / "data" / "sensitive_words.json"
        _loader = SensitiveWordLoader(str(json_path))
    return _loader
