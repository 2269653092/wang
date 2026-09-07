from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import tools_condition
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage

# GohenLoop 进口(移到 humanloop_manager.py 以避免循环进口)
# from gohumanloop.core.manager import DefaultHumanLoopManager
# from gohumanloop.adapters.langgraph_adapter import HumanloopAdapter
# from gohumanloop.providers.terminal_provider import TerminalProvider
from app.core.humanloop_manager import humanloop_adapter

from app.core.state import State
from app.core.logger import logger
from app.utils import (
  create_tool_node_with_fallback,
  flight_info_to_string,
  create_entry_node,
)
from app.tools.flights import fetch_user_flight_information
# 进口护卫车代理商
from app.guardrails.guardrail_agents import (
    jailbreak_guardrail_agent,
    jailbreak_guardrail_agent_instructions,
    relevance_guardrail_agent,
    relevance_guardrail_agent_instructions,
)
from app.assistants.assistant_base import (
  Assistant,
  CompleteOrEscalate,
  llm,
)
# 进口新助理及其工具
from app.assistants.woocommerce_assistant import (
  woocommerce_assistant,
  ToWooCommerceProducts,
  ToWooCommerceOrders,
)
from app.tools.woocommerce import (
  search_products,
  search_orders,
)
from app.tools.forms import submit_form
from app.assistants.form_submission_assistant import (
  form_submission_assistant,
  ToFormSubmission,
)

from app.assistants.primary_assistant import (
  primary_assistant,
  primary_assistant_tools,
  ToFlightBookingAssistant,
  ToBookCarRental,
  ToHotelBookingAssistant,
  ToBookExcursion,
)
from app.assistants.flight_booking_assistant import (
  flight_booking_assistant,
  update_flight_safe_tools,
  update_flight_sensitive_tools,
)
from app.assistants.car_rental_assistant import (
  car_rental_assistant,
  book_car_rental_safe_tools,
  book_car_rental_sensitive_tools,
)
from app.assistants.hotel_booking_assistant import (
  hotel_booking_assistant,
  book_hotel_safe_tools,
  book_hotel_sensitive_tools,
)
from app.assistants.excursion_assistant import (
  excursion_assistant,
  book_excursion_safe_tools,
  book_excursion_sensitive_tools,
)

# GOHUNLOU 初始化人类操作管理器和人类操作设计师
# humanloop_manager = DefaultHumanLoopManager(
#     initial_providers=TerminalProvider(name="TerminalProvider")
# )
# humanloop_adapter = HumanloopAdapter(humanloop_manager, default_timeout=60)
# 移至humanloop_manager.py, 以避免循环导入

# 初始化图形
builder = StateGraph(State)

def user_info(state: State, config: RunnableConfig):
  # 获取用户飞行信息
  flight_info = fetch_user_flight_information.invoke(input={}, config=config)
  user_info_str = flight_info_to_string(flight_info)
  return {"user_info": user_info_str}

builder.add_node("fetch_user_info", user_info)

# - 保安警卫车节点...
def guardrail_check(state: State, config: RunnableConfig):
    """检查用户输入的安全性和相关性的节点 。"""
    # 获取最新的用户消息
    # 假设在这种情况下最后一条电文总是来自用户
    user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    if not user_messages:
        logger.warning("No user message found for guardrail check. Allowing.")
        return {
            "messages": [HumanMessage(content="No user input to check. Please provide a query.")]
        }
    
    latest_user_message = user_messages[-1]
    user_input = latest_user_message.content
    
    logger.info(f"🛡️ Checking safety and relevance for user input: '{user_input}'")
    
    # 1. 检查越狱未遂情况
    jailbreak_prompt = f"{jailbreak_guardrail_agent_instructions}\n\nUser Input: {user_input}"
    jailbreak_result = jailbreak_guardrail_agent.invoke(jailbreak_prompt)
    
    if not jailbreak_result.is_safe:
        logger.warning(f"🚨 Jailbreak attempt detected: {jailbreak_result.reasoning}")
        return {
            "messages": [HumanMessage(content=f"I cannot assist with that request. Reason: {jailbreak_result.reasoning}")]
        }

    # 2. 核实相关性
    relevance_prompt = f"{relevance_guardrail_agent_instructions}\n\nUser Input: {user_input}"
    relevance_result = relevance_guardrail_agent.invoke(relevance_prompt)
    
    if not relevance_result.is_relevant:
        logger.warning(f"⚠️ Irrelevant input detected: {relevance_result.reasoning}")
        # 目前,我们仍允许继续对话,但将问题记录下来。
        # 这可以更改为回信, 如果需要, 结束对话 。
        # 返回 {
        # “ 消息” : [HumanMessage( content=f) 我只能帮助查询有关航班、 旅馆、 汽车租赁、 游览、 电子商务和表格。 您的询问似乎无关。 原因 : { 相关_ 结果. 理由} ]
        # }
        
    # 如果两次检查都通过,输入是安全的(至少可能)相关的。
    logger.info("✅ Input passed safety and relevance checks.")
    return {"messages": []} # 没有新信件要添加, 只要继续

