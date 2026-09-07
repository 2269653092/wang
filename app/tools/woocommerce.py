# 客户支持/聊天/应用程序/应用程序/服务/工具/软件/电子商务。

import httpx
from langchain_core.tools import tool
from app.core.settings import get_settings
from app.core.logger import logger
from typing import List, Dict, Optional

settings = get_settings()

@tool
def search_products(query: str, limit: int = 10) -> List[Dict]:
    """在 WooCommerce 中根据查询搜索产品。 参考: 查询: 搜索查询( 如产品名称、 类别) 限制: 要返回的产品的最大数量( 默认值: 10) 返回: 含有关键细节的产品词典列表 。"""
    logger.info(f"🔍 WooCommerce search_products called with query: '{query}', limit: {limit}")
    
    if not settings.WOOCOMMERCE_API_URL or not settings.WOOCOMMERCE_CONSUMER_KEY or not settings.WOOCOMMERCE_CONSUMER_SECRET:
        error_msg = "WooCommerce API credentials are not configured."
        logger.error(f"❌ {error_msg}")
        raise ValueError(error_msg)
    
    # 确保 URL 遵循正确的 WooCommerce REST API 格式
    base_url = settings.WOOCOMMERCE_API_URL.rstrip('/')
    logger.info(f"🌐 Base URL from settings: {base_url}")
    
    if not base_url.endswith('/wp-json/wc/v3'):
        # 如果 URL 不包含 API 路径, 请添加
        if '/wp-json/wc/v3' not in base_url:
            url = f"{base_url}/wp-json/wc/v3/products"
        else:
            url = f"{base_url}/products"
    else:
        url = f"{base_url}/products"
    
    logger.info(f"🌍 Final API URL: {url}")
    params = {
        "search": query,
        "per_page": min(limit, 100)  # WooCommerce API 限值
    }
    
    logger.info(f"📦 Request params: {params}")
    
    # 使用同步 httpx 客户端
    with httpx.Client(verify=False, timeout=30.0) as client:  # 禁用本地 dev 的 SSL 校验
        try:
            logger.info(f"🚀 Making API request to: {url}")
            response = client.get(
                url,
                params=params,
                auth=httpx.BasicAuth(settings.WOOCOMMERCE_CONSUMER_KEY, settings.WOOCOMMERCE_CONSUMER_SECRET)
            )
            
            logger.info(f"📊 Response status: {response.status_code}")
            response.raise_for_status()
            products = response.json()
            
            logger.info(f"✅ Successfully retrieved {len(products)} products")
            
            # 提取关键信息
            simplified_products = []
            for product in products:
                simplified_products.append({
                    "id": product.get("id"),
                    "name": product.get("name"),
                    "price": product.get("price"),
                    "description": product.get("short_description") or product.get("description", "")[:100] + "...",
                    "permalink": product.get("permalink"),
                    "sku": product.get("sku"),
                })
            
            return simplified_products
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP error occurred while searching products: {e} (Status: {e.response.status_code})")
        except httpx.TimeoutException as e:
            raise Exception(f"Timeout error while searching products. The WooCommerce server may be slow or unavailable: {e}")
        except httpx.ConnectError as e:
            raise Exception(f"Connection error while searching products. Check if WooCommerce server is running: {e}")
        except Exception as e:
            raise Exception(f"An error occurred while searching products: {e}")

