from vectorizer.vectordb.vectordb import VectorDB
from app.core.settings import get_settings
from langchain_core.tools import tool
from app.core.humanloop_manager import humanloop_adapter # 导入适应器
import sqlite3
from typing import List, Dict, Optional, Union
from datetime import datetime, date

settings = get_settings()
db = settings.SQLITE_DB_PATH

cars_vectordb = VectorDB(table_name="car_rentals", collection_name="car_rentals_collection")

@tool
def search_car_rentals(
    query: str,
    limit: int = 2,
) -> List[Dict]:
    """寻找基于自然语言查询的汽车租赁。"""
    search_results = cars_vectordb.search(query, limit=limit)

    rentals = []
    for result in search_results:
        payload = result.payload
        rentals.append({
            "id": payload["id"],
            "name": payload["name"],
            "location": payload["location"],
            "price_tier": payload["price_tier"],
            "start_date": payload["start_date"],
            "end_date": payload["end_date"],
            "booked": payload["booked"],
            "chunk": payload["content"],
            "similarity": result.score,
        })
    return rentals

@tool
@humanloop_adapter.require_approval(execute_on_reject=False)
async def book_car_rental(rental_id: int, approval_result=None) -> str:
    """用身份证订租车"""
    # 如果批准被拒绝, 此函数机构将不会执行 。
    # 如果获得批准,批准结果将包含批准细节。
    
    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    cursor.execute("UPDATE car_rentals SET booked = 1 WHERE id = ?", (rental_id,))
    conn.commit()

    if cursor.rowcount > 0:
        conn.close()
        return f"Car rental {rental_id} successfully booked."
    else:
        conn.close()
        return f"No car rental found with ID {rental_id}."

@tool
@humanloop_adapter.require_approval(execute_on_reject=False)
async def update_car_rental(
    rental_id: int,
    start_date: Optional[Union[datetime, date]] = None,
    end_date: Optional[Union[datetime, date]] = None,
    approval_result=None
) -> str:
    """以身份证明更新租车的开始日期和结束日期。"""
    # 如果批准被拒绝, 此函数机构将不会执行 。
    # 如果获得批准,批准结果将包含批准细节。
    
    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    if start_date:
        cursor.execute(
            "UPDATE car_rentals SET start_date = ? WHERE id = ?",
            (start_date.strftime('%Y-%m-%d'), rental_id),
        )
    if end_date:
        cursor.execute(
            "UPDATE car_rentals SET end_date = ? WHERE id = ?",
            (end_date.strftime('%Y-%m-%d'), rental_id),
        )

    conn.commit()

    if cursor.rowcount > 0:
        conn.close()
        return f"Car rental {rental_id} successfully updated."
    else:
        conn.close()
        return f"No car rental found with ID {rental_id}."

@tool
@humanloop_adapter.require_approval(execute_on_reject=False)
async def cancel_car_rental(rental_id: int, approval_result=None) -> str:
    """以身份证取消租车"""
    # 如果批准被拒绝, 此函数机构将不会执行 。
    # 如果获得批准,批准结果将包含批准细节。
    
    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    cursor.execute("UPDATE car_rentals SET booked = 0 WHERE id = ?", (rental_id,))
    conn.commit()

    if cursor.rowcount > 0:
        conn.close()
        return f"Car rental {rental_id} successfully cancelled."
    else:
        conn.close()
        return f"No car rental found with ID {rental_id}."