builder.add_node("guardrail_check", guardrail_check)

# -- -- 图边 -- --
builder.add_edge(START, "fetch_user_info")
builder.add_edge("fetch_user_info", "guardrail_check")

# 飞行预订助理
builder.add_node(
  "enter_update_flight",
  create_entry_node("Flight Updates & Booking Assistant", "update_flight"),
)
builder.add_node("update_flight", flight_booking_assistant)
builder.add_edge("enter_update_flight", "update_flight")
builder.add_node(
  "update_flight_safe_tools",
  create_tool_node_with_fallback(update_flight_safe_tools),
)
builder.add_node(
  "update_flight_sensitive_tools",
  create_tool_node_with_fallback(update_flight_sensitive_tools),
)

def route_update_flight(state: State) -> Literal[
  "update_flight_safe_tools",
  "update_flight_sensitive_tools",
  "primary_assistant",
  "__end__",
]:
  route = tools_condition(state)
  if route == END:
      return END
  tool_calls = state["messages"][-1].tool_calls
  safe_toolnames = [t.name for t in update_flight_safe_tools]
  if all(tc["name"] in safe_toolnames for tc in tool_calls):
      return "update_flight_safe_tools"
  return "update_flight_sensitive_tools"

# 用于检查是否执行 Complete OrEscalate 的助手功能
def should_route_to_primary(state: State) -> bool:
    if state["messages"] and len(state["messages"]) > 0:
        last_message = state["messages"][-1]
        # 检查最后一个信件是否是包含完整 OrEscalate 结果的工具响应
        if hasattr(last_message, 'content') and isinstance(last_message.content, str):
            return 'Task completed/escalated to main assistant' in last_message.content
    return False

# 工具执行结果路线功能
def route_update_flight_tools(state: State) -> Literal["update_flight", "primary_assistant"]:
    return "primary_assistant" if should_route_to_primary(state) else "update_flight"

def route_car_rental_tools(state: State) -> Literal["book_car_rental", "primary_assistant"]:
    return "primary_assistant" if should_route_to_primary(state) else "book_car_rental"

def route_hotel_tools(state: State) -> Literal["book_hotel", "primary_assistant"]:
    return "primary_assistant" if should_route_to_primary(state) else "book_hotel"

def route_excursion_tools(state: State) -> Literal["book_excursion", "primary_assistant"]:
    return "primary_assistant" if should_route_to_primary(state) else "book_excursion"

# WooCommerce 助理
builder.add_node(
  "enter_woocommerce",
  create_entry_node("WooCommerce Assistant", "woocommerce"),
)
builder.add_node("woocommerce", woocommerce_assistant)
builder.add_edge("enter_woocommerce", "woocommerce")
builder.add_node(
  "woocommerce_safe_tools",
  create_tool_node_with_fallback([search_products, search_orders, CompleteOrEscalate]), # 包含 WooCommerce 工具
)

def route_woocommerce(state: State) -> Literal[
  "woocommerce_safe_tools",
  "primary_assistant",
  "__end__",
]:
  route = tools_condition(state)
  if route == END:
      return END
  return "woocommerce_safe_tools"

