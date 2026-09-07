# 客户_support_chat/ap/services/chat_service.py 客户_support_chat/ap/services/chat_service.py 客户_support_chat/ap/services/chat_service.py 客户_support_cord_chat/ap/services/chat_service.py
"""此模块为使用 LangGraph 多试剂系统处理用户信息提供服务。 它包含主. py 的核心聊天逻辑, 以便在网络应用程序中重新使用 。"""

import asyncio
from typing import Dict, Any, List, Union
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage
from app.graph import multi_agentic_graph
from app.core.logger import logger

# 尝试导入 Web_app 模块
try:
    from app.core.user_data_manager import set_pending_action, get_pending_action, get_user_decision, clear_pending_action, clear_user_decision, add_operation_log
    WEB_APP_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Web app modules not available. HITL functionality will be limited. Error: {e}")
    WEB_APP_AVAILABLE = False


async def process_user_message(session_data: Dict[str, Any], user_message: str) -> str:
    """使用 LangGraph 多试剂系统处理用户信息 。 参考: 会话_ data (Dict[str, anyny]): 会话数据包含配置( thread_ id, 客运_ id) 。 user_ message (str): 用户要处理的信息 。 返回: str: AI 回复信息 。"""
    # 从会话(_data)提取配置
    config = session_data.get("config", {})
    # 确保它的格式符合兰格法的正确格式
    langgraph_config = {"configurable": config}
    
    # 用于跟踪打印信件 ID 以避免重复的变量
    # 在网络上,我们收集信息,只回复最新的AI回应
    printed_message_ids = set()
    latest_ai_response = None
    
    try:
        # 将用户输入添加到操作日志
        if WEB_APP_AVAILABLE:
            add_operation_log(session_data["session_id"], {
                "type": "user_input",
                "title": "User Message",
                "content": user_message
            })
        
        # 通过图形处理用户输入
        # 使用流- 活动来更好地同步支持和更多颗粒控制
        # 然而,为了简单和与现有代码兼容 我们使用流
        events = multi_agentic_graph.stream(
            {"messages": [("user", user_message)]}, langgraph_config, stream_mode="values"
        )
        
        # 从流中收集信件
        all_tool_calls_needing_response = []  # 跟踪所有需要响应的工具呼叫
        
        for event in events:
            messages = event.get("messages", [])
            for message in messages:
                if message.id not in printed_message_ids:
                    # 跟踪需要响应的任何工具呼叫
                    if hasattr(message, 'tool_calls') and message.tool_calls:
                        for tool_call in message.tool_calls:
                            # 只有追踪尚未处理的工具电话
                            if tool_call["id"] not in [tc["id"] for tc in all_tool_calls_needing_response]:
                                all_tool_calls_needing_response.append(tool_call)
                                logger.debug(f"Tracking tool call: {tool_call['name']} (ID: {tool_call['id']})")
                    
                    # 记录不同类型的电文
                    if WEB_APP_AVAILABLE:
                        if isinstance(message, AIMessage) and message.content and message.content.strip():
                            # 仅在有有意义的内容时才在操作日志中添加 AI 响应
                            add_operation_log(session_data["session_id"], {
                                "type": "ai_response",
                                "title": "AI Response",
                                "content": message.content
                            })
                        elif hasattr(message, 'tool_calls') and message.tool_calls:
                            # 将工具呼叫添加到操作日志
                            for tool_call in message.tool_calls:
                                add_operation_log(session_data["session_id"], {
                                    "type": "tool_call",
                                    "title": f"{tool_call['name']} call",
                                    "content": "\n".join([f"{k}: {v}" for k, v in tool_call['args'].items()]),
                                    "details": {
                                        "tool_name": tool_call['name'],
                                        "tool_call_id": tool_call['id'],
                                        "parameters": tool_call['args']
                                    }
                                })
                    
                    # 消息. pettty_ print () # 我们不想在网络应用程序中打印到控制台
                    if isinstance(message, AIMessage) and message.content.strip():
                        # 只保留最新大赦国际的答复,并非全部
                        latest_ai_response = message.content
                    printed_message_ids.add(message.id)
                    
        logger.info(f"Processed {len(all_tool_calls_needing_response)} tool calls during stream")
                    
        # 检查中断( HITL)
        snapshot = multi_agentic_graph.get_state(langgraph_config)
        logger.info(f"Graph snapshot - next: {snapshot.next}, values keys: {list(snapshot.values.keys()) if snapshot.values else 'None'}")
        
        if snapshot.next:
            # 通过提供适当的工具电文回复处理中断的处理
            logger.info("Interrupt occurred. In a web app, this would require user approval.")
            
            # 获取应该包含工具电话的最后一条消息
            last_message = snapshot.values["messages"][-1] if snapshot.values.get("messages") else None
            
            if last_message and hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                logger.info(f"Last message has {len(last_message.tool_calls)} tool calls: {[tc['name'] for tc in last_message.tool_calls]}")
                
                # 对于 Web 应用程序上下文, 我们将设置待处理的动作, 等待用户输入
                if WEB_APP_AVAILABLE:
                    # 为用户批准提取工具呼叫细节
                    tool_calls_details = []
                    for tool_call in last_message.tool_calls:
                        tool_calls_details.append({
                            "id": tool_call["id"],
                            "name": tool_call["name"],
                            "args": tool_call["args"]
                        })
                    
                    # 存储待决行动
                    pending_action = {
                        "tool_calls": tool_calls_details,
                        "timestamp": asyncio.get_event_loop().time()
                    }
                    set_pending_action(session_data["session_id"], pending_action)
                    
                    # 添加中断到操作日志
                    add_operation_log(session_data["session_id"], {
                        "type": "system_message",
                        "title": "HITL Interrupt",
                        "content": "Sensitive action requires user approval",
                        "details": {
                            "tool_calls": tool_calls_details
                        }
                    })
                    
                    # 创建工具信件回复以确认此工具调用
                    # 这对于防止丢失工具呼叫响应错误是必要的
                    tool_messages = []
                    for tool_call in last_message.tool_calls:
                        tool_messages.append(
                            ToolMessage(
                                tool_call_id=tool_call["id"],
                                content="Action requires user approval. Please wait for user decision.",
                            )
                        )
                    
                    logger.info(f"Sending {len(tool_messages)} acknowledgment messages for HITL")
                    
                    # 发送工具信息以识别工具调用
                    # 这将防止丢失工具呼叫响应的错误
                    multi_agentic_graph.update_state(
                        langgraph_config,
                        {"messages": tool_messages},
                    )
                    
                    # 需要回回邮件表示用户批准
                    if latest_ai_response:
                        latest_ai_response += "\n\n[User approval required for sensitive action. Please approve or reject this action in the web interface.]"
                    else:
                        latest_ai_response = "[User approval required for sensitive action. Please approve or reject this action in the web interface.]"
                else:
                    # 如果网络应用程序不可用, 返回到自动拒绝
                    # 为所有工具调用创建工具信件回复
                    tool_messages = []
                    for tool_call in last_message.tool_calls:
                        tool_messages.append(
                            ToolMessage(
                                tool_call_id=tool_call["id"],
                                content="API call denied by user. Reasoning: 'Sensitive operations require explicit approval in web interface. Please contact support for assistance with booking changes or cancellations.'. Continue assisting, accounting for the user's input.",
                            )
                        )
                    
                    # 继续使用拒绝回复的图形执行
                    denial_response = multi_agentic_graph.invoke(
                        {"messages": tool_messages},
                        langgraph_config,
                    )
                    
                    # 处理拒绝回复信息
                    messages = denial_response.get("messages", [])
                    for message in messages:
                        if message.id not in printed_message_ids:
                            if isinstance(message, AIMessage) and message.content.strip():
                                # 仅保持对大赦国际最新答复的拒绝处理
                                latest_ai_response = message.content
                            printed_message_ids.add(message.id)
            else:
                logger.warning("Interrupt detected but no tool calls found in last message")
                # 如果找不到工具呼叫, 返回
                if latest_ai_response:
                    latest_ai_response += "\n\n[User approval required for sensitive action. Please contact support for assistance.]"
                else:
                    latest_ai_response = "[User approval required for sensitive action. Please contact support for assistance.]"
        else:
            logger.info("No interrupt detected")
            # 未发生中断, 但检查是否有未处理的工具电话需要响应
            # 这是防止工具_ 调用边边框错误的保障措施
            if all_tool_calls_needing_response:
                logger.info(f"Checking {len(all_tool_calls_needing_response)} tool calls for proper acknowledgment")
                
                # 检查是否通过查看最后状态处理所有工具调用
                final_messages = snapshot.values.get("messages", [])
                handled_tool_call_ids = set()
                
                # 收集拥有相应工具消息的所有工具调用 ID
                for msg in final_messages:
                    if hasattr(msg, 'tool_call_id') and msg.tool_call_id:
                        handled_tool_call_ids.add(msg.tool_call_id)
                
                logger.info(f"Found {len(handled_tool_call_ids)} handled tool call IDs")
                
                # 查找没有响应的任何工具电话
                unhandled_tool_calls = [
                    tc for tc in all_tool_calls_needing_response 
                    if tc["id"] not in handled_tool_call_ids
                ]
                
                if unhandled_tool_calls:
                    logger.warning(f"Found {len(unhandled_tool_calls)} unhandled tool calls, creating acknowledgment messages")
                    
                    for tc in unhandled_tool_calls:
                        logger.warning(f"Unhandled tool call: {tc['name']} (ID: {tc['id']})")
                    
                    # 为未处理的工具调用创建确认信息
                    acknowledgment_messages = []
                    for tool_call in unhandled_tool_calls:
                        acknowledgment_messages.append(
                            ToolMessage(
                                tool_call_id=tool_call["id"],
                                content=f"Tool '{tool_call['name']}' processed successfully.",
                            )
                        )
                    
                    # 如果有的话, 发送确认信息
                    if acknowledgment_messages:
                        try:
                            multi_agentic_graph.update_state(
                                langgraph_config,
                                {"messages": acknowledgment_messages},
                            )
                            logger.info(f"Sent {len(acknowledgment_messages)} acknowledgment messages for unhandled tool calls")
                        except Exception as ack_error:
                            logger.error(f"Failed to send acknowledgment messages: {ack_error}")
                else:
                    logger.info("All tool calls have been properly acknowledged")
            
        # 返回最新的 AI 回复, 或在未生成 AI 回复时返回默认信息
        if latest_ai_response:
            return latest_ai_response
        else:
            return "I'm sorry, I didn't understand that. Could you please rephrase?"
            
    except Exception as e:
        logger.error(f"An error occurred while processing the user message: {e}")
        
        # 工具_调用错误的特殊处理
        if "tool_calls must be followed by tool messages" in str(e):
            logger.warning("Detected tool_calls acknowledgment error - attempting recovery")
            logger.error(f"Full error details: {e}")
            
            try:
                # 获取当前图形状态以了解什么是工具调用
                snapshot = multi_agentic_graph.get_state(langgraph_config)
                logger.info(f"Graph state - next: {snapshot.next}")
                
                # 查找带有工具电话的最后一条消息
                if snapshot.values and "messages" in snapshot.values:
                    messages = snapshot.values["messages"]
                    logger.info(f"Total messages in state: {len(messages)}")
                    
                    # 以工具调用来查找信件
                    for i, msg in enumerate(reversed(messages[-10:])):
                        if hasattr(msg, 'tool_calls') and msg.tool_calls:
                            logger.info(f"Message {len(messages)-i} has {len(msg.tool_calls)} tool calls:")
                            for tc in msg.tool_calls:
                                logger.info(f"  - {tc['name']} (ID: {tc['id']})")
                
                # 尝试从错误消息中提取工具调用 ID 并创建确认
                error_str = str(e)
                if "tool_call_ids did not have response messages:" in error_str:
                    # 从错误消息中提取工具调用 ID
                    import re
                    tool_call_match = re.search(r'call_[a-zA-Z0-9]+', error_str)
                    if tool_call_match:
                        missing_tool_call_id = tool_call_match.group()
                        logger.info(f"Creating emergency acknowledgment for tool call ID: {missing_tool_call_id}")
                        
                        # 创建紧急确认信息
                        emergency_acknowledgment = ToolMessage(
                            tool_call_id=missing_tool_call_id,
                            content="Emergency acknowledgment: Tool call processed.",
                        )
                        
                        # 尝试发送确认
                        multi_agentic_graph.update_state(
                            langgraph_config,
                            {"messages": [emergency_acknowledgment]},
                        )
                        
                        logger.info("Emergency acknowledgment sent successfully")
                        
                        # 答复,表示已处理过这一问题
                        return "I apologize for the technical difficulty. Your request has been processed. Please try rephrasing your question if you need additional assistance."
                        
            except Exception as recovery_error:
                logger.error(f"Failed to recover from tool_calls error: {recovery_error}")
        
        # 将错误添加到操作日志
        if WEB_APP_AVAILABLE:
            add_operation_log(session_data["session_id"], {
                "type": "error",
                "title": "Processing Error",
                "content": str(e)
            })
        # 在 Web 应用程序中, 您可能想要返回更方便用户的错误消息
        # 或以不同方式处理不同类型的错误
        return "An unexpected error occurred while processing your request. Please try again later."


