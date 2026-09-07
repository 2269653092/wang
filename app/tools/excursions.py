from vectorizer.vectordb.vectordb import VectorDB
from app.core.settings import get_settings
from langchain_core.tools import tool
from app.core.humanloop_manager import humanloop_adapter # 导入适应器
import sqlite3
from typing import Optional, List, Dict

settings = get_settings()
db = settings.SQLITE_DB_PATH
excursions_vectordb = VectorDB(table_name="trip_recommendations", collection_name="excursions_collection")

@tool
def search_trip_recommendations(
    query: str,
    limit: int = 2,
) -> List[Dict]:
    """根据自然语言查询寻找出行建议。"""
    search_results = excursions_vectordb.search(query, limit=limit)

    recommendations = []
    for result in search_results:
        payload = result.payload
        recommendations.append({
            "id": payload["id"],
            "name": payload["name"],
            "location": payload["location"],
            "keywords": payload["keywords"],
            "details": payload["details"],
            "booked": payload["booked"],
            "chunk": payload["content"],
            "similarity": result.score,
        })
    return recommendations

@tool
@humanloop_adapter.require_approval(execute_on_reject=False)
async def book_excursion(recommendation_id: int, approval_result=None) -> str:
    """用它的ID记录一种游览。"""
    # 如果批准被拒绝, 此函数机构将不会执行 。
    # 如果获得批准,批准结果将包含批准细节。
    
    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE trip_recommendations SET booked = 1 WHERE id = ?", (recommendation_id,)
    )
    conn.commit()

    if cursor.rowcount > 0:
        conn.close()
        return f"Excursion {recommendation_id} successfully booked."
    else:
        conn.close()
        return f"No excursion found with ID {recommendation_id}."

@tool
@humanloop_adapter.require_approval(execute_on_reject=False)
async def update_excursion(recommendation_id: int, details: str, approval_result=None) -> str:
    """以其身份来更新远足的细节 。"""
    # 如果批准被拒绝, 此函数机构将不会执行 。
    # 如果获得批准,批准结果将包含批准细节。
    
    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE trip_recommendations SET details = ? WHERE id = ?",
        (details, recommendation_id),
    )
    conn.commit()

    if cursor.rowcount > 0:
        conn.close()
        return f"Excursion {recommendation_id} successfully updated."
    else:
        conn.close()
        return f"No excursion found with ID {recommendation_id}."

@tool
@humanloop_adapter.require_approval(execute_on_reject=False)
async def cancel_excursion(recommendation_id: int, approval_result=None) -> str:
    """取消通过 ID 的远航 。"""
    # 如果批准被拒绝, 此函数机构将不会执行 。
    # 如果获得批准,批准结果将包含批准细节。
    
    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE trip_recommendations SET booked = 0 WHERE id = ?", (recommendation_id,)
    )
    conn.commit()

    if cursor.rowcount > 0:
        conn.close()
        return f"Excursion {recommendation_id} successfully cancelled."
    else:
        conn.close()
        return f"No excursion found with ID {recommendation_id}."
