from vectorizer.vectordb.vectordb import VectorDB
from app.core.settings import get_settings
from langchain_core.tools import tool
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

settings = get_settings()
faq_vectordb = VectorDB(table_name="faq", collection_name="faq_collection")

@tool
def search_faq(
    query: str,
    limit: int = 2,
) -> List[Dict]:
    """根据自然语言查询搜索 FAQ 条目 。"""
    search_results = faq_vectordb.search(query, limit=limit)

    faq_entries = []
    for result in search_results:
        payload = result.payload
        content = payload.get("content", "")
        
        # 尝试从内容中解析\ {A 格式, 如果它遵循编号为\ {A 格式的话
        question = "General FAQ Information"
        answer = content
        category = "FAQ"
        
        # 查找编号的提问模式( 例如, “ 1 ” , 我能收到... ) 。
        import re
        question_match = re.search(r'^\d+\. (.+?)(?=\n|$)', content, re.MULTILINE)
        if question_match:
            question = question_match.group(1).strip()
            # 解压缩解答( 问题之后的所有内容)
            answer_start = content.find(question) + len(question)
            answer = content[answer_start:].strip()
        elif content.startswith('##'):
            # 处理部分标题
            lines = content.split('\n', 1)
            question = lines[0].replace('##', '').strip()
            answer = lines[1] if len(lines) > 1 else "See section content for details."
        
        faq_entries.append({
            "question": question,
            "answer": answer,
            "category": category,
            "chunk": content,
            "similarity": result.score,
        })
    return faq_entries

@tool
def lookup_policy(query: str) -> str:
    """咨询公司政策以检查是否允许某些选项。 在进行飞行更改或执行其他“  write” 事件之前先使用此选项 。"""
    faq_results = search_faq.invoke({"query": query, "limit": 2})
    if not faq_results:
        return "Sorry, I couldn't find any relevant policy information. Please contact support for assistance."
    
    policy_info = "\n\n".join([f"Q: {entry['question']}\nA: {entry['answer']}" for entry in faq_results])
    return f"Here's the relevant policy information:\n\n{policy_info}"