@tool
def search_orders(search_type: str, search_value: str, limit: int = 10) -> List[Dict]:
    """在 WooCommerce 中根据特定标准搜索命令。 参考: 搜索类型: 要执行的搜索类型。 必须是 : “ email ”、“ name ” 或 “ id ” 。 搜索_ value: 要根据搜索类型搜索的值。 限制: 返回命令的最大数量( 默认值: 10) 。 返回: 含有关键细节的命令字典列表 。"""
    logger.info(f"🔍 WooCommerce search_orders called with search_type: '{search_type}', search_value: '{search_value}', limit: {limit}")
    
    if not settings.WOOCOMMERCE_API_URL or not settings.WOOCOMMERCE_CONSUMER_KEY or not settings.WOOCOMMERCE_CONSUMER_SECRET:
        error_msg = "WooCommerce API credentials are not configured."
        logger.error(f"❌ {error_msg}")
        raise ValueError(error_msg)
    
    # 验证搜索类型
    valid_search_types = ['email', 'name', 'id']
    if search_type not in valid_search_types:
        error_msg = f"Invalid search_type: {search_type}. Must be one of: {valid_search_types}"
        logger.error(f"❌ {error_msg}")
        raise ValueError(error_msg)
    
    # 确保 URL 遵循正确的 WooCommerce REST API 格式
    base_url = settings.WOOCOMMERCE_API_URL.rstrip('/')
    logger.info(f"🌐 Base URL from settings: {base_url}")
    
    if not base_url.endswith('/wp-json/wc/v3'):
        # 如果 URL 不包含 API 路径, 请添加
        if '/wp-json/wc/v3' not in base_url:
            url = f"{base_url}/wp-json/wc/v3/orders"
        else:
            url = f"{base_url}/orders"
    else:
        url = f"{base_url}/orders"
    
    logger.info(f"🌍 Final API URL for orders: {url}")
    
    # 基于搜索类型的构建参数
    params = {
        "per_page": min(limit, 100)  # WooCommerce API 限值
    }
    
    if search_type == 'email':
        # 通过客户电子邮件搜索
        params["customer_email"] = search_value
    elif search_type == 'name':
        # 为了搜索姓名,我们将搜索名名和姓的帐单
        params["search"] = search_value
    elif search_type == 'id':
        # 搜索身份资料,可以直接得到命令
        try:
            order_id = int(search_value)
            url = f"{url}/{order_id}"
            params = {}  # 具体顺序所需无参数
        except ValueError:
            # 如果不是有效的整数,则作为一般搜索处理
            params["search"] = search_value
    
    logger.info(f"📦 Request params for orders: {params}")
    logger.info(f"🔗 Request URL: {url}")
    
    # 使用同步的 httpx 客户端, 较长时间超时命令
    with httpx.Client(verify=False, timeout=60.0) as client:  # 增加定单超时
        try:
            logger.info(f"🚀 Making API request to orders endpoint: {url}")
            response = client.get(
                url,
                params=params,
                auth=httpx.BasicAuth(settings.WOOCOMMERCE_CONSUMER_KEY, settings.WOOCOMMERCE_CONSUMER_SECRET)
            )
            
            logger.info(f"📊 Order search response status: {response.status_code}")
            response.raise_for_status()
            
            # 处理单顺序响应( 使用 ID 搜索时)
            if search_type == 'id' and params == {}:
                order = response.json()
                orders = [order] if order else []
            else:
                orders = response.json()
            
            logger.info(f"✅ Successfully retrieved {len(orders)} orders")
            
            # 用于调试的日志搜索结果
            if len(orders) == 0:
                logger.warning(f"⚠️ No orders found for {search_type} search with value '{search_value}'.")
            
            # 提取关键信息
            simplified_orders = []
            for order in orders:
                simplified_orders.append({
                    "id": order.get("id"),
                    "status": order.get("status"),
                    "total": order.get("total"),
                    "currency": order.get("currency"),
                    "customer_note": order.get("customer_note"),
                    "date_created": order.get("date_created"),
                    "billing": {
                        "first_name": order.get("billing", {}).get("first_name"),
                        "last_name": order.get("billing", {}).get("last_name"),
                        "email": order.get("billing", {}).get("email"),
                    },
                })
            
            return simplified_orders
        except httpx.HTTPStatusError as e:
            raise Exception(f"HTTP error occurred while searching orders: {e} (Status: {e.response.status_code})")
        except httpx.TimeoutException as e:
            raise Exception(f"Timeout error while searching orders. The WooCommerce server may be slow or unavailable: {e}")
        except httpx.ConnectError as e:
            raise Exception(f"Connection error while searching orders. Check if WooCommerce server is running: {e}")
        except Exception as e:
            raise Exception(f"An error occurred while searching orders: {e}")

# 如有必要,可在此添加用于WooCommerce 操作的额外工具