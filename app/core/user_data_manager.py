import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

# 存储用户会话数据的目录
USER_DATA_DIR = "./data/sessions"

def initialize_user_data_dir():
    """如果用户数据目录不存在, 初始化该目录 。"""
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)

def get_user_data_file(session_id: str) -> str:
    """获取特定用户数据的文件路径 。"""
    return os.path.join(USER_DATA_DIR, f"{session_id}.json")

def load_user_data(session_id: str) -> Dict[str, Any]:
    """从单个 JSON 文件装入用户数据 。"""
    initialize_user_data_dir()
    user_file = get_user_data_file(session_id)
    
    if not os.path.exists(user_file):
        return {}
    
    try:
        with open(user_file, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_user_data(session_id: str, data: Dict[str, Any]):
    """将用户数据保存到单个 JSON 文件 。"""
    user_file = get_user_data_file(session_id)
    with open(user_file, "w") as f:
        json.dump(data, f, indent=2)

def get_user_session(session_id: str) -> Dict[str, Any]:
    """按会话 ID 获取用户会话, 如果不存在的话, 创建一个新的会话 。"""
    user_data = load_user_data(session_id)
    
    if not user_data:
        # 初始化带有默认值的新会话
        user_data = {
            "session_id": session_id,
            "chat_history": [],
            "pending_action": None,
            "user_decision": None,
            "operation_log": [],  # 添加操作日志存储
            "created_at": datetime.now().isoformat()
        }
        save_user_data(session_id, user_data)
    
    return user_data

def update_user_chat_history(session_id: str, user_message: str, ai_response: str):
    """更新用户会话的聊天历史 。"""
    user_data = load_user_data(session_id)
    
    if not user_data:
        user_data = {
            "session_id": session_id,
            "chat_history": [],
            "pending_action": None,
            "user_decision": None,
            "operation_log": [],  # 添加操作日志存储
            "created_at": datetime.now().isoformat()
        }
    
    # 在聊天历史中添加新消息配对
    user_data["chat_history"].append({
        "timestamp": datetime.now().isoformat(),
        "user_message": user_message,
        "ai_response": ai_response
    })
    
    save_user_data(session_id, user_data)

def set_pending_action(session_id: str, action_details: Dict[str, Any]):
    """设定用户会话的待采取行动 。"""
    user_data = load_user_data(session_id)
    
    if not user_data:
        user_data = {
            "session_id": session_id,
            "chat_history": [],
            "pending_action": None,
            "user_decision": None,
            "operation_log": [],  # 添加操作日志存储
            "created_at": datetime.now().isoformat()
        }
    
    user_data["pending_action"] = action_details
    save_user_data(session_id, user_data)

def get_pending_action(session_id: str) -> Optional[Dict[str, Any]]:
    """获取一个用户会话的待处理动作 。"""
    session_data = get_user_session(session_id)
    return session_data.get("pending_action")

def clear_pending_action(session_id: str):
    """清除用户会话的待处理动作 。"""
    user_data = load_user_data(session_id)
    if user_data:
        user_data["pending_action"] = None
        save_user_data(session_id, user_data)

def set_user_decision(session_id: str, decision: str):
    """设定用户决定为待处理的动作 。"""
    user_data = load_user_data(session_id)
    
    if not user_data:
        user_data = {
            "session_id": session_id,
            "chat_history": [],
            "pending_action": None,
            "user_decision": None,
            "operation_log": [],  # 添加操作日志存储
            "created_at": datetime.now().isoformat()
        }
    
    user_data["user_decision"] = decision
    save_user_data(session_id, user_data)

def get_user_decision(session_id: str) -> Optional[str]:
    """获取用户决定, 以便进行待决行动 。"""
    session_data = get_user_session(session_id)
    return session_data.get("user_decision")

def clear_user_decision(session_id: str):
    """清除用户决定待处理的动作 。"""
    user_data = load_user_data(session_id)
    if user_data:
        user_data["user_decision"] = None
        save_user_data(session_id, user_data)

def add_operation_log(session_id: str, log_entry: Dict[str, Any]):
    """在用户会话中添加操作日志条目 。"""
    user_data = load_user_data(session_id)
    
    if not user_data:
        user_data = {
            "session_id": session_id,
            "chat_history": [],
            "pending_action": None,
            "user_decision": None,
            "operation_log": [],  # 添加操作日志存储
            "created_at": datetime.now().isoformat()
        }
    
    # 如果不提供添加时间戳
    if "timestamp" not in log_entry:
        log_entry["timestamp"] = datetime.now().isoformat()
    
    user_data["operation_log"].append(log_entry)
    save_user_data(session_id, user_data)

def get_operation_log(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """获取用户会话的操作日志, 有可选限制 。"""
    session_data = get_user_session(session_id)
    log = session_data.get("operation_log", [])
    
    # 返回最晚到限制的条目
    if limit > 0 and len(log) > limit:
        return log[-limit:]
    return log

def clear_operation_log(session_id: str):
    """清除用户会话的操作日志 。"""
    user_data = load_user_data(session_id)
    if user_data:
        user_data["operation_log"] = []
        save_user_data(session_id, user_data)