"""OS notification bridge. macOS only for the hackathon build (spec's
target laptop); falls back to a log line everywhere else so the rest of
the system never breaks because a notification couldn't be shown.
"""
import platform
import subprocess
import logging

logger = logging.getLogger("nannadesk.notifications")


def notify(title: str, message: str) -> None:
    if platform.system() == "Darwin":
        script = f'display notification {_osa_quote(message)} with title {_osa_quote(title)}'
        try:
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True, timeout=5)
            return
        except Exception as exc:  # pragma: no cover - best-effort OS integration
            logger.warning("osascript notification failed: %s", exc)

    logger.info("[notification] %s: %s", title, message)


def _osa_quote(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
