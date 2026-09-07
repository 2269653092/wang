#!/usr/bin/env python3
"""多代理 RAG 客户支持系统数据库初始化和样本数据人口表脚本。 此脚本创建数据库图案, 并用样本旅行数据将其填充 。"""

import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path

# 获取数据库路径
db_path = Path("./data/travel/travel2.sqlite")

def init_database():
    """利用模型和样本数据初始化数据库。"""
    
    # 确保数据目录存在
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 如果已有数据库文件, 则删除文件
    if db_path.exists():
        os.remove(db_path)
        print(f"Removed existing database: {db_path}")
    
    # 连接到数据库( 这将创建数据库)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"Creating database: {db_path}")
    
    try:
        # 从 SQL 文件读取和执行 schema 计划
        with open("init_database.sql", "r", encoding="utf-8") as f:
            schema_sql = f.read()
        
        # 执行 schema 创建
        cursor.executescript(schema_sql)
        print("✓ Database schema created successfully")
        
        # 添加样本数据
        populate_sample_data(cursor)
        
        # 提交所有更改
        conn.commit()
        print("✓ Database initialized successfully")
        
    except Exception as e:
        print(f"✗ Error initializing database: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def populate_sample_data(cursor):
    """利用旅行数据样本充实数据库。"""
    
    # 样本飞行数据
    base_date = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
    
    flights_data = [
        (1, "AA100", "LAX", "JFK", base_date + timedelta(days=1), base_date + timedelta(days=1, hours=5), None, None, "Scheduled", "A320"),
        (2, "UA200", "JFK", "LAX", base_date + timedelta(days=2), base_date + timedelta(days=2, hours=6), None, None, "Scheduled", "B737"),
        (3, "DL300", "LAX", "MIA", base_date + timedelta(days=3), base_date + timedelta(days=3, hours=5), None, None, "Scheduled", "A321"),
        (4, "AA400", "MIA", "LAX", base_date + timedelta(days=5), base_date + timedelta(days=5, hours=5), None, None, "Scheduled", "A320"),
        (5, "UA500", "JFK", "SFO", base_date + timedelta(days=7), base_date + timedelta(days=7, hours=6), None, None, "Scheduled", "B777"),
        (6, "DL600", "SFO", "JFK", base_date + timedelta(days=10), base_date + timedelta(days=10, hours=5), None, None, "Scheduled", "A350"),
    ]
    
    cursor.executemany("""
        INSERT INTO flights (flight_id, flight_no, departure_airport, arrival_airport, 
                           scheduled_departure, scheduled_arrival, actual_departure, actual_arrival, 
                           status, aircraft_code)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, flights_data)
    
    # 票票样本数据
    tickets_data = [
        ("TKT001", "BOOK001", "5102 899977"),
        ("TKT002", "BOOK002", "5102 899977"),
        ("TKT003", "BOOK003", "1234 567890"),
        ("TKT004", "BOOK004", "9876 543210"),
    ]
    
    cursor.executemany("""
        INSERT INTO tickets (ticket_no, book_ref, passenger_id)
        VALUES (?, ?, ?)
    """, tickets_data)
    
    # 机票机票抽样数据
    ticket_flights_data = [
        ("TKT001", 1, "Economy"),
        ("TKT002", 3, "Business"),
        ("TKT003", 2, "Economy"),
        ("TKT004", 5, "First"),
    ]
    
    cursor.executemany("""
        INSERT INTO ticket_flights (ticket_no, flight_id, fare_conditions)
        VALUES (?, ?, ?)
    """, ticket_flights_data)
    
    # 抽样登机通行证数据
    boarding_passes_data = [
        ("TKT001", 1, "12A"),
        ("TKT002", 3, "3C"),
        ("TKT003", 2, "25F"),
        ("TKT004", 5, "1A"),
    ]
    
    cursor.executemany("""
        INSERT INTO boarding_passes (ticket_no, flight_id, seat_no)
        VALUES (?, ?, ?)
    """, boarding_passes_data)
    
    # 抽样旅馆数据
    hotels_data = [
        ("Grand Hotel Downtown", "New York, NY", "Luxury", (base_date + timedelta(days=1)).strftime('%Y-%m-%d'), (base_date + timedelta(days=3)).strftime('%Y-%m-%d'), 0),
        ("Budget Inn Express", "Los Angeles, CA", "Budget", (base_date + timedelta(days=2)).strftime('%Y-%m-%d'), (base_date + timedelta(days=4)).strftime('%Y-%m-%d'), 0),
        ("Beachfront Resort", "Miami, FL", "Luxury", (base_date + timedelta(days=5)).strftime('%Y-%m-%d'), (base_date + timedelta(days=8)).strftime('%Y-%m-%d'), 0),
        ("City Center Hotel", "San Francisco, CA", "Mid-tier", (base_date + timedelta(days=7)).strftime('%Y-%m-%d'), (base_date + timedelta(days=10)).strftime('%Y-%m-%d'), 0),
        ("Airport Hotel", "New York, NY", "Budget", (base_date + timedelta(days=1)).strftime('%Y-%m-%d'), (base_date + timedelta(days=2)).strftime('%Y-%m-%d'), 0),
        ("Luxury Suites", "Los Angeles, CA", "Luxury", (base_date + timedelta(days=3)).strftime('%Y-%m-%d'), (base_date + timedelta(days=6)).strftime('%Y-%m-%d'), 0),
    ]
    
    cursor.executemany("""
        INSERT INTO hotels (name, location, price_tier, checkin_date, checkout_date, booked)
        VALUES (?, ?, ?, ?, ?, ?)
    """, hotels_data)
    
    # 汽车租赁抽样数据
    car_rentals_data = [
        ("Economy Car Rental", "Los Angeles, CA", "Budget", (base_date + timedelta(days=1)).strftime('%Y-%m-%d'), (base_date + timedelta(days=7)).strftime('%Y-%m-%d'), 0),
        ("Luxury Vehicle Rental", "New York, NY", "Luxury", (base_date + timedelta(days=2)).strftime('%Y-%m-%d'), (base_date + timedelta(days=5)).strftime('%Y-%m-%d'), 0),
        ("Mid-size Car Rental", "Miami, FL", "Mid-tier", (base_date + timedelta(days=5)).strftime('%Y-%m-%d'), (base_date + timedelta(days=10)).strftime('%Y-%m-%d'), 0),
        ("SUV Rental Service", "San Francisco, CA", "Mid-tier", (base_date + timedelta(days=7)).strftime('%Y-%m-%d'), (base_date + timedelta(days=12)).strftime('%Y-%m-%d'), 0),
        ("Compact Car Rental", "Los Angeles, CA", "Budget", (base_date + timedelta(days=3)).strftime('%Y-%m-%d'), (base_date + timedelta(days=8)).strftime('%Y-%m-%d'), 0),
        ("Premium Car Service", "New York, NY", "Luxury", (base_date + timedelta(days=1)).strftime('%Y-%m-%d'), (base_date + timedelta(days=4)).strftime('%Y-%m-%d'), 0),
    ]
    
    cursor.executemany("""
        INSERT INTO car_rentals (name, location, price_tier, start_date, end_date, booked)
        VALUES (?, ?, ?, ?, ?, ?)
    """, car_rentals_data)
    
    # 旅行建议样本数据
    trip_recommendations_data = [
        ("Hollywood Tour", "Los Angeles, CA", "entertainment,sightseeing,celebrity", "Visit famous Hollywood landmarks including Walk of Fame, TCL Chinese Theatre, and Hollywood Sign viewpoints. Duration: 4 hours.", 0),
        ("Central Park Walking Tour", "New York, NY", "nature,walking,park", "Explore Central Park's most iconic locations including Bethesda Fountain, Strawberry Fields, and Bow Bridge. Duration: 3 hours.", 0),
        ("Art Deco Architecture Tour", "Miami, FL", "architecture,history,culture", "Discover Miami's stunning Art Deco district in South Beach with guided tours of historic buildings. Duration: 2.5 hours.", 0),
        ("Golden Gate Bridge Experience", "San Francisco, CA", "sightseeing,bridge,photography", "Complete Golden Gate Bridge experience including Crissy Field, Battery Spencer viewpoint, and walking across the bridge. Duration: 3 hours.", 0),
        ("Beach Day Package", "Miami, FL", "beach,relaxation,water", "Full day Miami Beach experience with chair rental, umbrella, and water activities. Duration: Full day.", 0),
        ("Wine Country Tour", "San Francisco, CA", "wine,tasting,countryside", "Napa Valley wine tasting tour with transportation from San Francisco. Includes 3 wineries and lunch. Duration: 8 hours.", 0),
        ("Broadway Show Package", "New York, NY", "theater,entertainment,culture", "Premium Broadway show tickets with pre-show dinner at Times Square restaurant. Duration: 5 hours.", 0),
        ("Sunset Strip Nightlife", "Los Angeles, CA", "nightlife,music,entertainment", "Guided tour of famous Sunset Strip venues with VIP access to select clubs. Duration: 6 hours.", 0),
    ]
    
    cursor.executemany("""
        INSERT INTO trip_recommendations (name, location, keywords, details, booked)
        VALUES (?, ?, ?, ?, ?)
    """, trip_recommendations_data)
    
    print("✓ Sample data populated successfully")
    print(f"  - {len(flights_data)} flights")
    print(f"  - {len(tickets_data)} tickets")
    print(f"  - {len(ticket_flights_data)} ticket-flight associations")
    print(f"  - {len(boarding_passes_data)} boarding passes")
    print(f"  - {len(hotels_data)} hotels")
    print(f"  - {len(car_rentals_data)} car rentals")
    print(f"  - {len(trip_recommendations_data)} trip recommendations")

def verify_database():
    """校验数据库创建正确 。"""
    if not db_path.exists():
        print("✗ Database file not found!")
        return False
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查是否所有表格都已存在
        tables = ["flights", "tickets", "ticket_flights", "boarding_passes", "hotels", "car_rentals", "trip_recommendations"]
        
        for table in tables:
            cursor.execute("SELECT COUNT(*) FROM {}".format(table))
            count = cursor.fetchone()[0]
            print(f"  ✓ Table '{table}': {count} records")
        
        # 测试失败的具体查询
        cursor.execute("""
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
                t.passenger_id = '5102 899977'
        """)
        
        results = cursor.fetchall()
        print(f"  ✓ Test query successful: {len(results)} ticket(s) found for passenger '5102 899977'")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Database verification failed: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("Initializing Multi-Agent RAG Customer Support Database...")
    print("=" * 60)
    
    init_database()
    
    print("\nVerifying database...")
    print("=" * 30)
    if verify_database():
        print("\n🎉 Database initialization completed successfully!")
        print(f"Database location: {db_path.absolute()}")
        print("\nYou can now run the customer support chat system:")
        print("poetry run python -m app.cli")
    else:
        print("\n❌ Database initialization failed!")
        exit(1)
