from os import environ
from dotenv import load_dotenv

load_dotenv()

class Config:
    OPENAI_API_KEY: str = environ.get("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = environ.get("OPENAI_BASE_URL", "")
    
    # 成本优化模型配置
    OPENAI_MODEL: str = environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
    OPENAI_DISABLE_THINKING: bool = environ.get(
        "OPENAI_DISABLE_THINKING",
        "true" if "deepseek" in OPENAI_BASE_URL.lower() else "false",
    ).lower() == "true"
    MAX_TOKENS: int = int(environ.get("MAX_TOKENS", "1000"))  # 限制控制成本的标识
    
    DATA_PATH: str = "./data/travel"
    LOG_LEVEL: str = environ.get("LOG_LEVEL", "DEBUG")
    SQLITE_DB_PATH: str = environ.get(
        "SQLITE_DB_PATH", "./data/travel/travel2.sqlite"
    )
    QDRANT_URL: str = environ.get("QDRANT_URL", "http://localhost:6333")
    QDRANT_KEY: str = environ.get("QDRANT_KEY", "")
    RECREATE_COLLECTIONS: bool = environ.get("RECREATE_COLLECTIONS", "False")
    LIMIT_ROWS: int = environ.get("LIMIT_ROWS", "100")
    
    # WooCommerce APIP 设置
    # WOCOMMERCE_API_URL 应该是Wordpress 基本 URL (例如“https://yourstore.com”) 。
    # 系统将自动附加“/wp-json/wc/v3”以创建完整 API 端点
    WOOCOMMERCE_CONSUMER_KEY: str = environ.get("WOOCOMMERCE_CONSUMER_KEY", "")
    WOOCOMMERCE_CONSUMER_SECRET: str = environ.get("WOOCOMMERCE_CONSUMER_SECRET", "")
    WOOCOMMERCE_API_URL: str = environ.get("WOOCOMMERCE_API_URL", "")
    
    # 表格提交 API 设置
    FORM_SUBMISSION_API_URL: str = environ.get("FORM_SUBMISSION_API_URL", "")
    
    # Blog 搜索 API 设置
    BLOG_SEARCH_API_URL: str = environ.get("BLOG_SEARCH_API_URL", "")

def get_settings():
    return Config()
