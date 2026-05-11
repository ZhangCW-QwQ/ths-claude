"""Hooks 包：通过 import 触发自注册。

注册顺序很重要 —— guard 类 hook 必须先于"决策"类 hook 注册。
hooks.config.yaml 是真正的"运行时面板"，告诉 ops 如何在不改代码的情况下临时禁用某个 hook。
"""
from . import registry  # noqa: F401  # init the registry
from . import pre_generation_injection_guard  # noqa: F401
from . import pre_publish_safety_gate  # noqa: F401
from . import prompt_secret_leak_guard  # noqa: F401
