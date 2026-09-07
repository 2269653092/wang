from langchain_openai import OpenAIEmbeddings
from vectorizer.core.settings import get_settings
from vectorizer.core.logger import logger
from typing import Union, List

settings = get_settings()

# 配置包含嵌入特定配置的 OpenAI 嵌入
if settings.EMBEDDING_BASE_URL:
    embeddings = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        openai_api_key=settings.EMBEDDING_API_KEY,
        openai_api_base=settings.EMBEDDING_BASE_URL
    )
else:
    embeddings = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        openai_api_key=settings.EMBEDDING_API_KEY
    )

def generate_embedding(content: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
    """使用 API 或基于配置配置的本地模型生成嵌入"""
    # 检查是否启用本地嵌入
    if settings.USE_LOCAL_EMBEDDINGS:
        logger.info("Using local embeddings")
        try:
            from .local_embedding_generator import generate_local_embedding
            return generate_local_embedding(content)
        except Exception as e:
            logger.error(f"Local embedding failed: {str(e)}")
            logger.info("Falling back to API embeddings...")
    
    # 使用 API 嵌入
    logger.info("Using API embeddings")
    try:
        if isinstance(content, str):
            return embeddings.embed_query(content)
        elif isinstance(content, list):
            return embeddings.embed_documents(content)
        else:
            raise ValueError("Content must be either a string or a list of strings")
    except Exception as e:
        logger.error(f"API embedding failed: {str(e)}")
        
        # 如果 API 失败且本地嵌入功能不启用, 请尝试让它们启用 。
        if not settings.USE_LOCAL_EMBEDDINGS:
            logger.info("API failed, attempting to use local embeddings as fallback...")
            try:
                from .local_embedding_generator import generate_local_embedding
                return generate_local_embedding(content)
            except Exception as local_e:
                logger.error(f"Local embedding fallback also failed: {str(local_e)}")
                raise Exception(f"Both API and local embeddings failed. API error: {str(e)}, Local error: {str(local_e)}")
        else:
            raise