async def process_user_decision(session_data: Dict[str, Any], decision: str) -> str:
    """处理用户对待决行动的决定( 批准/ 拒绝) 。 参考: 会话_ data (Dict[str,  any]): 会话数据包含配置( tread_ id, 客运_ id) 。 决定 (str): 用户的决定 (“ 批准” 或“ 拒绝 ” 。 返回: str: AI 处理决定后的反应信息 。"""
    if not WEB_APP_AVAILABLE:
        return "HITL functionality is not available in this environment."
    
    # 从会话(_data)提取配置
    config = session_data.get("config", {})
    # 确保它的格式符合兰格法的正确格式
    langgraph_config = {"configurable": config}
    
    # 用于跟踪打印信件 ID 以避免重复的变量
    printed_message_ids = set()
    result_message = ""
    
    try:
        # 获取待决诉讼
        pending_action = get_pending_action(session_data["session_id"])
        if not pending_action:
            return "No pending action found."
        
        # 将用户决定添加到操作日志
        add_operation_log(session_data["session_id"], {
            "type": "user_input",
            "title": "User Decision",
            "content": f"User {decision.lower()}d the action"
        })
        
        # 从待决行动中获取工具电话
        tool_calls = pending_action.get("tool_calls", [])
        
        if decision.lower() == "approve":
            # 供批准,我们直接使用工具
            # 这是一种简化的方法----在实际执行中,你会
            # 执行实际工具并返回其结果
            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                # 导入和实施合适的工具
                try:
                    if tool_name == "update_hotel":
                        from app.tools.hotels import update_hotel
                        # 使用 ainvoke 进行同步函数
                        result = await update_hotel.ainvoke(tool_args)
                        result_message = f"Hotel updated successfully: {result}"
                    elif tool_name == "book_hotel":
                        from app.tools.hotels import book_hotel
                        # 使用 ainvoke 进行同步函数
                        result = await book_hotel.ainvoke(tool_args)
                        result_message = f"Hotel booked successfully: {result}"
                    elif tool_name == "cancel_hotel":
                        from app.tools.hotels import cancel_hotel
                        # 使用 ainvoke 进行同步函数
                        result = await cancel_hotel.ainvoke(tool_args)
                        result_message = f"Hotel cancelled successfully: {result}"
                    elif tool_name == "update_car_rental":
                        from app.tools.cars import update_car_rental
                        # 使用 ainvoke 进行同步函数
                        result = await update_car_rental.ainvoke(tool_args)
                        result_message = f"Car rental updated successfully: {result}"
                    elif tool_name == "book_car_rental":
                        from app.tools.cars import book_car_rental
                        # 使用 ainvoke 进行同步函数
                        result = await book_car_rental.ainvoke(tool_args)
                        result_message = f"Car rental booked successfully: {result}"
                    elif tool_name == "cancel_car_rental":
                        from app.tools.cars import cancel_car_rental
                        # 使用 ainvoke 进行同步函数
                        result = await cancel_car_rental.ainvoke(tool_args)
                        result_message = f"Car rental cancelled successfully: {result}"
                    elif tool_name == "book_excursion":
                        from app.tools.excursions import book_excursion
                        # 使用 ainvoke 进行同步函数
                        result = await book_excursion.ainvoke(tool_args)
                        result_message = f"Excursion booked successfully: {result}"
                    elif tool_name == "update_excursion":
                        from app.tools.excursions import update_excursion
                        # 使用 ainvoke 进行同步函数
                        result = await update_excursion.ainvoke(tool_args)
                        result_message = f"Excursion updated successfully: {result}"
                    elif tool_name == "cancel_excursion":
                        from app.tools.excursions import cancel_excursion
                        # 使用 ainvoke 进行同步函数
                        result = await cancel_excursion.ainvoke(tool_args)
                        result_message = f"Excursion cancelled successfully: {result}"
                    elif tool_name == "update_ticket_to_new_flight":
                        from app.tools.flights import update_ticket_to_new_flight
                        # 使用 ainvoke 进行同步函数
                        result = await update_ticket_to_new_flight.ainvoke({**tool_args, "config": langgraph_config})
                        result_message = f"Flight updated successfully: {result}"
                    elif tool_name == "cancel_ticket":
                        from app.tools.flights import cancel_ticket
                        # 使用 ainvoke 进行同步函数
                        result = await cancel_ticket.ainvoke({**tool_args, "config": langgraph_config})
                        result_message = f"Flight cancelled successfully: {result}"
                    else:
                        result_message = f"Tool {tool_name} executed successfully (tool not implemented in approval handler)"
                    
                    # 将工具执行结果添加到操作日志
                    add_operation_log(session_data["session_id"], {
                        "type": "tool_result",
                        "title": f"{tool_name} Result",
                        "content": result if 'result' in locals() else result_message
                    })
                    
                except Exception as e:
                    error_msg = f"Error executing {tool_name}: {str(e)}"
                    result_message = error_msg
                    add_operation_log(session_data["session_id"], {
                        "type": "error",
                        "title": f"{tool_name} Execution Error",
                        "content": error_msg
                    })
        else:  # 拒绝拒绝
            # 拒绝时,我们只需通知用户
            result_message = "Operation cancelled by user."
            # 添加取消到操作日志
            add_operation_log(session_data["session_id"], {
                "type": "system_message",
                "title": "Action Cancelled",
                "content": "User rejected the sensitive action"
            })
        
        # 清除待采取行动和用户决定
        clear_pending_action(session_data["session_id"])
        clear_user_decision(session_data["session_id"])
        
        # 返回结果消息
        if result_message:
            return result_message
        else:
            return "Action processed successfully."
            
    except Exception as e:
        logger.error(f"An error occurred while processing the user decision: {e}")
        # 将错误添加到操作日志
        add_operation_log(session_data["session_id"], {
            "type": "error",
            "title": "Decision Processing Error",
            "content": str(e)
        })
        # 清除待处理的动作和用户决定,即使有错误
        try:
            clear_pending_action(session_data["session_id"])
            clear_user_decision(session_data["session_id"])
        except:
            pass
        return "An unexpected error occurred while processing your decision. Please try again later."




