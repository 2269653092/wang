from typing import Optional
from langchain_core.runnables import Runnable, RunnableConfig
from app.core.state import State
from pydantic import BaseModel
from app.core.settings import get_settings
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

settings = get_settings()

# 初始化语文模式(由助理分担)
llm = ChatOpenAI(
    model=settings.OPENAI_MODEL,
    openai_api_key=settings.OPENAI_API_KEY,
    openai_api_base=settings.OPENAI_BASE_URL if settings.OPENAI_BASE_URL else None,
    temperature=1,
    max_tokens=settings.MAX_TOKENS,  # 限制控制成本的标识
    extra_body=(
        {"thinking": {"type": "disabled"}}
        if settings.OPENAI_DISABLE_THINKING
        else None
    ),
)

class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def __call__(self, state: State, config: Optional[RunnableConfig] = None):
        while True:
            result = self.runnable.invoke(state, config)

            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                break
        return {"messages": result}

# 定义完整 OrEscalate 工具
@tool
def CompleteOrEscalate(reason: str) -> str:
    """标记已完成当前任务或将控制升级到主要助理的工具 。 参数: 原因: 完成或升级的原因 返回: 确认此动作的信息"""
    return f"Task completed/escalated to main assistant. Reason: {reason}"
