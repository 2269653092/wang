from vectorizer.core.logger import logger
from vectorizer.vectordb.vectordb import VectorDB
from vectorizer.core.settings import get_settings

settings = get_settings()

def create_collections():
    # 定义所有可用的收藏
    # FAQ 收集与外部数据一起工作,其他则需要 SQLite 数据库
    collections = [
        ("faq", "faq_collection"),                 # 使用来自网络的外部 FAQ 数据 - 总是有效
        ("flights", "flights_collection"),         # 需要SQLite DB和飞行表
        ("hotels", "hotels_collection"),           # 需要SQLite DB 配旅馆桌
        ("car_rentals", "car_rentals_collection"), # 需要SQLite DB 带有汽车租赁表
        ("trip_recommendations", "excursions_collection")    # 需要 SQLite DB 和 Trif_建议表格
    ]
    
    logger.info(f"Starting vectorizer with {len(collections)} collections to process")
    logger.info(f"Collections: {[f'{table}->{collection}' for table, collection in collections]}")
    
    # 首先测试嵌入 API 连接
    logger.info("Testing embedding API connection...")
    test_vectordb = VectorDB("test", "test_collection", create_collection=False)
    import asyncio
    connection_ok = asyncio.run(test_vectordb.test_openai_connection())
    
    if not connection_ok:
        logger.error("Embedding API connection failed. Please check your configuration.")
        logger.error("See EMBEDDING_SETUP.md for configuration instructions.")
        return
    
    # 跟踪成功和失败的收藏
    successful_collections = []
    failed_collections = []

    for table_name, collection_name in collections:
        try:
            logger.info(f"\n" + "="*80)
            logger.info(f"Processing: {table_name} -> {collection_name}")
            logger.info(f"="*80)
            
            logger.info(f"Starting the vector database service for {table_name}")
            vectordb = VectorDB(table_name=table_name, collection_name=collection_name, create_collection=True)
            
            logger.info(f"Starting embedding creation for {collection_name}...")
            vectordb.create_embeddings()
            
            logger.info(f"✅ Embedding generation and storage completed for {collection_name}")
            successful_collections.append((table_name, collection_name))
            
        except Exception as e:
            logger.error(f"❌ An error occurred while processing {table_name}: {type(e).__name__}: {str(e)}")
            logger.exception("Detailed error information:")
            failed_collections.append((table_name, collection_name, str(e)))
            
            # 对于依赖数据库的收藏,日志帮助信息
            if table_name != "faq":
                logger.info(f"💡 Note: {table_name} collection requires SQLite database with {table_name} table. "
                           f"If the database is empty or missing, this collection will be skipped.")
    
    # 简要报告摘要报告
    logger.info(f"\n" + "="*80)
    logger.info(f"VECTORIZATION SUMMARY")
    logger.info(f"="*80)
    
    if successful_collections:
        logger.info(f"✅ Successfully processed {len(successful_collections)} collections:")
        for table, collection in successful_collections:
            logger.info(f"   • {table} -> {collection}")
    
    if failed_collections:
        logger.warning(f"❌ Failed to process {len(failed_collections)} collections:")
        for table, collection, error in failed_collections:
            logger.warning(f"   • {table} -> {collection}: {error[:100]}...")
    
    logger.info(f"\n🎯 System is ready with {len(successful_collections)} active collections!")
    
    if not successful_collections:
        logger.error(f"⚠️ No collections were successfully created. Check your configuration and database setup.")

if __name__ == "__main__":
    create_collections()
    logger.info(f"\n🚀 Note: To populate other collections (flights, hotels, car_rentals, excursions), "
               f"ensure the SQLite database at {settings.SQLITE_DB_PATH} contains the required tables with data.")
