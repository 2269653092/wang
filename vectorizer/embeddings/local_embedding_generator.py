"""使用句式转换器进行本地嵌入生成器的本地嵌入生成器"""

import sys
import os
from typing import Union, List
import numpy as np

# 将项目 root 添加到导入的 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, project_root)

try:
    from vectorizer.core.settings import get_settings
    from vectorizer.core.logger import logger
    settings = get_settings()
except ImportError:
    # 直接执行的后退
    print("Running in standalone mode - using default settings")
    
    class MockSettings:
        LOCAL_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    
    settings = MockSettings()
    
    # 简单日志后退
    class SimpleLogger:
        def info(self, msg): print(f"INFO: {msg}")
        def error(self, msg): print(f"ERROR: {msg}")
        def warning(self, msg): print(f"WARNING: {msg}")
    
    logger = SimpleLogger()

# 全球示范实例
_model = None

def get_local_model():
    """获取或初始化本地嵌入模式"""
    global _model
    
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            model_name = settings.LOCAL_EMBEDDING_MODEL
            logger.info(f"Loading local embedding model: {model_name}")
            
            # 尝试装入模型
            _model = SentenceTransformer(model_name)
            logger.info(f"Successfully loaded local model: {model_name}")
            logger.info(f"Model embedding dimension: {_model.get_sentence_embedding_dimension()}")
            
        except ImportError:
            logger.error("sentence-transformers not installed. Install with: pip install sentence-transformers")
            raise
        except Exception as e:
            logger.error(f"Failed to load local model {model_name}: {str(e)}")
            logger.info("Trying fallback model: all-MiniLM-L6-v2")
            try:
                _model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Successfully loaded fallback model: all-MiniLM-L6-v2")
            except Exception as fallback_error:
                logger.error(f"Failed to load fallback model: {str(fallback_error)}")
                raise
    
    return _model

def generate_local_embedding(content: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
    """使用本地句子- 变换者模式 参数 生成嵌入 : 内容: 字符串或嵌入字符串列表 返回: 嵌入矢量作为浮点列表"""
    try:
        model = get_local_model()
        
        if isinstance(content, str):
            # 单字符串
            embedding = model.encode(content)
            return embedding.tolist()
            
        elif isinstance(content, list):
            # 字符串列表列表
            embeddings = model.encode(content)
            return [emb.tolist() for emb in embeddings]
            
        else:
            raise ValueError("Content must be either a string or a list of strings")
            
    except Exception as e:
        logger.error(f"Error generating local embeddings: {str(e)}")
        raise

def test_local_embeddings():
    """测试本地嵌入生成"""
    try:
        logger.info("Testing local embedding generation...")
        
        test_texts = [
            "Hello world",
            "This is a test sentence",
            "Local embeddings are working!"
        ]
        
        # 测试单字符串
        single_embedding = generate_local_embedding(test_texts[0])
        logger.info(f"Single embedding shape: {len(single_embedding)}")
        logger.info(f"First 5 values: {single_embedding[:5]}")
        
        # 测试多字符串
        batch_embeddings = generate_local_embedding(test_texts)
        logger.info(f"Batch embeddings shape: {len(batch_embeddings)} x {len(batch_embeddings[0])}")
        
        logger.info("Local embedding test successful!")
        return True
        
    except Exception as e:
        logger.error(f"Local embedding test failed: {str(e)}")
        return False

if __name__ == "__main__":
    # 直接运行时测试
    test_local_embeddings()