# 项目学习指南（多智能体 RAG 客服系统）

> 本文档面向打算学习、改造此项目的开发者，内容包括：项目介绍、技术架构、目录结构、代码阅读顺序，以及改造前必须处理的清单。
 
                                                         
                                                             
## 一、项目介绍

这是一个基于 **多智能体（Multi-Agent）+ RAG（检索增强生成）** 的智能客服系统，fork 自 [ro-anderson/multi-agent-rag-customer-support](https://github.com/ro-anderson/multi-agent-rag-customer-support)，原项目是 LangChain 官方的多智能体客服教程代码。

### 它能做什么

用户通过自然语言与系统对话，系统像"一个客服经理带着一群专家"一样工作：

| 业务域 | 负责助手 | 数据来源 |
|---|---|---|
| 航班查询 / 改签 / 退票 | 航班助手 (flight_booking_assistant) | SQLite 旅行库 + Qdrant 向量库 |
| 酒店搜索 / 预订 / 取消 | 酒店助手 (hotel_booking_assistant) | SQLite + Qdrant |
| 租车预订 / 修改 / 取消 | 租车助手 (car_rental_assistant) | SQLite + Qdrant |
| 行程 / 活动推荐 | 行程助手 (excursion_assistant) | SQLite + Qdrant |
| 商品 / 订单查询 | WooCommerce 助手 | 外部电商 API |
| 表单提交 | 表单助手 (form_submission_assistant) | 外部 API |
| 公司政策 / 常识问答 | 主助手直接回答（lookup_policy / FAQ RAG） | Qdrant |

### 相比原项目新增的核心能力

1. **安全护栏（Guardrails）**：用户输入在进入主助手前，先经过两个检查代理——
   - 越狱防护：检测试图绕过系统指令的恶意输入，命中则直接拦截；
   - 相关性检查：判断问题是否在业务范围内（当前仅记录日志，未拦截，代码中有注释掉的拦截逻辑）。
2. **人工审核（GoHumanLoop）**：敏感操作（改签、取消订单等）在用户确认之外，还会通过 GoHumanLoop 框架发送给管理员（示例为飞书）做最终审批，形成"用户确认 + 管理员审批"双重保险。
3. **扩展业务域**：新增 WooCommerce 电商和表单提交两个助手。
4. **Web 界面**：FastAPI + 浏览器聊天页面，支持敏感操作的在线审批和操作日志查看。
5. **FAQ 增量更新服务**：定时扫描知识库目录（md/docx/pdf），增量更新向量索引。

### 核心架构一句话

> LangGraph 状态图 = 主助手（监督者）+ 6 个专业助手（专家）+ 安全护栏（入口闸机）+ 敏感工具中断（HITL）+ GoHumanLoop（人工终审）

系统流程图见 `assets/graphs/multi-agent-rag-system-graph.png`。

### 技术栈

- **Python 3.12+**，Poetry 依赖管理
- **LangChain / LangGraph**：多智能体编排、状态管理、图执行
- **Qdrant**：向量数据库（本地 Docker 或云服务）
- **SQLite**：旅行业务库（`travel2.sqlite`，来自 LangGraph benchmark，日期会被自动刷新到当前时间）
- **OpenAI API**：对话模型（默认 gpt-3.5-turbo，支持 `OPENAI_BASE_URL` 指向第三方代理）与嵌入模型
- **GoHumanLoop**：人工审核框架（飞书通知）
- **FastAPI + Jinja2**：Web 界面
- **APScheduler**：FAQ 定时更新

---

## 二、精简后的项目结构

```text
Multi-Agent/
├── app/                         # ★ 核心应用
│   ├── cli.py                   # 命令行入口：交互循环与用户确认
│   ├── web.py                   # FastAPI Web 入口
│   ├── graph.py                 # ★ StateGraph 节点、边、路由与中断
│   ├── chat_service.py          # Web 与 LangGraph 之间的调用层
│   ├── utils.py                 # 节点构造、异常回退和数据库准备
│   ├── core/                    # 状态、配置、日志、会话和人工审核
│   ├── assistants/              # 主助手与七个专业助手
│   ├── tools/                   # SQLite、Qdrant 和外部 API 工具
│   ├── guardrails/              # 越狱与相关性护栏
│   ├── vectordb/                # FAQ 增量更新所用的轻量向量库封装
│   └── templates/               # Web 聊天页面
├── vectorizer/                  # 离线向量化：分块、Embedding、Qdrant
│   ├── main.py                  # 批量生成五个 collection
│   ├── core/                    # 向量化配置与日志
│   ├── embeddings/              # API/本地嵌入实现
│   └── vectordb/                # 批量索引和检索实现
├── knowledge/                   # 知识库
│   ├── documents/               # md/docx/pdf 原始文档
│   ├── faq_config.yaml          # 数据源配置
│   └── updater/                 # APScheduler 增量更新服务
├── data/                        # SQLite、会话数据和运行日志
├── docs/                        # 学习指南与原项目说明
├── assets/                      # 系统流程图和演示图片
├── scripts/                     # 开发辅助脚本
└── drafts/                      # 迁移前学习草稿；不参与运行
```

> 注：`__pycache__`、`*.pyc`、`*.log`、`data/sessions/*.json`（会话数据）为运行产物，阅读时可忽略。

---

## 三、核心概念速览（读代码前先看）

### 1. 一次对话怎么流动（数据流）

```
用户输入
  ↓
fetch_user_info 节点 ── 查询当前用户航班信息，注入上下文
  ↓
guardrail_check 节点 ── 越狱检查（拦截则返回拒绝消息）→ 相关性检查（记录）
  ↓
primary_assistant ── 主助手判断：
  ├─ 普通问题 → 自己调用工具（search_flights / lookup_policy / 网络搜索）→ 回答
  └─ 专业问题 → 调用 ToXxx 分派工具 → 路由到对应专业助手
      ↓
专业助手（如 flight_booking_assistant）
  ├─ 安全工具（search_*）→ 直接执行
  └─ 敏感工具（book/cancel/update_*）
      ├─ ① LangGraph interrupt 暂停 → 等待用户确认
      └─ ② GoHumanLoop require_approval → 管理员（飞书）审批
  ↓
CompleteOrEscalate 工具 → 回到主助手总结 → END
```

### 2. 三类"节点"模式

每个专业助手在图里都是同一套结构，看明白一个就全明白了：

- **enter_xxx 节点**（`create_entry_node` 生成）：给主助手的委派请求回一个 ToolMessage，告知新助手"现在由你接管"，并 push 新的 dialog_state；
- **xxx 助手节点**：LLM + 工具绑定（Assistant 实例）；
- **xxx_safe_tools / xxx_sensitive_tools 节点**：ToolNode 执行工具，带错误 fallback。

### 3. 敏感操作如何触发双重审批

- `graph.py` 中 `interrupt_before` 指定了 4 个敏感工具节点，执行前 LangGraph 暂停；
- CLI 端（`main.py`）：暂停后询问用户 y/n；
- Web 端（`chat_service.py`）：暂停后把待审批操作存入会话，前端弹出审批按钮；
- 工具函数上还挂了 `@humanloop_adapter.require_approval` 装饰器——即使用户在界面上点了"通过"，工具真正执行时还会走 GoHumanLoop 让管理员审批。

### 4. RAG 用在哪里

- **政策问答**（`tools/lookup.py`）：从 Qdrant 的 faq_collection 检索 FAQ 相关内容再回答；
- **业务查询**（`search_flights` / `search_hotels` 等）：向量检索对应业务 collection，语义匹配代替 SQL 查询；
- 嵌入由 `vectorizer` 离线生成：SQLite 各业务表 + `knowledge/documents/` 文档 → 分块（≤2048 字符）→ 嵌入 → 存入 Qdrant。

### 5. 设计模式

- **策略模式**：所有助手继承 `Assistant` 基类，行为差异只在 prompt + 工具列表；
- **监督者模式（Chain of Responsibility）**：主助手不处理专业业务，只负责分派与汇总；
- **HITL（人在回路）**：敏感操作必须经过用户/管理员确认。

---

## 四、推荐阅读顺序

按"先懂意图、再懂骨架、后抠细节、最后跑通全链路"的原则，分四层：

### 第 1 层：建立全局认识（约 15 分钟，只读不写）

1. `README.md` —— 项目定位、功能、运行方式（项目作者写的介绍）。
2. `assets/graphs/multi-agent-rag-system-graph.png` —— 系统流程图，先"看图"理解节点与边。
3. `PROJECT_GUIDE.md`（本文档）第三、四节。

### 第 2 层：读懂核心对话系统（约 1~2 小时，本项目精华）

**按依赖顺序读，这样读 `graph.py` 时不会有陌生符号：**

1. `app/core/settings.py` —— 所有配置项，是全局依赖的起点。
2. `app/core/state.py` —— 只有 20 行：消息列表（add_messages 合并）+ 对话框栈，是图的"数据中枢"。
3. `app/assistants/assistant_base.py` —— `Assistant` 基类与 `CompleteOrEscalate`，理解"助手 = 提示词 + 工具 + 基类循环"。
4. `app/assistants/flight_booking_assistant.py` —— 挑一个**最简单且最典型**的专业助手，看懂"安全工具 vs 敏感工具"的划分。
5. `app/tools/hotels.py` —— 挑一个工具文件，看工具如何封装：向量检索（search_*）+ 直改 SQLite（book/cancel）+ `require_approval` 装饰器。
6. `app/assistants/primary_assistant.py` —— 主助手：prompt 里的分派规则 + `ToXxx` 委派工具定义。
7. `app/graph.py` —— **全项目最核心的文件**，此时读它基本无障碍：把上面所有部件"焊接"成图，并集中定义路由函数、护栏节点、中断列表。
8. `app/cli.py` —— CLI 入口，看 interrupt 如何在"图外"被消费（y/n 确认循环）。

### 第 3 层：安全机制与 Web 全链路（约 1 小时）

9. `app/guardrails/guardrail_agents.py` —— 两个结构化输出的检查代理（便宜模型 gpt-4o-mini + temperature=0）。
10. `app/core/humanloop_manager.py` —— GoHumanLoop 适配器配置（注意：里面有硬编码密钥，见第五节清单）。
11. `app/chat_service.py` —— Web 端如何复用图：`process_user_message` 处理流式输出与 HITL 暂停，`process_user_decision` 执行审批结果。
12. `app/web.py` —— FastAPI 路由与前端页面的对应关系。

### 第 4 层：数据链路与扩展模块（按需阅读）

13. `vectorizer/main.py` → `vectorizer/vectordb/vectordb.py` —— 向量化管线：分块、异步嵌入（限流重试）、upsert。
14. `vectorizer/embeddings/embedding_generator.py` —— 嵌入 API 封装（含模型探测逻辑）。
15. `knowledge/updater/update_service.py` —— 定时增量更新知识库索引（APScheduler + 文件修改时间判断）。
16. `app/core/user_data_manager.py` —— JSON 文件会话存储（当前"内存"方案的替代品）。

### 读完后的自我检验题

- 新增一个"包裹查询助手"需要动哪几个文件？（答案：新建 assistant + tools + 在 graph.py 注册节点/路由/中断，参考 woocommerce 的三个助手）
- 敏感工具与安全工具的本质区别在哪？（答案：是否在 `interrupt_before` 列表中 + 是否挂 `require_approval` 装饰器）
- 为什么主助手 prompt 强调"一次只委派一个助手"？（答案：dialog_state 是单值栈，多路委派会互相覆盖）

---

## 五、改造前必须处理的清单（重要）

原作者把以下内容写死在代码里，改造成自己的项目前**逐项检查**：

| 位置 | 问题 | 建议 |
|---|---|---|
| `humanloop_manager.py:9` | **硬编码了真实的 GoHumanLoop API Key** | 改为从 `.env` 读取（`environ.get("GOHUMANLOOP_API_KEY")`），删掉这行字面量 |
| `main.py:37` 与 `app/web.py:55` | `passenger_id` 硬编码为 `"5102 899977"` | 改为从会话/登录态注入 |
| `.env` | 各 API Key、`OPENAI_BASE_URL`（原项目用第三方中转）、Qdrant 云地址 | 全部换成你自己的 |
| `graph.py:466-472` | `interrupt_before` 只列了 4 个旅行节点；新增敏感工具后要同步加入 | 按业务需要扩展 |
| `guardrail_agents.py` | 相关性检查只记录日志不拦截（拦截代码被注释） | 按需开启拦截，或调整为"转人工" |
| `data/sessions/` | 会话数据存 JSON 文件，重启即散乱 | 长期使用建议换 SQLite/Redis |
| `knowledge/faq_config.yaml` + `knowledge/documents/` | 知识库文档还是原作者的内容（含"阿里云大模型ACP考试大纲"） | 替换成你自己的知识库 |

### 建议的最小改造路线

1. 先跑通：`.env` 配好自己的 Key → `docker compose up qdrant -d` → `vectorizer` 建索引 → CLI 版对话；
2. 清密钥：处理第五节的硬编码项；
3. 换业务：替换 `knowledge/documents/` 知识库，改主助手 prompt 中的业务描述（现在是 Swiss Airlines）；
4. 加功能：按 woocommerce 助手的模式复制一份"新助手"骨架，改 prompt、工具、路由即可。

---

## 六、执行流程图（文字版）

> 共 3 张图：**图 1 全局主流程** → **图 2 专业助手子图（以航班为例）** → **图 3 敏感操作双重审批与数据来源**。
> 每个节点标注了作用与代码文件位置（行号为当前版本，路径均以项目根目录为基准）。

### 【图 1】全局主流程：一次完整对话的执行路径

```
 ┌────────────────────────────────────────────────────────────────┐
 │ 0. 入口层（两种入口，殊途同归）                                  │
 │   CLI 版：app/cli.py:46-101              │
 │     while 循环 input() → stream(graph) → 敏感操作时问 y/n       │
 │   Web 版：app/web.py:76（POST /chat）                  │
 │     └→ services/chat_service.py:29 process_user_message()      │
 │         作用：驱动图执行、发现 interrupt 后存"待审批操作"、记日志 │
 └───────────────────────────────┬────────────────────────────────┘
                                 │ {"messages":[("user",输入)]}, config
                                 │   config 含 thread_id / passenger_id
                                 ▼
 ┌────────────────────────────────────────────────────────────────┐
 │ ① fetch_user_info  节点                                         │
 │    作用：查出当前用户已订航班，转成字符串注入 user_info 上下文，  │
 │          让主助手"知道自己是谁"                                 │
 │    文件：app/graph.py:94-100                                    │
 │          app/services/tools/flights.py: fetch_user_flight_     │
 │            information（SQLite 查询）                           │
 │          app/services/utils.py:160 flight_info_to_string()     │
 └───────────────────────────────┬────────────────────────────────┘
                                 ▼
 ┌────────────────────────────────────────────────────────────────┐
 │ ② guardrail_check  节点（安全护栏 · 入口闸机）                   │
 │    作用：a) 越狱检查——命中则返回拒绝消息，正常业务被阻断；       │
 │          b) 相关性检查——不相关仅记日志（graph.py:134 有注释掉的 │
 │            拦截代码，可按需打开）                               │
 │    文件：app/graph.py:102-145                                   │
 │          app/services/guardrails/guardrail_agents.py            │
 │          （两个结构化输出代理：gpt-4o-mini + temperature=0）     │
 └───────────────────────────────┬────────────────────────────────┘
                                 ▼
 ┌────────────────────────────────────────────────────────────────┐
 │ ③ primary_assistant  节点（主助手 · 监督者）                     │
 │    作用：判断用户意图。                                        │
 │          · 普通问题 → 自己调用工具直接回答                       │
 │          · 专业问题 → 调用 ToXxx 委派工具，路由给专业助手        │
 │    文件：app/graph.py:404-443（节点注册 + route_primary_        │
 │          assistant 路由函数，graph.py:410）                    │
 │          app/services/assistants/primary_assistant.py          │
│          （prompt 分派规则 + 6 个 ToXxx 委派工具定义）           │
 │    工具：primary_assistant_tools = [DuckDuckGo 网络搜索,         │
 │          search_flights, lookup_policy(政策RAG),               │
 │          ToFlightBookingAssistant, ToBookCarRental,            │
 │          ToHotelBookingAssistant, ToBookExcursion,             │
 │          ToWooCommerceProducts, ToWooCommerceOrders,           │
│          ToFormSubmission]                                     │
 └──────┬───────────────────────────┬────────────────────────┬────┘
        │ 普通问题                    │ 调用了 ToXxx 委派工具    │ 无工具调用
        ▼                            ▼                        ▼
 primary_assistant_tools        enter_xxx 入口节点        等待用户补充信息
 （graph.py:405-407）          （如 enter_update_flight，   （回到③再判断）
   执行工具→回答                graph.py:152，由
        │                      route_primary_assistant        │
        ▼                      按工具名路由到这里）            ▼
   ── END ──                         │                  ── END ──
                                     ▼
                              进入【图 2】专业助手区
```

### 【图 2】专业助手子图：以"航班助手"为例

> 7 个专业助手在图中是**完全同构**的一套模式（入口节点 → 助手节点 → 安全/敏感工具节点），
> 看明白航班这一个，其余 6 个只是换 prompt、工具、路由函数名。对照表见下方。

```
          （来自【图1】③ enter_update_flight，graph.py:152-156）
                                     ▼
 ┌────────────────────────────────────────────────────────────────┐
 │ ④ enter_update_flight  入口节点                                 │
 │    作用：给主助手的委派请求回一条 ToolMessage"现在由你接管"，    │
 │          并 push dialog_state="update_flight"                  │
 │    文件：app/graph.py:152-156                                  │
 │          app/services/utils.py:19 create_entry_node()          │
 │            （通用工厂函数，所有 enter_xxx 都由它生成）           │
 └──────────────────────────────────┬─────────────────────────────┘
                                     ▼
 ┌────────────────────────────────────────────────────────────────┐
 │ ⑤ update_flight  助手节点（专业助手 = prompt + 工具 + Assistant）│
 │    作用：理解用户改签/退票意图，选工具执行；                     │
 │          用户改主意或任务完成 → CompleteOrEscalate 交回主助手   │
 │    文件：app/graph.py:156                                      │
 │          app/services/assistants/flight_booking_assistant.py   │
 │    工具划分：                                                   │
 │      safe      = [search_flights, CompleteOrEscalate]          │
 │      sensitive = [update_ticket_to_new_flight, cancel_ticket]  │
 │    路由：route_update_flight（graph.py:167）按工具名分流         │
 └──────────────┬──────────────────────────────┬──────────────────┘
                │ 安全工具                      │ 敏感工具
                ▼                              ▼
  ⑥ update_flight_safe_tools            ⑦ update_flight_sensitive_tools
     节点（graph.py:158-160）              节点（graph.py:162-164）
     直接执行（查航班/政策）               【HITL 中断】执行前被
        │                                 interrupt_before 拦截
        ▼                                 （graph.py:466-472）
  回到 ⑤ 继续对话                           │
        │                                   ▼
        └──────► 任务完成 ──► CompleteOrEscalate 触发
                    （graph.py:192 route_update_flight_tools 检测到
                     "Task completed/escalated to main assistant"）
                          │
                          ▼
                    回到【图1】③ 主助手 → 总结 → END
```

**其余 6 个专业助手对照表**（与上图结构完全一致，仅替换内容）：

| 业务域 | enter 节点 | 助手节点 | 安全工具 | 敏感工具 | 对应文件 |
|---|---|---|---|---|---|
| 租车 | enter_book_car_rental | book_car_rental | search_car_rentals | book/update/cancel_car_rental | `assistants/car_rental_assistant.py` + `tools/cars.py` |
| 酒店 | enter_book_hotel | book_hotel | search_hotels | book/update/cancel_hotel | `assistants/hotel_booking_assistant.py` + `tools/hotels.py` |
| 行程 | enter_book_excursion | book_excursion | search_excursions | book/update/cancel_excursion | `assistants/excursion_assistant.py` + `tools/excursions.py` |
| 电商 | enter_woocommerce | woocommerce | search_products / search_orders | 无（只读查询） | `assistants/woocommerce_assistant.py` + `tools/woocommerce.py` |
| 表单 | enter_form_submission | form_submission | submit_form | 无 | `assistants/form_submission_assistant.py` + `tools/forms.py` |

> 以上节点的注册、路由函数、条件边都在 `app/graph.py` 中（新增助手就是照抄这几段）。

### 【图 3】敏感操作的双重审批（HITL + GoHumanLoop）与数据来源

以用户请求"取消机票"为例，走到【图 2】的 ⑦ 节点后：

```
⑦ update_flight_sensitive_tools 即将执行（graph.py interrupt_before 拦截暂停）
   ▼
━━━━━━ 第 1 层审批：用户确认（HITL · 人在回路）━━━━━━
CLI 版：main.py:64-96
    get_state() 发现 snapshot.next 非空 → 询问 y/n
    ├─ y       → graph.invoke(None) 继续执行
    └─ 其他    → 回 ToolMessage"API call denied by user..."，助手重新应答
Web 版：chat_service.py:113-178
    process_user_message() 发现中断 → 待审批操作(工具名+参数)存入会话
    → app/core/user_data_manager.py（JSON 文件）
    → 前端 chat.html 弹出审批按钮
    → POST /approve-action（app/web.py:111）或 /reject-action（:132）
    → chat_service.py:338 process_user_decision() 按审批结果执行/拒绝
   │ 用户同意                        │ 用户拒绝
   ▼                                ▼
 继续执行敏感工具                工具不执行，助手给出被拒提示
   ▼
━━━━━━ 第 2 层审批：管理员人工审核（GoHumanLoop）━━━━━━
 每个敏感工具函数头挂着装饰器：
   @tool
   @humanloop_adapter.require_approval(execute_on_reject=False)
   （见 tools/hotels.py:38、tools/flights.py 的改签/退票等）
   ▼
 app/core/humanloop_manager.py 配置 APIProvider → 飞书应用
   （默认 127.0.0.1:9800/api，超时 300s）
   ▼
 管理员在飞书收到审批卡片 → 批准 / 拒绝
   │ 批准                          │ 拒绝
   ▼                              ▼
 工具函数体真正执行              不执行（execute_on_reject=False）
 （改 SQLite / 调外部 API）       返回"已被管理员拒绝"的结果
   ▼
 执行结果写回 messages → 助手总结 → 回到主助手 → END
```

**各模块的数据来源（谁读写什么）：**

```
 SQLite   travel2.sqlite（data/travel/）
          · 航班/酒店/租车/行程业务数据，工具层直接 SQL 读写
          · 首次运行由 services/utils.py:61 download_and_prepare_db()
            自动下载并刷新日期到当前时间
 Qdrant   5 个 collection：faq / flights / hotels / car_rentals / excursions
          · 写入：vectorizer/main.py 离线批量生成嵌入后 upsert
          · 读取：services/vectordb/vectordb.py（复用 VectorDB.search）
 Web会话  data/sessions/*.json
          · 会话历史、待审批操作、操作日志（user_data_manager.py）
 外部 API WooCommerce / 表单（各 tools/*.py）
          飞书审批（humanloop_manager.py → GoHumanLoop）
 知识库    knowledge/documents/（md/docx/pdf 原始文档）
          · 静态：vectorizer 全量向量化
          · 增量：knowledge/updater/update_service.py 定时扫描（APScheduler）