def route_woocommerce_tools(state: State) -> Literal["woocommerce", "primary_assistant"]:
    logger.info(f"🤖 WooCommerce tools routing check")
    if should_route_to_primary(state):
        logger.info(f"➡️ Routing from WooCommerce tools back to primary assistant")
        return "primary_assistant"
    else:
        logger.info(f"➡️ Routing from WooCommerce tools back to WooCommerce assistant")
        return "woocommerce"

builder.add_conditional_edges("woocommerce_safe_tools", route_woocommerce_tools)
builder.add_conditional_edges("woocommerce", route_woocommerce)

# 表格提交助理
builder.add_node(
  "enter_form_submission",
  create_entry_node("Form Submission Assistant", "form_submission"),
)
builder.add_node("form_submission", form_submission_assistant)
builder.add_edge("enter_form_submission", "form_submission")
builder.add_node(
  "form_submission_safe_tools",
  create_tool_node_with_fallback([submit_form, CompleteOrEscalate]), # 包含表格提交工具
)

def route_form_submission(state: State) -> Literal[
  "form_submission_safe_tools",
  "primary_assistant",
  "__end__",
]:
  route = tools_condition(state)
  if route == END:
      return END
  return "form_submission_safe_tools"

def route_form_submission_tools(state: State) -> Literal["form_submission", "primary_assistant"]:
    return "primary_assistant" if should_route_to_primary(state) else "form_submission"

builder.add_conditional_edges("form_submission_safe_tools", route_form_submission_tools)
builder.add_conditional_edges("form_submission", route_form_submission)

builder.add_conditional_edges("update_flight_safe_tools", route_update_flight_tools)
builder.add_conditional_edges("update_flight_sensitive_tools", route_update_flight_tools)
builder.add_conditional_edges("update_flight", route_update_flight)

# 汽车租赁助理
builder.add_node(
  "enter_book_car_rental",
  create_entry_node("Car Rental Assistant", "book_car_rental"),
)
builder.add_node("book_car_rental", car_rental_assistant)
builder.add_edge("enter_book_car_rental", "book_car_rental")
builder.add_node(
  "book_car_rental_safe_tools",
  create_tool_node_with_fallback(book_car_rental_safe_tools),
)
builder.add_node(
  "book_car_rental_sensitive_tools",
  create_tool_node_with_fallback(book_car_rental_sensitive_tools),
)

def route_book_car_rental(state: State) -> Literal[
  "book_car_rental_safe_tools",
  "book_car_rental_sensitive_tools",
  "primary_assistant",
  "__end__",
]:
  route = tools_condition(state)
  if route == END:
      return END
  tool_calls = state["messages"][-1].tool_calls
  safe_toolnames = [t.name for t in book_car_rental_safe_tools]
  if all(tc["name"] in safe_toolnames for tc in tool_calls):
      return "book_car_rental_safe_tools"
  return "book_car_rental_sensitive_tools"

builder.add_conditional_edges("book_car_rental_safe_tools", route_car_rental_tools)
builder.add_conditional_edges("book_car_rental_sensitive_tools", route_car_rental_tools)
builder.add_conditional_edges("book_car_rental", route_book_car_rental)

# 旅馆预订助理
builder.add_node(
  "enter_book_hotel",
  create_entry_node("Hotel Booking Assistant", "book_hotel"),
)
builder.add_node("book_hotel", hotel_booking_assistant)
builder.add_edge("enter_book_hotel", "book_hotel")
builder.add_node(
  "book_hotel_safe_tools",
  create_tool_node_with_fallback(book_hotel_safe_tools),
)
builder.add_node(
  "book_hotel_sensitive_tools",
  create_tool_node_with_fallback(book_hotel_sensitive_tools),
)

def route_book_hotel(state: State) -> Literal[
  "book_hotel_safe_tools",
  "book_hotel_sensitive_tools",
  "primary_assistant",
  "__end__",
]:
  route = tools_condition(state)
  if route == END:
      return END
  tool_calls = state["messages"][-1].tool_calls
  safe_toolnames = [t.name for t in book_hotel_safe_tools]
  if all(tc["name"] in safe_toolnames for tc in tool_calls):
      return "book_hotel_safe_tools"
  return "book_hotel_sensitive_tools"

