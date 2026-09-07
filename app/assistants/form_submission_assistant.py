# 客户_support_chat/ap/services/services/助理/form_subject_sideant.py 客户_support_chat/ap/services/services/助理/提交书_form_support_support_sideant.py.

from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from app.tools.forms import submit_form
from app.assistants.assistant_base import Assistant, llm, CompleteOrEscalate
from pydantic import BaseModel, Field
from typing import Dict, Any

# 定义表格提交的任务授权工具
class ToFormSubmission(BaseModel):
    """向专门助理移交工作,处理提交用户表格事宜。"""
    form_data: Dict[str, Any] = Field(description="A dictionary containing form field names as keys and user inputs as values.")

# 表格提交助理
form_submission_assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a specialized assistant for handling user form submissions. "
            "Your primary role is to collect necessary information from the user and then use the submit_form tool "
            "to send the data to the specified API endpoint. "
            "The form requires the following mandatory fields: "
            "- 'your-name': The user's full name "
            "- 'your-email': The user's email address "
            "- 'your-subject': The subject of the inquiry "
            "Additionally, the form always includes '_wpcf7': 942 as a fixed parameter. "
            "You MUST collect all three mandatory fields from the user before submitting the form. "
            "If the user doesn't provide all required information, politely ask for the missing fields. "
            "Always confirm with the user before submitting the form. "
            "If the user's request is not related to form submission, "
            "use the CompleteOrEscalate tool to return control to the main assistant. "
            "For debugging purposes, please include detailed information about the form data being submitted. "
            "Current time: {time}.",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now())

# 表格提交辅助工具
form_submission_assistant_tools = [
    submit_form,
    CompleteOrEscalate,
]

# 创建提交表单助手可运行
form_submission_assistant_runnable = form_submission_assistant_prompt | llm.bind_tools(form_submission_assistant_tools)

# 证明提交表格助理
form_submission_assistant = Assistant(form_submission_assistant_runnable)