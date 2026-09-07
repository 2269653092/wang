import os
from langchain_openai import OpenAIEmbeddings

# --- 配置--
# 确保设置 OpenAI_API_KEY 环境变量。
# 您可以设置在您的终端 像这样 :
# Linux/macOS: 导出 OpenAI_ API_ KEY ='您在这里的自动钥匙'
# Windows( comand 提示): 设置 OpenAI_ API_ KEY = 您的 api- key- here
# Windows (电壳): $env: OPENAI_ API_ KEY : "这里是你的钥匙"

API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("OPENAI_BASE_URL")
if not API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set.")

print(API_KEY)
print(BASE_URL)
MODEL_NAME = "text-embedding-ada-002"
# ----------------------

def generate_embeddings(texts, model=MODEL_NAME):
    """生成使用指定模式的文本列表的嵌入。 参考: 文本( 字符串列表 ) : 要嵌入的文本 。 模型( 字符串) : 要使用的嵌入模式的名称 。 返回: 列表 : 嵌入矢量列表 。"""
    # 配置 OpenAI 嵌入
    if BASE_URL:
        embeddings = OpenAIEmbeddings(
            model=model,
            openai_api_key=API_KEY,
            openai_api_base=BASE_URL
        )
    else:
        embeddings = OpenAIEmbeddings(
            model=model,
            openai_api_key=API_KEY
        )
    
    try:
        # 生成嵌入
        if isinstance(texts, str):
            return [embeddings.embed_query(texts)]
        elif isinstance(texts, list):
            return embeddings.embed_documents(texts)
        else:
            raise ValueError("Content must be either a string or a list of strings")
    except Exception as e:
        print(f"An error occurred: {e}")
        raise # 重新提出调试例外

if __name__ == "__main__":
    print(f"Generating embeddings using model: {MODEL_NAME}")
    
    # 示例案文
    texts_to_embed = [
        "The quick brown fox jumps over the lazy dog.",
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        "Embeddings are a powerful tool in natural language processing."
    ]
    
    try:
        embeddings = generate_embeddings(texts_to_embed)
        
        print(f"\nSuccessfully generated {len(embeddings)} embeddings.")
        print(f"Dimension of the first embedding: {len(embeddings[0])}")
        print(f"First 5 elements of the first embedding: {embeddings[0][:5]}")
        
        # 基本检查 : 所有嵌入的长度应该相同
        lengths = [len(e) for e in embeddings]
        if all(l == lengths[0] for l in lengths):
            print(f"All embeddings have consistent dimension: {lengths[0]}")
        else:
             print(f"Warning: Embedding dimensions are inconsistent: {lengths}")

    except Exception as e:
        print(f"Demo failed: {e}")