import os
import sqlite3
import uuid
import re
import requests
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from vectorizer.core.settings import get_settings
from vectorizer.core.logger import logger
from .chunkenizer import recursive_character_splitting
from vectorizer.embeddings.embedding_generator import generate_embedding
import asyncio
import aiohttp
from tqdm.asyncio import tqdm_asyncio
from more_itertools import chunked
import time

settings = get_settings()

class VectorDB:
    def __init__(self, table_name, collection_name, create_collection=False):
        self.table_name = table_name
        self.collection_name = collection_name
        self.connect_to_qdrant()
        if create_collection:
            self.create_or_clear_collection()

    def connect_to_qdrant(self):
        # 如果提供了 API 键,则使用 API 键( 对于云 Qdrant) ,否则连接而不连接( 对于本地)
        logger.info(f"🔗 Connecting to Qdrant...")
        logger.info(f"🌐 URL: {settings.QDRANT_URL}")
        logger.info(f"🔑 API Key: {'***' + settings.QDRANT_KEY[-10:] if settings.QDRANT_KEY else 'None'}")
        
        try:
            if settings.QDRANT_KEY:
                logger.info("🔐 Using API key authentication")
                self.client = QdrantClient(
                    url=settings.QDRANT_URL, 
                    api_key=settings.QDRANT_KEY,
                    timeout=60  # 加速超时到60秒
                )
            else:
                logger.info("🔓 No API key - connecting without authentication")
                self.client = QdrantClient(url=settings.QDRANT_URL, timeout=60)
            
            # 测试连接
            logger.info("🧪 Testing connection by getting collections...")
            collections = self.client.get_collections()
            logger.info(f"✅ Connected to Qdrant successfully! Found {len(collections.collections)} existing collections:")
            
            for collection in collections.collections:
                logger.info(f"  📁 {collection.name}")
                
        except Exception as e:
            logger.error(f"❌ Failed to connect to Qdrant at {settings.QDRANT_URL}: {type(e).__name__}: {str(e)}")
            raise

    def create_or_clear_collection(self):
        max_retries = 3
        retry_delay = 5
        
        # 确定嵌入尺寸
        embedding_size = self.get_embedding_dimensions()
        
        for attempt in range(max_retries):
            try:
                # 检查收藏是否收藏已存在
                exists = self.client.collection_exists(self.collection_name)
                
                if exists:
                    # 检查我们是否应该根据环境变量重建
                    should_recreate = settings.RECREATE_COLLECTIONS
                    if isinstance(should_recreate, str):
                        should_recreate = should_recreate.lower() == "true"
                    
                    if should_recreate:
                        logger.info(f"Collection {self.collection_name} already exists. Recreating it.")
                        self.client.delete_collection(collection_name=self.collection_name)
                        # 删除后稍稍等待
                        import time
                        time.sleep(2)
                    else:
                        logger.info(f"Collection {self.collection_name} already exists. Skipping recreation.")
                        return
                
                # 创建带有动态嵌入大小的新收藏
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=embedding_size, distance=Distance.COSINE)
                )
                logger.info(f"Successfully created collection: {self.collection_name} with embedding size: {embedding_size}")
                return
                
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Attempt {attempt + 1}/{max_retries} failed to create collection: {str(e)}")
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    import time
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to create collection after {max_retries} attempts: {str(e)}")
                    raise
                    
    def get_embedding_dimensions(self):
        """根据正在使用的模型确定嵌入尺寸"""
        try:
            if settings.USE_LOCAL_EMBEDDINGS:
                # 对于本地嵌入器, 从模型中获取尺寸
                from vectorizer.embeddings.local_embedding_generator import get_local_model
                model = get_local_model()
                embedding_size = model.get_sentence_embedding_dimension()
                logger.info(f"Using local embedding model with {embedding_size} dimensions")
                return embedding_size
            else:
                logger.info(
                    f"Using configured API embedding size: {settings.EMBEDDING_DIMENSIONS}"
                )
                return settings.EMBEDDING_DIMENSIONS
        except Exception as e:
            logger.warning(f"Could not determine embedding dimensions: {str(e)}")
            logger.info(
                f"Defaulting to configured dimensions: {settings.EMBEDDING_DIMENSIONS}"
            )
            return settings.EMBEDDING_DIMENSIONS

    def format_content(self, data, collection_name):
        # 执行不同收藏的格式化逻辑
        if collection_name == 'car_rentals_collection':
            booking_status = "booked" if data['booked'] else "not booked"
            return f"Car rental: {data['name']}, located at: {data['location']}, price tier: {data['price_tier']}. " +\
                f"Rental period starts on {data['start_date']} and ends on {data['end_date']}. " +\
                    f"Currently, the rental is: {booking_status}."

        elif collection_name == 'excursions_collection':
            booking_status = "booked" if data['booked'] else "not booked"
            return f"Excursion: {data['name']} at {data['location']}. " +\
                f"Additional details: {data['details']}. " +\
                    f"Currently, the excursion is {booking_status}. " +\
                        f"Keywords: {data['keywords']}."

        elif collection_name == 'flights_collection':

            return f"Flight {data['flight_no']} from {data['departure_airport']} to {data['arrival_airport']} " +\
                f"was scheduled to depart at {data['scheduled_departure']} and arrive at {data['scheduled_arrival']}. " +\
                    f"The actual departure was at {data['actual_departure']} and the actual arrival was at {data['actual_arrival']}. " +\
                        f"Currently, the flight status is '{data['status']}' and it was operated with aircraft code {data['aircraft_code']}."

        elif collection_name == 'hotels_collection':
            booking_status = "booked" if data['booked'] else "not booked"
            return f"Hotel {data['name']} located in {data['location']} is categorized as {data['price_tier']} tier. " +\
                f"The check-in date is {data['checkin_date']} and the check-out date is {data['checkout_date']}. " +\
                    f"Currently, the booked status is: {booking_status}."

        elif collection_name == 'faq_collection':
            return data['page_content']  # 为 FAQ 直接返回页面内容
        else:
            return str(data)

    async def generate_embedding_async(self, content, session):
        max_retries = 5
        base_delay = 1
        
        # 固定嵌入 API 的基准 URL 构建
        base_url = settings.EMBEDDING_BASE_URL
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]  # 从末尾删除/ v1
        embedding_url = f"{base_url}/v1/embeddings"
        
        model = settings.EMBEDDING_MODEL
        
        logger.info(f"Using embedding URL: {embedding_url}")
        logger.info(f"Using model: {model}")
        logger.info(f"Content length: {len(content)} characters")
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempt {attempt + 1}/{max_retries} - Making embedding request...")
                
                headers = {"Authorization": f"Bearer {settings.EMBEDDING_API_KEY}"}
                payload = {"model": model, "input": content}
                
                async with session.post(
                    embedding_url,
                    headers=headers,
                    json=payload,
                    timeout=60  # 添加明确的超时
                ) as response:
                    logger.info(f"Response status: {response.status}")
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"HTTP Error {response.status}: {error_text}")
                        raise Exception(f"HTTP {response.status}: {error_text}")
                    
                    result = await response.json()
                    
                    if "data" in result and len(result["data"]) > 0:
                        embedding = result["data"][0]["embedding"]
                        logger.info(f"Successfully generated embedding with {len(embedding)} dimensions")
                        return embedding
                    else:
                        logger.error(f"Unexpected API response structure: {result}")
                        raise ValueError(f"Unexpected API response: {result}")
                        
            except Exception as e:
                logger.error(f"Error in attempt {attempt + 1}: {type(e).__name__}: {str(e)}")
                
                if attempt == max_retries - 1:
                    logger.error(f"Failed to generate embedding after {max_retries} attempts")
                    raise
                    
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)

    async def process_chunk(self, chunk, metadata, session):
        # 检查并限制输入长度以达到 API 要求(最多 2048 字符)
        max_length = 2048
        original_length = len(chunk)
        
        if original_length > max_length:
            logger.warning(f"Content too long ({original_length} chars), truncating to {max_length} chars")
            chunk = chunk[:max_length]
            # 确保我们不会在一个字中断断
            if chunk and not chunk[-1].isspace():
                last_space = chunk.rfind(' ')
                if last_space > max_length * 0.8:  # 只有我们不会失去太多的内容
                    chunk = chunk[:last_space]
        
        if len(chunk.strip()) == 0:
            logger.warning("Empty content after processing, skipping...")
            return None
            
        final_length = len(chunk)
        if final_length != original_length:
            logger.debug(f"Text length adjusted: {original_length} -> {final_length} chars")
            
        try:
            embedding = await self.generate_embedding_async(chunk, session)
            return PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "content": chunk,
                    "original_length": original_length,
                    "final_length": final_length,
                    **metadata
                }
            )
        except Exception as e:
            logger.error(f"Failed to process chunk (length: {final_length}): {str(e)}")
            raise

    async def create_embeddings_async(self):
        # 先测试 OpenAI 连接
        logger.info("🔍 Running preliminary checks...")
        
        if not await self.test_openai_connection():
            raise Exception("OpenAI API connection test failed. Cannot proceed with embedding generation.")
        
        logger.info("🚀 All checks passed! Proceeding with embedding generation...")
        
        if self.table_name == "faq":
            await self.index_faq_docs()
        else:
            await self.index_regular_docs()

    async def index_regular_docs(self):
        logger.info(f"📊 Processing regular collection: {self.collection_name} from table: {self.table_name}")
        
        try:
            # 检查数据库文件是否存在
            if not os.path.exists(settings.SQLITE_DB_PATH):
                logger.warning(f"⚠️ SQLite database file not found: {settings.SQLITE_DB_PATH}")
                logger.info(f"💡 Skipping collection {self.collection_name}. Create the database file to enable this collection.")
                return
                
            db_connection = sqlite3.connect(settings.SQLITE_DB_PATH)
            cursor = db_connection.cursor()
            
            # 检查表格是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (self.table_name,))
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                logger.warning(f"⚠️ Table '{self.table_name}' does not exist in database.")
                logger.info(f"💡 Skipping collection {self.collection_name}. Create table '{self.table_name}' to enable this collection.")
                db_connection.close()
                return
            
            # 获取表格数据
            cursor.execute(f"SELECT * FROM {self.table_name}")
            rows = cursor.fetchall()
            column_names = [column[0] for column in cursor.description]
            db_connection.close()
            
            if not rows:
                logger.warning(f"⚠️ No data found in table {self.table_name}.")
                logger.info(f"💡 Skipping collection {self.collection_name}. Add data to table '{self.table_name}' to enable this collection.")
                return
                
            logger.info(f"📋 Found {len(rows)} records in table {self.table_name}")
            
        except Exception as e:
            logger.error(f"❌ Database error for table {self.table_name}: {str(e)}")
            logger.info(f"💡 Skipping collection {self.collection_name} due to database error.")
            return

        # 将行转换为词典和进程内容
        data = [dict(zip(column_names, row)) for row in rows]
        
        # 处理每个项目,其文本长度验证与常见问题一样
        processed_chunks = []
        chunk_metadata = []  # 每个块块存储元数据
        max_chunk_size = 1900  # 保守缓冲带,以确保块块不超过2048年
        
        for i, item in enumerate(data):
            try:
                # 使用现有格式_ content 方法格式化内容
                content = self.format_content(item, self.collection_name)
                logger.debug(f"Item {i+1}: formatted content length = {len(content)} chars")
                
                if len(content) <= max_chunk_size:
                    processed_chunks.append(content)
                    chunk_metadata.append(item)  # 存储原始数据库记录
                else:
                    # 应用与 AQ 相同的智能分裂法
                    logger.debug(f"Content too long ({len(content)} chars), applying smart splitting...")
                    
                    # 首先按段落拆分
                    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
                    
                    current_chunk = ""
                    for paragraph in paragraphs:
                        if len(current_chunk) + len(paragraph) + 2 > max_chunk_size:
                            if current_chunk:
                                processed_chunks.append(current_chunk.strip())
                                chunk_metadata.append(item)  # 存储原始数据库记录
                                current_chunk = paragraph
                            else:
                                # 单段过长,一分为二,一分为二
                                sentences = [s.strip() for s in re.split(r'[.!?]+', paragraph) if s.strip()]
                                for sentence in sentences:
                                    if not sentence.endswith(('.', '!', '?')):
                                        sentence += '.'
                                        
                                    if len(current_chunk) + len(sentence) + 1 > max_chunk_size:
                                        if current_chunk:
                                            processed_chunks.append(current_chunk.strip())
                                            chunk_metadata.append(item)  # 存储原始数据库记录
                                            current_chunk = sentence
                                        else:
                                            # 单项刑期过长,短短
                                            processed_chunks.append(sentence[:max_chunk_size])
                                            chunk_metadata.append(item)  # 存储原始数据库记录
                                    else:
                                        current_chunk = current_chunk + " " + sentence if current_chunk else sentence
                        else:
                            current_chunk = current_chunk + "\n\n" + paragraph if current_chunk else paragraph
                    
                    # 添加最终块
                    if current_chunk:
                        processed_chunks.append(current_chunk.strip())
                        chunk_metadata.append(item)  # 存储原始数据库记录
                        
            except Exception as e:
                logger.error(f"❌ Error processing item {i+1}: {str(e)}")
                continue
        
        # 必要时适用额外的循环分裂,保存元数据
        final_chunks = []
        final_metadata = []
        
        for chunk, metadata in zip(processed_chunks, chunk_metadata):
            if chunk.strip():
                split_chunks = recursive_character_splitting(chunk, chunk_size=1800, chunk_overlap=20)
                valid_split_chunks = [c for c in split_chunks if c.strip()]
                final_chunks.extend(valid_split_chunks)
                # 每个分割块的元数据与原始块的元数据相同
                final_metadata.extend([metadata] * len(valid_split_chunks))
        
        if not final_chunks:
            logger.warning(f"⚠️ No valid chunks generated for {self.collection_name}")
            return
            
        # 校验所有块都在限制之内
        oversized_chunks = [i for i, chunk in enumerate(final_chunks) if len(chunk) > 2048]
        if oversized_chunks:
            logger.warning(f"⚠️ Found {len(oversized_chunks)} chunks exceeding 2048 chars, applying emergency truncation...")
            for i in oversized_chunks:
                original_length = len(final_chunks[i])
                final_chunks[i] = final_chunks[i][:2000]
                logger.warning(f"  Chunk {i}: truncated from {original_length} to {len(final_chunks[i])} chars")
        
        logger.info(f"📋 Generated {len(final_chunks)} valid chunks for {self.collection_name}")

        # 与 FAQ 相同同步处理的批量中处理块块
        batch_size = 50  # 用于更好地处理错误的小批量
        delay = 1  # 批次之间延迟秒数
        total_indexed = 0

        async with aiohttp.ClientSession() as session:
            for i in range(0, len(final_chunks), batch_size):
                batch = final_chunks[i:i+batch_size]
                batch_original_metadata = final_metadata[i:i+batch_size]
                logger.info(f"🔄 Processing batch {i//batch_size + 1}/{(len(final_chunks) + batch_size - 1)//batch_size} ({len(batch)} chunks)")
                
                # 为每个块创建元数据, 包括原始数据库字段
                batch_metadata = []
                for j, original_meta in enumerate(batch_original_metadata):
                    combined_metadata = {
                        "type": self.table_name, 
                        "batch": i//batch_size + 1,
                        **original_meta  # 包含所有原始数据库字段
                    }
                    batch_metadata.append(combined_metadata)
                
                tasks = [self.process_chunk(chunk, metadata, session) for chunk, metadata in zip(batch, batch_metadata)]
                
                points = []
                for task in tqdm_asyncio.as_completed(tasks, desc=f"Generating embeddings for {self.collection_name} (batch {i//batch_size + 1})", total=len(tasks)):
                    try:
                        point = await task
                        if point is not None:
                            points.append(point)
                    except Exception as e:
                        logger.error(f"❌ Error processing chunk: {str(e)}")

                if points:
                    try:
                        self.client.upsert(
                            collection_name=self.collection_name,
                            points=points
                        )
                        logger.info(f"💾 Indexed {len(points)} documents into {self.collection_name} (batch {i//batch_size + 1})")
                        total_indexed += len(points)
                    except Exception as e:
                        logger.error(f"❌ Error upserting batch to Qdrant: {str(e)}")

                # 各批之间为避免利率限额而避免的延迟
                if i + batch_size < len(final_chunks):
                    logger.debug(f"⏳ Waiting {delay} seconds before next batch...")
                    await asyncio.sleep(delay)

        logger.info(f"✅ Finished indexing {self.collection_name}. Total documents indexed: {total_indexed}")

    async def index_faq_docs(self):
        faq_url = "https://storage.googleapis.com/benchmarks-artifacts/travel-db/swiss_faq.md"
        
        logger.info(f"📄 Downloading FAQ content from: {faq_url}")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(faq_url) as response:
                    logger.info(f"📈 FAQ download response status: {response.status}")
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"❌ Failed to download FAQ: HTTP {response.status} - {error_text}")
                        raise Exception(f"Failed to download FAQ: HTTP {response.status}")
                    
                    faq_text = await response.text()
                    logger.info(f"📝 Downloaded FAQ content: {len(faq_text)} characters")
                    
            except Exception as e:
                logger.error(f"💥 Error downloading FAQ: {str(e)}")
                raise

        # 将 FAQ 拆分到文档中, 由信头先拆分到文档中
        initial_docs = [txt.strip() for txt in re.split(r"(?=\n##)", faq_text) if txt.strip()]
        logger.info(f"📋 Initial split FAQ into {len(initial_docs)} sections")
        
        # 为遵守 2048 字符字符限制而进一步拆分大文档以遵守 2048 字符限制
        max_chunk_size = 1900  # 更保守的缓冲区,以确保文件不超过2048年
        docs = []
        
        for i, doc_content in enumerate(initial_docs):
            logger.debug(f"Processing section {i+1}: {len(doc_content)} chars")
            
            if len(doc_content) <= max_chunk_size:
                docs.append({"page_content": doc_content})
            else:
                logger.info(f"Section {i+1} too long ({len(doc_content)} chars), applying smart splitting...")
                
                # 将大文档先按段落拆分
                paragraphs = [p.strip() for p in doc_content.split('\n\n') if p.strip()]
                logger.debug(f"  Split into {len(paragraphs)} paragraphs")
                
                current_chunk = ""
                chunk_count = 0
                
                for j, paragraph in enumerate(paragraphs):
                    # 如果添加此段, 将会超过限制, 保存当前块块并启动新块块
                    if len(current_chunk) + len(paragraph) + 2 > max_chunk_size:  # +2 for\n\nn +2 for\n\nn
                        if current_chunk:
                            docs.append({"page_content": current_chunk.strip()})
                            chunk_count += 1
                            logger.debug(f"    Created chunk {chunk_count}: {len(current_chunk)} chars")
                            current_chunk = paragraph
                        else:
                            # 单段太长,一分为二,一分为二
                            logger.debug(f"    Paragraph {j+1} too long ({len(paragraph)} chars), splitting by sentences...")
                            sentences = [s.strip() for s in re.split(r'[.!?]+', paragraph) if s.strip()]
                            
                            for k, sentence in enumerate(sentences):
                                # 如果删除后添加插件插件插件
                                if k < len(sentences) - 1 or not sentence.endswith(('.', '!', '?')):
                                    sentence += '.'
                                    
                                if len(current_chunk) + len(sentence) + 1 > max_chunk_size:
                                    if current_chunk:
                                        docs.append({"page_content": current_chunk.strip()})
                                        chunk_count += 1
                                        logger.debug(f"      Created sentence chunk {chunk_count}: {len(current_chunk)} chars")
                                        current_chunk = sentence
                                    else:
                                        # 连单句都过长,一分为二
                                        logger.debug(f"      Sentence too long ({len(sentence)} chars), splitting by words...")
                                        words = sentence.split()
                                        word_chunk = ""
                                        
                                        for word in words:
                                            if len(word_chunk) + len(word) + 1 > max_chunk_size:
                                                if word_chunk:
                                                    docs.append({"page_content": word_chunk.strip()})
                                                    chunk_count += 1
                                                    logger.debug(f"        Created word chunk {chunk_count}: {len(word_chunk)} chars")
                                                    word_chunk = word
                                                else:
                                                    # 单字过长, 短短( 非常罕见)
                                                    truncated = word[:max_chunk_size]
                                                    docs.append({"page_content": truncated})
                                                    chunk_count += 1
                                                    logger.warning(f"        Truncated very long word: {len(word)} -> {len(truncated)} chars")
                                            else:
                                                word_chunk = word_chunk + " " + word if word_chunk else word
                                        
                                        if word_chunk:
                                            current_chunk = word_chunk
                                else:
                                    current_chunk = current_chunk + " " + sentence if current_chunk else sentence
                    else:
                        current_chunk = current_chunk + "\n\n" + paragraph if current_chunk else paragraph
                
                # 如果最后一个块存在, 如果它存在, 添加最后一个块
                if current_chunk:
                    docs.append({"page_content": current_chunk.strip()})
                    chunk_count += 1
                    logger.debug(f"    Final chunk {chunk_count}: {len(current_chunk)} chars")
                
                logger.info(f"  Section {i+1} split into {chunk_count} chunks")
        
        logger.info(f"📋 Final split FAQ into {len(docs)} documents (after aggressive size optimization)")
        
        # 日志文件规模统计并进行最后验证
        if docs:
            doc_lengths = [len(doc["page_content"]) for doc in docs]
            logger.info(f"📏 Document length stats: min={min(doc_lengths)}, max={max(doc_lengths)}, avg={sum(doc_lengths)//len(doc_lengths)}")
            
            sample_doc = docs[0]["page_content"][:200] + "..." if len(docs[0]["page_content"]) > 200 else docs[0]["page_content"]
            logger.info(f"📖 Sample document: {sample_doc}")
            
            # 检查任何文件是否过长并修复
            oversized_docs = [i for i, doc in enumerate(docs) if len(doc["page_content"]) > 2048]
            if oversized_docs:
                logger.warning(f"⚠️ Found {len(oversized_docs)} documents still exceeding 2048 chars, applying emergency truncation...")
                for i in oversized_docs:
                    original_length = len(docs[i]["page_content"])
                    docs[i]["page_content"] = docs[i]["page_content"][:2000]  # 紧急缺勤
                    logger.warning(f"  Document {i}: truncated from {original_length} to {len(docs[i]['page_content'])} chars")
                
                # 在紧急修复后核查无超过限制的文件
                final_oversized = [i for i, doc in enumerate(docs) if len(doc["page_content"]) > 2048]
                if final_oversized:
                    logger.error(f"❌ CRITICAL: {len(final_oversized)} documents still exceed 2048 chars after emergency fixes!")
                else:
                    logger.info(f"✅ All documents now within 2048 character limit after emergency fixes")
            else:
                logger.info(f"✅ All documents are within the 2048 character limit!")

        logger.info(f"🤖 Starting embedding generation for {len(docs)} FAQ documents (all guaranteed <= 2048 chars)...")
        
        async with aiohttp.ClientSession() as session:
            tasks = [self.process_chunk(doc["page_content"], {"type": "faq"}, session) for doc in docs]

            try:
                points = await tqdm_asyncio.gather(*tasks, desc="Generating embeddings for FAQ documents")
                logger.info(f"✅ Successfully generated {len([p for p in points if p is not None])} embeddings")
            except Exception as e:
                logger.error(f"💥 Error during embedding generation: {str(e)}")
                raise

        if points:
            logger.info(f"📁 Upserting {len(points)} points to Qdrant collection: {self.collection_name}")
            
            try:
                for batch in chunked(points, 100):  # 视需要调整批量规模
                    non_null_batch = [p for p in batch if p is not None]
                    if non_null_batch:
                        logger.info(f"📎 Upserting batch of {len(non_null_batch)} points...")
                        self.client.upsert(
                            collection_name=self.collection_name,
                            points=non_null_batch
                        )
                        
                logger.info(f"✅ Successfully indexed {len([p for p in points if p is not None])} FAQ documents into {self.collection_name}.")
            except Exception as e:
                logger.error(f"💥 Error upserting to Qdrant: {str(e)}")
                raise
        else:
            logger.warning("⚠️ No FAQ documents were successfully embedded and indexed.")

    def create_embeddings(self):
        asyncio.run(self.create_embeddings_async())

    async def test_openai_connection(self):
        """用简单的嵌入请求测试 OpenAI API 连接"""
        logger.info("Testing OpenAI API connection...")
        
        # 固定嵌入 API 的基准 URL 构建
        base_url = settings.EMBEDDING_BASE_URL
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]  # 从末尾删除/ v1
        embedding_url = f"{base_url}/v1/embeddings"
        
        logger.info(f"Base URL: {base_url}")
        logger.info(f"Embedding URL: {embedding_url}")
        
        test_content = "Hello, this is a test."
        
        # 首次尝试获得可用的模型
        logger.info("Checking available models...")
        available_models = await self.get_available_models()
        
        # 优先测试显式配置的模型，再尝试常见 OpenAI 兼容模型。
        primary_models = [
            settings.EMBEDDING_MODEL,
            "text-embedding-3-small",  # spi2d.net兼容性优先模式
            "text-embedding-3-large",
            "text-embedding-ada-002"
        ]
        
        # api2d.net 和其他提供者的额外后退模型
        fallback_models = [
            "embedding-ada-002",  # 有些 API 使用这种格式
            "text-embedding-v1",
            "embedding-v1",
            "ada",  # 有些供应商使用短名
            "davinci"
        ]
        
        # 要尝试的合并模型
        models_to_try = []
        
        # 如果我们有的话, 先添加可用的模型
        if available_models:
            models_to_try.extend(available_models)
            
        # 添加初级模型
        for model in primary_models:
            if model not in models_to_try:
                models_to_try.append(model)
                
        # 添加后退模式
        for model in fallback_models:
            if model not in models_to_try:
                models_to_try.append(model)
        
        logger.info(f"Testing {len(models_to_try)} models: {models_to_try[:8]}...")  # 首显示 8
        
        for i, model in enumerate(models_to_try):
            try:
                logger.info(f"[{i+1}/{len(models_to_try)}] Testing model: {model}")
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        embedding_url,
                        headers={"Authorization": f"Bearer {settings.EMBEDDING_API_KEY}"},
                        json={"model": model, "input": test_content},
                        timeout=30
                    ) as response:
                        logger.info(f"Response status for {model}: {response.status}")
                        
                        if response.status == 200:
                            result = await response.json()
                            if "data" in result and len(result["data"]) > 0:
                                embedding = result["data"][0]["embedding"]
                                logger.info(f"SUCCESS! Model {model} works! Embedding size: {len(embedding)}")
                                # 储存工作模式供日后使用
                                self.working_model = model
                                return True
                        
                        error_text = await response.text()
                        logger.warning(f"Model {model} failed: HTTP {response.status} - {error_text[:100]}...")
                        
            except Exception as e:
                logger.warning(f"Error testing model {model}: {type(e).__name__}: {str(e)}")
                continue
        
        logger.error(f"All {len(models_to_try)} embedding models failed. The API may not support embeddings.")
        logger.error("Consider using a different API provider or local embedding model.")
        return False

    async def get_available_models(self):
        """从 API 获取可用的模型列表"""
        base_url = settings.EMBEDDING_BASE_URL
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]
        models_url = f"{base_url}/v1/models"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    models_url,
                    headers={"Authorization": f"Bearer {settings.EMBEDDING_API_KEY}"},
                    timeout=30
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if "data" in result:
                            models = [model["id"] for model in result["data"]]
                            embedding_models = [m for m in models if "embedding" in m.lower()]
                            logger.info(f"Available embedding models: {embedding_models}")
                            return embedding_models
                    
                    error_text = await response.text()
                    logger.warning(f"Could not get models list: HTTP {response.status} - {error_text}")
                    return []
        except Exception as e:
            logger.warning(f"Error getting models list: {str(e)}")
            return []

    def search(self, query, limit=2, with_payload=True):
        query_vector = generate_embedding(query)
        search_result = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            with_payload=with_payload
        )
        return search_result

if __name__ == "__main__":
    vectordb = VectorDB("example_table", "example_collection")
    vectordb.create_embeddings()