builder.add_conditional_edges("book_hotel_safe_tools", route_hotel_tools)
builder.add_conditional_edges("book_hotel_sensitive_tools", route_hotel_tools)
builder.add_conditional_edges("book_hotel", route_book_hotel)

# 外出旅行助理助理
builder.add_node(
  "enter_book_excursion",
  create_entry_node("Trip Recommendation Assistant", "book_excursion"),
)
builder.add_node("book_excursion", excursion_assistant)
builder.add_edge("enter_book_excursion", "book_excursion")
builder.add_node(
  "book_excursion_safe_tools",
  create_tool_node_with_fallback(book_excursion_safe_tools),
)
builder.add_node(
  "book_excursion_sensitive_tools",
  create_tool_node_with_fallback(book_excursion_sensitive_tools),
)

def route_book_excursion(state: State) -> Literal[
  "book_excursion_safe_tools",
  "book_excursion_sensitive_tools",
  "primary_assistant",
  "__end__",
]:
  route = tools_condition(state)
  if route == END:
      return END
  tool_calls = state["messages"][-1].tool_calls
  safe_toolnames = [t.name for t in book_excursion_safe_tools]
  if all(tc["name"] in safe_toolnames for tc in tool_calls):
      return "book_excursion_safe_tools"
  return "book_excursion_sensitive_tools"

builder.add_conditional_edges("book_excursion_safe_tools", route_excursion_tools)
builder.add_conditional_edges("book_excursion_sensitive_tools", route_excursion_tools)
builder.add_conditional_edges("book_excursion", route_book_excursion)

# 初级初级助理助理
builder.add_node("primary_assistant", primary_assistant)
builder.add_node(
  "primary_assistant_tools", create_tool_node_with_fallback(primary_assistant_tools)
)
builder.add_edge("fetch_user_info", "primary_assistant")

def route_primary_assistant(state: State) -> Literal[
  "primary_assistant_tools",
  "enter_update_flight",
  "enter_book_car_rental",
  "enter_book_hotel",
  "enter_book_excursion",
  "enter_woocommerce", # 新路线
  "enter_form_submission", # 新路线
  "__end__",
]:
  route = tools_condition(state)
  if route == END:
      return END
  tool_calls = state["messages"][-1].tool_calls
  if tool_calls:
      tool_name = tool_calls[0]["name"]
      if tool_name == ToFlightBookingAssistant.__name__:
          return "enter_update_flight"
      elif tool_name == ToBookCarRental.__name__:
          return "enter_book_car_rental"
      elif tool_name == ToHotelBookingAssistant.__name__:
          return "enter_book_hotel"
      elif tool_name == ToBookExcursion.__name__:
          return "enter_book_excursion"
      elif tool_name == ToWooCommerceProducts.__name__ or tool_name == ToWooCommerceOrders.__name__:
          return "enter_woocommerce"
      elif tool_name == ToFormSubmission.__name__:
          return "enter_form_submission"
      else:
          return "primary_assistant_tools"
  return "primary_assistant"

builder.add_conditional_edges(
  "primary_assistant",
  route_primary_assistant,
  {
      "enter_update_flight": "enter_update_flight",
      "enter_book_car_rental": "enter_book_car_rental",
      "enter_book_hotel": "enter_book_hotel",
      "enter_book_excursion": "enter_book_excursion",
      "enter_woocommerce": "enter_woocommerce", # 新边缘
      "enter_form_submission": "enter_form_submission", # 新边缘
      "primary_assistant_tools": "primary_assistant_tools",
      END: END,
  },
)
builder.add_edge("primary_assistant_tools", "primary_assistant")

# 从警卫车检查到初级助理的路线
builder.add_edge("guardrail_check", "primary_assistant")

# 以中断编译图形
interrupt_nodes = [
  "update_flight_sensitive_tools",
  "book_car_rental_sensitive_tools",
  "book_hotel_sensitive_tools",
  "book_excursion_sensitive_tools",
  # 新助理不需要中断,因为他们没有敏感操作
]

memory = MemorySaver()
multi_agentic_graph = builder.compile(
  checkpointer=memory,
  interrupt_before=interrupt_nodes,
)
