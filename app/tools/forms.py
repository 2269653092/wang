# 客户端_support_chat/ap/services/tools/forms.py 客户端_support_chat/ap/services/tools/forms.

import httpx
from langchain_core.tools import tool
from app.core.settings import get_settings
from typing import Dict, Any

settings = get_settings()

@tool
def submit_form(form_data: Dict[str, Any]) -> str:
    """向指定的 API 提交用户窗体数据。 参考: 窗体_ data : 包含以字段名称为密钥的字典, 用户输入为值。 必须包含以下强制字段 : “ 您的姓名 ” 、 “ 您的电子邮件 ” 、 “ 您的主体 ” 。 返回: API 的确认信息或错误信息 。"""
    if not settings.FORM_SUBMISSION_API_URL:
        raise ValueError("Form submission API URL is not configured.")
    
    # 验证所需的字段
    required_fields = ['your-name', 'your-email', 'your-subject']
    missing_fields = [field for field in required_fields if field not in form_data or not form_data[field]]
    
    if missing_fields:
        raise ValueError(f"Missing required form fields: {', '.join(missing_fields)}")
    
    # 添加固定 _wpcf7 参数
    final_form_data = form_data.copy()
    final_form_data["_wpcf7"] = 946
    
    with httpx.Client() as client:
        try:
            response = client.post(
                settings.FORM_SUBMISSION_API_URL,
                json=final_form_data
            )
            
            # 用于调试的日志详细响应信息
            print(f"Form submission API response status: {response.status_code}")
            print(f"Form submission API response headers: {dict(response.headers)}")
            
            try:
                result = response.json()
                print(f"Form submission API response JSON: {result}")
            except Exception as json_error:
                print(f"Form submission API response text (non-JSON): {response.text}")
                result = {}
            
            response.raise_for_status()
            
            # 从 API 返回成功信息或具体回应
            # 这可能需要根据实际的API答复格式进行调整。
            if result.get("status") == "success" or response.status_code == 200:
                return f"Form submitted successfully. Thank you for your submission!"
            else:
                return f"Form submission may have encountered an issue. API response: {result}"
                
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP error occurred while submitting form: {e}")
        except Exception as e:
            raise Exception(f"An error occurred while submitting form: {e}")