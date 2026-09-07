from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from app.tools import (
    search_flights,
    lookup_policy,
)
from ddgs import DDGS
from langchain_core.tools import tool
from app.assistants.assistant_base import Assistant, llm
from app.core.state import State
from pydantic import BaseModel, Field

# 进口新的授权模式
from app.assistants.woocommerce_assistant import ToWooCommerceProducts, ToWooCommerceOrders
from app.assistants.form_submission_assistant import ToFormSubmission


@tool
def web_search(query: str) -> list[dict]:
    """Search the public web for up-to-date information."""
    return DDGS().text(query, max_results=10)

# 界定任务授权工具
class ToFlightBookingAssistant(BaseModel):
    """转到一名专门助理处理飞行更新和取消事宜。"""
    request: str = Field(description="Any necessary follow-up questions the update flight assistant should clarify before proceeding.")

class ToBookCarRental(BaseModel):
    """转到专门助理处理租车订票工作。"""
    location: str = Field(description="The location where the user wants to rent a car.")
    start_date: str = Field(description="The start date of the car rental.")
    end_date: str = Field(description="The end date of the car rental.")
    request: str = Field(description="Any additional information or requests from the user regarding the car rental.")

class ToHotelBookingAssistant(BaseModel):
    """转到一名专门助理处理旅馆预订、改建和注销事宜。"""
    location: str = Field(description="The location where the user wants to book a hotel. Use 'Unknown' if not specified for cancellation requests.", default="Unknown")
    checkin_date: str = Field(description="The check-in date for the hotel. Use 'Unknown' if not specified for cancellation requests.", default="Unknown")
    checkout_date: str = Field(description="The check-out date for the hotel. Use 'Unknown' if not specified for cancellation requests.", default="Unknown")
    request: str = Field(description="Any additional information or requests from the user regarding the hotel operation (booking, cancellation, modification).")

class ToBookExcursion(BaseModel):
    """转到一名专门助理处理旅行建议和其他旅行预订事宜。"""
    location: str = Field(description="The location where the user wants to book a recommended trip.")
    request: str = Field(description="Any additional information or requests from the user regarding the trip recommendation.")

# 小学助助助
primary_assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful customer support assistant for Swiss Airlines. "
            "Your primary role is to search for flight information and company policies to answer customer queries. "
            "When customers need help with specialized services, you must delegate to the appropriate assistant: "
            "\n\nDELEGATION RULES (ALWAYS delegate, never try to handle these yourself):"
            "- Flight updates/cancellations → ToFlightBookingAssistant"
            "- Car rental booking/modification/cancellation → ToBookCarRental"
            "- Hotel booking/modification/cancellation/status → ToHotelBookingAssistant"
            "- Trip recommendations/excursions → ToBookExcursion"
            # 新的授权规则
            "- Product searches → ToWooCommerceProducts"
            "- Order searches (with email/name verification) → ToWooCommerceOrders"
            "- Form submissions → ToFormSubmission"
            "\n\nFor hotel operations, delegate even for:"
            "- 'cancel my hotel', 'cancel it' (when referring to hotel)"
            "- 'check hotel status', 'hotel booking status'"
            "- 'modify my hotel booking', 'change hotel dates'"
            "\n\nIMPORTANT: If the user asks about MULTIPLE services in one query (e.g., 'car and hotel status'), "
            "do NOT delegate to multiple assistants. Instead, handle it yourself by:"
            "1. Using search_flights to check current bookings"
            "2. Providing a summary of what you can see"
            "3. Asking the user to specify which service they want detailed help with"
            "\n\nOnly delegate to ONE assistant at a time. Never make multiple delegation calls in a single response."
            "\n\nOnly the specialized assistants have permission to make these changes. "
            "The user is not aware of the different specialized assistants, so do not mention them; just quietly delegate through function calls. "
            "Provide detailed information to the customer, and always double-check the database before concluding that information is unavailable. "
            "When searching, be persistent. Expand your query bounds if the first search returns no results. "
            "If a search comes up empty, expand your search before giving up."
            "\n\nCurrent user flight information:\n<Flights>\n{user_info}\n</Flights>"
            "\nCurrent time: {time}.",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now())

# 初级初级助理工具
primary_assistant_tools = [
    web_search,
    search_flights,
    lookup_policy,
    ToFlightBookingAssistant,
    ToBookCarRental,
    ToHotelBookingAssistant,
    ToBookExcursion,
    # 代表团使用的新工具
    ToWooCommerceProducts,
    ToWooCommerceOrders,
    ToFormSubmission,
]

# 创建主助理助手可运行
primary_assistant_runnable = primary_assistant_prompt | llm.bind_tools(primary_assistant_tools)

# 证明初级助理
primary_assistant = Assistant(primary_assistant_runnable)
