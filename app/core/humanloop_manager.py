# 人类管理者。 py
import os
from gohumanloop  import DefaultHumanLoopManager , APIProvider
#from gohumanloop import   APIProvider
from gohumanloop.adapters.langgraph_adapter import HumanloopAdapter
from gohumanloop.providers.terminal_provider import TerminalProvider 
from gohumanloop.utils import get_secret_from_env

# GOHUNLOU 初始化人类操作管理器和人类操作设计师
# 为避免循环进口,在单独的档案中这样做。
# humanloop_manager = DefaultHumanLoopManager(
#     initial_providers=TerminalProvider(name="TerminalProvider")
# )
# humanloop_adapter = HumanloopAdapter(humanloop_manager, default_timeout=60)

# 创建 GoHumanLoopManager 实例
humanloop_manager = DefaultHumanLoopManager(
    APIProvider(
        name="ApiProvider",
        api_base_url="http://127.0.0.1:9800/api", # 换成自己飞书应用的URL
        api_key=get_secret_from_env("GOHUMANLOOP_API_KEY"),  # 从_env ("GOHUMANLOOP_API_KEY")获得机密),
        default_platform="feishu"
    )
)
# 创建 LangGraphAdapter 实例
humanloop_adapter = HumanloopAdapter(
    manager=humanloop_manager,
    default_timeout=300,  # 默认超时时间为5分钟
)
