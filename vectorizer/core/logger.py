import logging

# 创建自定义日志器
logger = logging.getLogger(__name__)

# 创建处理器
c_handler = logging.StreamHandler()
f_handler = logging.FileHandler('ta-vectordb.log')
c_handler.setLevel(logging.INFO)
f_handler.setLevel(logging.ERROR)

# 创建格式化器并将其添加到处理器
c_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
c_handler.setFormatter(c_format)
f_handler.setFormatter(f_format)

# 将处理器添加到日志器
logger.addHandler(c_handler)
logger.addHandler(f_handler)
