"""简单的 hook 注册器。

为什么不用 pluggy / 类似框架：
- 本仓库 hook 数量小（< 10），透明度优先。
- 自家注册器更容易在 evidence 日志里追踪每次 hook 触发。
"""
from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from src.utils.logger import log_event


@dataclass
class HookSpec:
    name: str
    event: str
    callable: Callable
    blocking: bool
    description: str


_registry: dict[str, list[HookSpec]] = defaultdict(list)


def register(*, name: str, event: str, blocking: bool, description: str):
    def deco(fn: Callable):
        _registry[event].append(
            HookSpec(name=name, event=event, callable=fn, blocking=blocking, description=description)
        )
        return fn

    return deco


class HookBlocked(RuntimeError):
    """Hook 显式拒绝。pipeline 不应继续。"""

    def __init__(self, hook_name: str, reason: str, payload: dict | None = None):
        super().__init__(f"[hook:{hook_name}] BLOCKED — {reason}")
        self.hook_name = hook_name
        self.reason = reason
        self.payload = payload or {}


def run(event: str, ctx: dict) -> None:
    """执行某个 event 上注册的所有 hook。任意 blocking hook 抛 HookBlocked → 立即中断。"""
    for spec in _registry.get(event, []):
        if _is_disabled(spec.name):
            log_event("hook_skipped_disabled", {"hook": spec.name, "event": event})
            continue
        try:
            spec.callable(ctx)
            log_event("hook_ok", {"hook": spec.name, "event": event})
        except HookBlocked as e:
            log_event(
                "hook_block",
                {
                    "hook": e.hook_name,
                    "event": event,
                    "reason": e.reason,
                    "payload_keys": list(e.payload.keys()),
                },
            )
            if spec.blocking:
                raise
            # 非 blocking → 仅 warn 不中断


def _is_disabled(name: str) -> bool:
    """通过环境变量 GODCOMMENT_DISABLE_HOOKS=hook1,hook2 临时关闭。"""
    raw = os.environ.get("GODCOMMENT_DISABLE_HOOKS", "")
    return name in {x.strip() for x in raw.split(",") if x.strip()}


def list_hooks() -> list[str]:
    return list(_registry.keys())


def list_hook_specs() -> list[HookSpec]:
    return [s for items in _registry.values() for s in items]
