# 客户_支助_聊天/申请/服务/助理/woocommerce_助理.py

from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from app.tools.woocommerce import (
    search_products,
    search_orders,
)
from app.assistants.assistant_base import Assistant, llm, CompleteOrEscalate
from app.core.logger import logger
from pydantic import BaseModel, Field

# 定义 WooCommerce 的任务授权工具
class ToWooCommerceProducts(BaseModel):
    """转到专门助理处理WooCommerce产品搜索的工作。"""
    query: str = Field(description="The search query for products (e.g., product name, category).")

class ToWooCommerceOrders(BaseModel):
    """转到专门助理处理WooCommerce订单搜查的工作。"""
    search_type: str = Field(description="The type of search to perform. Must be one of: 'email', 'name', or 'id'.")
    search_value: str = Field(description="The value to search for. For email searches, provide the customer's email address. For name searches, provide the customer's full name. For ID searches, provide the order ID.")

# WooCommerce 助理助手提示提示
woocommerce_assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a specialized assistant for WooCommerce operations. "
            "Your primary role is to search for products and orders using the provided tools. "
            "When a user asks for product searches, immediately use the search_products tool. "
            "When a user asks for order searches, you MUST FIRST ask them to provide either their email address or full name to verify their identity before searching for orders. "
            "NEVER search for orders without proper verification information (email or name). "
            "If the user only says '查找订单' or similar without providing verification, politely ask them to provide their email address or full name. "
            "If they provide an email, use the search_orders tool with search_type='email' and their email as search_value. "
            "If they provide a name, use the search_orders tool with search_type='name' and their full name as search_value. "
            "If they provide an order ID, use the search_orders tool with search_type='id' and the ID as search_value. "
            "If a search returns no results, explain that no matching items were found and offer to try a different search method. "
            "If a tool call fails with timeout or connection errors, explain to the user that the server may be busy and suggest trying again. "
            "Always provide clear and concise information to the user based on the tool results. "
            "If the user's request is outside the scope of product or order searches, "
            "use the CompleteOrEscalate tool to return control to the main assistant. "
            "Current time: {time}.",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now())

# WooCommerce 辅助工具
woocommerce_assistant_tools = [
    search_products,
    search_orders,
    CompleteOrEscalate,
]

# 创建可运行的 WooCommerce 助理助手
woocommerce_assistant_runnable = woocommerce_assistant_prompt | llm.bind_tools(woocommerce_assistant_tools)

# 证明伍商助理
woocommerce_assistant = Assistant(woocommerce_assistant_runnable)