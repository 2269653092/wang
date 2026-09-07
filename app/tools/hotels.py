from vectorizer.vectordb.vectordb import VectorDB
from app.core.settings import get_settings
from langchain_core.tools import tool
from app.core.humanloop_manager import humanloop_adapter # 导入适应器
import sqlite3
from typing import Optional, Union, List, Dict
from datetime import datetime, date

settings = get_settings()
db = settings.SQLITE_DB_PATH
hotels_vectordb = VectorDB(table_name="hotels", collection_name="hotels_collection")

@tool
def search_hotels(
    query: str,
    limit: int = 2,
) -> List[Dict]:
    """根据自然语言查询搜索酒店。"""
    search_results = hotels_vectordb.search(query, limit=limit)

    hotels = []
    for result in search_results:
        payload = result.payload
        hotels.append({
            "id": payload["id"],
            "name": payload["name"],
            "location": payload["location"],
            "price_tier": payload["price_tier"],
            "checkin_date": payload["checkin_date"],
            "checkout_date": payload["checkout_date"],
            "booked": payload["booked"],
            "chunk": payload["content"],
            "similarity": result.score,
        })
    return hotels

@tool
@humanloop_adapter.require_approval(execute_on_reject=False)
async def book_hotel(hotel_id: int, approval_result=None) -> str:
    """用身份证订旅馆"""
    # 如果批准被拒绝, 此函数机构将不会执行 。
    # 如果获得批准,批准结果将包含批准细节。
    
    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    cursor.execute("UPDATE hotels SET booked = 1 WHERE id = ?", (hotel_id,))
    conn.commit()

    if cursor.rowcount > 0:
        conn.close()
        return f"Hotel {hotel_id} successfully booked."
    else:
        conn.close()
        return f"No hotel found with ID {hotel_id}."

@tool
@humanloop_adapter.require_approval(execute_on_reject=False)
async def update_hotel(
    hotel_id: int,
    checkin_date: Optional[Union[datetime, date]] = None,
    checkout_date: Optional[Union[datetime, date]] = None,
    approval_result=None
) -> str:
    """以身份证更新酒店的报到和离职日期 并标为订户"""
    # 如果批准被拒绝, 此函数机构将不会执行 。
    # 如果获得批准,批准结果将包含批准细节。
    
    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    # 更新时总是将旅馆标记为已预订
    cursor.execute("UPDATE hotels SET booked = 1 WHERE id = ?", (hotel_id,))

    if checkin_date:
        cursor.execute(
            "UPDATE hotels SET checkin_date = ? WHERE id = ?",
            (checkin_date.strftime('%Y-%m-%d'), hotel_id),
        )
    if checkout_date:
        cursor.execute(
            "UPDATE hotels SET checkout_date = ? WHERE id = ?",
            (checkout_date.strftime('%Y-%m-%d'), hotel_id),
        )

    conn.commit()

    if cursor.rowcount > 0:
        conn.close()
        return f"Hotel {hotel_id} successfully updated and booked."
    else:
        conn.close()
        return f"No hotel found with ID {hotel_id}."

@tool
@humanloop_adapter.require_approval(execute_on_reject=False)
async def cancel_hotel(hotel_id: int, approval_result=None) -> str:
    """取消酒店的身份证"""
    # 如果批准被拒绝, 此函数机构将不会执行 。
    # 如果获得批准,批准结果将包含批准细节。
    
    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    cursor.execute("UPDATE hotels SET booked = 0 WHERE id = ?", (hotel_id,))
    conn.commit()

    if cursor.rowcount > 0:
        conn.close()
        return f"Hotel {hotel_id} successfully cancelled."
    else:
        conn.close()
        return f"No hotel found with ID {hotel_id}."
