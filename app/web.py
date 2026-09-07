from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from pydantic import BaseModel
import uuid
import os

from app.chat_service import process_user_message
from .core.user_data_manager import (
    get_user_session, 
    update_user_chat_history, 
    get_pending_action, 
    set_user_decision, 
    clear_pending_action, 
    clear_user_decision,
    get_operation_log
)

# 负载环境变量
load_dotenv()

app = FastAPI()

# 设置 Jinja2 模板
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

class ChatMessage(BaseModel):
    message: str

class ApprovalDecision(BaseModel):
    decision: str

def get_session_data(request: Request):
    """为当前用户获取或创建会话数据 。"""
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # 获取用户会话数据
    session_data = get_user_session(session_id)
    
    # 确保会话_ data 中的配置
    if "config" not in session_data:
        session_data["config"] = {
            "thread_id": session_id,
            "passenger_id": "5102 899977"  # 默认旅客身份
        }
    
    return {
        "session_id": session_id,
        "config": session_data["config"],
        "user_data": session_data
    }

@app.get("/", response_class=HTMLResponse)
async def get_chat_page(request: Request, session_data: dict = Depends(get_session_data)):
    """服务聊天界面。"""
    # 设置会话 cookie
    response = templates.TemplateResponse("chat.html", {
        "request": request, 
        "session_id": session_data["session_id"],
        "chat_history": session_data["user_data"].get("chat_history", [])
    })
    response.set_cookie(key="session_id", value=session_data["session_id"])
    return response

@app.post("/chat")
async def chat(chat_message: ChatMessage, session_data: dict = Depends(get_session_data)):
    """处理聊天信息并回复 AI 回应 。"""
    try:
        # 处理用户消息
        ai_response = await process_user_message(session_data, chat_message.message)
        
        # 更新用户的聊天历史
        update_user_chat_history(session_data["session_id"], chat_message.message, ai_response)
        
        # 回回大赦国际的答复
        return JSONResponse(content={"response": ai_response})
        
    except Exception as e:
        # 记录调试错误
        print(f"Error processing chat message: {e}")
        # 返回用户友好的错误消息
        return JSONResponse(content={"error": "An unexpected error occurred. Please try again later."}, status_code=500)

# HITL(在卢普的人类)终点

@app.get("/pending-action")
async def get_pending_action_endpoint(session_data: dict = Depends(get_session_data)):
    """检查是否有需要用户批准的待决动作 。"""
    try:
        pending_action = get_pending_action(session_data["session_id"])
        if pending_action:
            return JSONResponse(content={"pending_action": pending_action})
        else:
            return JSONResponse(content={"pending_action": None})
    except Exception as e:
        print(f"Error checking pending action: {e}")
        return JSONResponse(content={"error": "An unexpected error occurred. Please try again later."}, status_code=500)


@app.post("/approve-action")
async def approve_action(request: Request, session_data: dict = Depends(get_session_data)):
    """核准待决行动。"""
    try:
        # 处理用户的核准决定
        from app.chat_service import process_user_decision
        ai_response = await process_user_decision(session_data, "approve")
        
        # 更新用户的聊天历史
        update_user_chat_history(session_data["session_id"], "[User approved action]", ai_response)
        
        # 回回大赦国际的答复
        return JSONResponse(content={"response": ai_response})
        
    except Exception as e:
        # 记录调试错误
        print(f"Error processing approval: {e}")
        # 返回用户友好的错误消息
        return JSONResponse(content={"error": "An unexpected error occurred. Please try again later."}, status_code=500)


@app.post("/reject-action")
async def reject_action(request: Request, session_data: dict = Depends(get_session_data)):
    """驳回待决诉讼。"""
    try:
        # 处理用户拒绝用户的决定
        from app.chat_service import process_user_decision
        ai_response = await process_user_decision(session_data, "reject")
        
        # 更新用户的聊天历史
        update_user_chat_history(session_data["session_id"], "[User rejected action]", ai_response)
        
        # 回回大赦国际的答复
        return JSONResponse(content={"response": ai_response})
        
    except Exception as e:
        # 记录调试错误
        print(f"Error processing rejection: {e}")
        # 返回用户友好的错误消息
        return JSONResponse(content={"error": "An unexpected error occurred. Please try again later."}, status_code=500)

@app.get("/operation-log")
async def get_operation_log_endpoint(session_data: dict = Depends(get_session_data)):
    """获取当前会话的操作日志 。"""
    try:
        # 只获取最新的 20 个日志条目来减少数据传输
        operation_log = get_operation_log(session_data["session_id"], limit=20)
        return JSONResponse(content={"operation_log": operation_log})
    except Exception as e:
        print(f"Error retrieving operation log: {e}")
        return JSONResponse(content={"error": "An unexpected error occurred. Please try again later."}, status_code=500)
