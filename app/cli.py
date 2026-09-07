# 主主. py

import uuid
import os  # 文件操作导入 OS 模块
from app.graph import multi_agentic_graph
from app.utils import download_and_prepare_db
from app.core.logger import logger
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage

def main():
    # 确保数据库得到下载和准备
    download_and_prepare_db()

    # 生成并保存图形可视化
    try:
        # 以 xray=True 生成图形对象以包含节点细节
        graph = multi_agentic_graph.get_graph(xray=True)
        # 使用美人鱼绘制图形为 PNG 图像
        graph_image = graph.draw_mermaid_png()
        graphs_dir = "./assets/graphs"
        if not os.path.exists(graphs_dir):
            os.makedirs(graphs_dir)
        image_path = os.path.join(graphs_dir, "multi-agent-rag-system-graph.png")
        with open(image_path, "wb") as f:
            f.write(graph_image)
        print(f"Graph saved at {image_path}")
    except Exception as e:
        logger.error(f"An error occurred while generating the graph visualization: {e}")
        print("Graph visualization could not be generated. Continuing without it.")

    # 为会话生成一个独特的线索ID
    thread_id = str(uuid.uuid4())

    # 带有客机 _ id 和 线索_ id 的配置
    config = {
        "configurable": {
            "passenger_id": "5102 899977",  # 视需要更新有效旅客身份证
            "thread_id": thread_id,
        }
    }

    # 用于跟踪打印信件 ID 以避免重复的变量
    printed_message_ids = set()

    try:
        while True:
            user_input = input("User: ")
            if user_input.strip().lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            # 通过图形处理用户输入
            events = multi_agentic_graph.stream(
                {"messages": [("user", user_input)]}, config, stream_mode="values"
            )

            for event in events:
                messages = event.get("messages", [])
                for message in messages:
                    if message.id not in printed_message_ids:
                        message.pretty_print()
                        printed_message_ids.add(message.id)

            # 检查中断
            snapshot = multi_agentic_graph.get_state(config)
            while snapshot.next:
                # 在敏感工具执行前发生中断
                user_input = input(
                    "\nDo you approve of the above actions? Type 'y' to continue; otherwise, explain your requested changes.\n\n"
                )
                if user_input.strip().lower() == "y":
                    # 继续执行
                    result = multi_agentic_graph.invoke(None, config)
                else:
                    # 向助理提供反馈
                    tool_call_id = snapshot.value["messages"][-1].tool_calls[0]["id"]
                    result = multi_agentic_graph.invoke(
                        {
                            "messages": [
                                ToolMessage(
                                    tool_call_id=tool_call_id,
                                    content=f"API call denied by user. Reasoning: '{user_input}'. Continue assisting, accounting for the user's input.",
                                )
                            ]
                        },
                        config,
                    )
                # 显示任何新信件的处理结果
                messages = result.get("messages", [])
                for message in messages:
                    if message.id not in printed_message_ids:
                        message.pretty_print()
                        printed_message_ids.add(message.id) 
                        
                # 更新快照
                snapshot = multi_agentic_graph.get_state(config)

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        print("An unexpected error occurred. Please check the logs for more details.")

if __name__ == "__main__":
    main()
