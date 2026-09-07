# 客户端_support_chat/ap/services/victdb/utlics.py 客户端_support_chat/ap/services/victdb/utitls.
def format_timestamp(timestamp):
    from datetime import datetime
    return datetime.utcfromtimestamp(timestamp).isoformat()
