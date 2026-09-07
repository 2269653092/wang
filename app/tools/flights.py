from vectorizer.vectordb.vectordb import VectorDB
from app.core.settings import get_settings
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from app.core.humanloop_manager import humanloop_adapter # 导入适应器
import sqlite3
from typing import Optional, Union, List, Dict
from datetime import datetime, date
import pytz

settings = get_settings()
db = settings.SQLITE_DB_PATH
flights_vectordb = VectorDB(table_name="flights", collection_name="flights_collection")


@tool
def fetch_user_flight_information(*, config: RunnableConfig) -> List[Dict]:
    """获取所有用户的机票以及相应的飞行信息和座位分配。"""
    configuration = config.get("configurable", {})
    passenger_id = configuration.get("passenger_id", None)
    if not passenger_id:
        raise ValueError("No passenger ID configured.")

    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    query = """
    SELECT 
        t.ticket_no, t.book_ref,
        f.flight_id, f.flight_no, f.departure_airport, f.arrival_airport, f.scheduled_departure, f.scheduled_arrival,
        bp.seat_no, tf.fare_conditions
    FROM 
        tickets t
        JOIN ticket_flights tf ON t.ticket_no = tf.ticket_no
        JOIN flights f ON tf.flight_id = f.flight_id
        LEFT JOIN boarding_passes bp ON bp.ticket_no = t.ticket_no AND bp.flight_id = f.flight_id
    WHERE 
        t.passenger_id = ?
    """
    cursor.execute(query, (passenger_id,))
    rows = cursor.fetchall()
    column_names = [column[0] for column in cursor.description]
    results = [dict(zip(column_names, row)) for row in rows]

    cursor.close()
    conn.close()

    return results

@tool
def search_flights(
    query: str,
    limit: int = 2,
) -> List[Dict]:
    """搜索基于自然语言查询的飞行。"""
    search_results = flights_vectordb.search(query, limit=limit)

    flights = []
    for result in search_results:
        payload = result.payload
        flights.append({
            "flight_id": payload["flight_id"],
            "flight_no": payload["flight_no"],
            "departure_airport": payload["departure_airport"],
            "arrival_airport": payload["arrival_airport"],
            "scheduled_departure": payload["scheduled_departure"],
            "scheduled_arrival": payload["scheduled_arrival"],
            "status": payload["status"],
            "aircraft_code": payload["aircraft_code"],
            "actual_departure": payload["actual_departure"],
            "actual_arrival": payload["actual_arrival"],
            "chunk": payload["content"],
            "similarity": result.score,
        })
    return flights

@tool
@humanloop_adapter.require_approval(execute_on_reject=False)
async def update_ticket_to_new_flight(
    ticket_no: str, new_flight_id: int, *, config: RunnableConfig, approval_result=None
) -> str:
    """更新用户到新有效航班的机票"""
    # 如果批准被拒绝, 此函数机构将不会执行 。
    # 如果获得批准,批准结果将包含批准细节。
    
    configuration = config.get("configurable", {})
    passenger_id = configuration.get("passenger_id", None)
    if not passenger_id:
        raise ValueError("No passenger ID configured.")

    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    # 检查机票是否存在,是否属于乘客
    cursor.execute(
        "SELECT * FROM tickets WHERE ticket_no = ? AND passenger_id = ?",
        (ticket_no, passenger_id),
    )
    ticket = cursor.fetchone()
    if not ticket:
        conn.close()
        # 如果用户意图得到确认,最好不要出现这种情况,但我们保留支票。
        return f"Ticket {ticket_no} not found for passenger {passenger_id}."

    # 更新机票航班
    cursor.execute(
        "UPDATE ticket_flights SET flight_id = ? WHERE ticket_no = ?",
        (new_flight_id, ticket_no),
    )
    conn.commit()

    conn.close()
    if cursor.rowcount > 0:
        return f"Ticket {ticket_no} successfully updated to flight {new_flight_id}."
    else:
        return f"Failed to update ticket {ticket_no}."

@tool
@humanloop_adapter.require_approval(execute_on_reject=False)
async def cancel_ticket(ticket_no: str, *, config: RunnableConfig, approval_result=None) -> str:
    """取消用户的机票, 从数据库中删除 。"""
    # 如果批准被拒绝, 此函数机构将不会执行 。
    # 如果获得批准,批准结果将包含批准细节。

    configuration = config.get("configurable", {})
    passenger_id = configuration.get("passenger_id", None)
    if not passenger_id:
        raise ValueError("No passenger ID configured.")

    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    # 检查机票是否存在,是否属于乘客
    cursor.execute(
        "SELECT * FROM tickets WHERE ticket_no = ? AND passenger_id = ?",
        (ticket_no, passenger_id),
    )
    ticket = cursor.fetchone()
    if not ticket:
        conn.close()
        # 如果用户意图得到确认,最好不要出现这种情况,但我们保留支票。
        return f"Ticket {ticket_no} not found for passenger {passenger_id}."

    # 删除机票机票
    cursor.execute(
        "DELETE FROM ticket_flights WHERE ticket_no = ?",
        (ticket_no,),
    )
    # 删除机票
    cursor.execute(
        "DELETE FROM tickets WHERE ticket_no = ?",
        (ticket_no,),
    )
    conn.commit()

    conn.close()
    return f"Ticket {ticket_no} successfully cancelled."
