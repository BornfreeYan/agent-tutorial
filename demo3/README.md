[返回首页](../README.md) | [上一节：demo2](../demo2/README.md) | [下一节：demo4](../demo4/README.md)

# demo3：Tool Calling Demo

这一节开始真正进入 Agent 的关键能力：让模型不只“回答”，还可以“做事”。

和前面两节一样，`tool_demo.py` 刻意写得很干净、几乎没有注释——讲解全部放在这份 README 里。

**这一节只保留工具调用本身。** 工具是 `add`，一个纯计算函数，不碰文件、不碰网络。这是故意的：把一个真实的副作用（写文件、发请求、删数据）加进来，会顺带拖进一堆和工具调用无关的知识——路径解析、目录创建、覆盖保护、路径穿越防护。那些东西不属于这一节，等你看懂了这个闭环再回头加也来得及。`demo4`、`demo5` 里有能跑的文件工具版本，本节文末的附录保留了对应的讲解。

## 本节目标

- 理解工具 schema 是怎么描述给模型的
- 学会执行模型发起的工具调用
- 理解工具结果如何反馈回模型，形成闭环

## 入口文件

- [tool_demo.py](tool_demo.py)

## 运行方式

和前两节共用同一个环境变量，仓库根目录的 `.env` 里填好 `DEEPSEEK_API_KEY` 即可（做法见[首页的环境准备](../README.md)）。

然后在本项目根目录下，运行：

```bash
python demo3/tool_demo.py
```

启动后输入一个问题，例如：

```text
帮我算 3 + 5 等于几
```

这一节是**单次问答**：问一个、答一个，不像 `demo2` 那样进入 `exit/quit` 循环。原因很简单——这一节要看到的是“一次工具调用长什么样”，循环是另一个话题（`demo2` 已经讲过了）。

## 代码走读

### 一、这一节真正变了什么

前两节的模型只能“说话”：你发消息，它回文本。这一节它第一次能**让程序去做事**。

但这里有一个必须先建立的认知，否则后面全是玄学：

> **模型本身不会执行任何东西。** 它只是输出一段“我想调用这个函数、参数是这些”的**请求**；真正动手做计算的是**你的代码**。

所以“让 Agent 使用工具”的完整链路是这样的：

```text
你 → 模型：这是可用的工具清单
模型 → 你：我要调用 add，参数是 {"a": 3, "b": 5}          ← 这是 tool_calls
你（本地执行工具）→ 真正算出 8
你 → 模型：工具执行完了，结果是 {"ok": true, "result": 8}   ← 这是 role=tool 的消息
模型 → 你：3 + 5 = 8                                       ← 这是最终自然语言答复
```

这条链路就是本节的全部内容。“模型负责决策，代码负责执行”——这也是后面所有 Agent 安全边界的根源。

```text
数据流心智模型：
核心是 run_agent_turn() 控制：

TOOLS 常量 - 定义工具清单
    ↓
call_llm() - 把 messages + tools 发给模型
    ↓
模型返回 assistant 消息：
   - 要么是普通 content
   - 要么是 tool_calls（函数名 + JSON 字符串参数）
    ↓
如果是 tool_calls：
   解析 arguments
   execute_tool_call() 本地执行对应函数
   把结果作为 role="tool" 消息追加回 messages
   再发给模型
    ↓
直到模型不再返回 tool_calls，给出最终 content

所以就是，定义工具 → 带工具请求 → 模型点菜 → 本地执行 → 结果回传 → 再请求 → 直到不点菜。
只要记住这个，其他函数都是在这个骨架上加东西。
```

### 二、工具是怎么“描述”给模型的：`TOOLS`

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "计算两个数字之和。用户要求做加法时必须使用这个工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "第一个加数"},
                    "b": {"type": "number", "description": "第二个加数"},
                },
                "required": ["a", "b"],
            },
        },
    }
]
```

这个结构叫 **JSON Schema**，是给模型看的“函数说明书”。模型读它来决定：什么时候该用、该填哪些参数。

**它必须写在请求里，删不掉，但它是模板不是编程题。** 每个工具的 `parameters` 都是同一个形状——`type: object` 加一组 `properties`，最后 `required` 列出必填项。内容变了，骨架不变。所以正确的态度是：记住骨架，具体字段照抄。

三个细节值得注意：

1. **`description` 是写给模型的 prompt，不是写给人的注释。** 它直接决定模型调不调、调得准不准。这里那句“用户要求做加法时必须使用这个工具”是刻意的——没有它，模型很可能直接心算完就回答了，你连工具调用都看不到。
2. **`parameters` 就是参数的形状**：两个 number，`required` 列出必填项。模型填出来的值会照着这个结构来。
3. **工具能解决“模型做不到的事”才最有用。** `add` 其实是个弱例子——模型自己也会算。它的价值在于让你把闭环跑通；换成“读某个文件”“查当前时间”，工具就变成不可替代的了。这个判断标准在选工具时很有用：**如果模型自己也能猜出答案，工具的说服力就低。**

### 三、请求和响应多了什么：`call_llm()`

和 `demo2` 相比，请求体里多了两行：

| 参数            | 取值     | 作用                                                   |
| --------------- | -------- | ------------------------------------------------------ |
| `tools`       | `TOOLS` | 把“你有哪些工具”告诉模型                               |
| `tool_choice` | `"auto"` | 让模型自己决定要不要调用。设成别的值可以强制或禁止调用 |

返回值也变了：`call_llm()` 现在返回**整个 assistant message**，而不是只返回正文。原因是当模型决定调用工具时，**回复里可能没有正文，只有 `tool_calls`**：

```json
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call_00_abc123",
      "type": "function",
      "function": {
        "name": "add",
        "arguments": "{\"a\": 3, \"b\": 5}"
      }
    }
  ]
}
```

**这里最容易踩的坑：`arguments` 是一个 JSON 字符串，不是 JSON 对象。** 注意上面那串 `\"` —— 它整体是个字符串，里面装的才是 JSON 文本。所以拿到它必须先 `json.loads()` 才能当字典用。程序里那三行 `[工具调用]` / `[工具参数]` / `[工具结果]` 打印就是为这个准备的：跑一次，你能亲眼看到 `arguments` 带着引号的样子。

为什么设计成这样？因为模型输出的永远是**文本**。它生成了一段“看起来像 JSON 的文本”，API 就把这段文本原样塞进 `arguments` 字段里交给你。解析是客户端的事，这也是 `execute_tool_call()` 存在的理由。

最后一句题外话，专治“这些字段名我猜不出来”：`tool_calls`、`function.arguments`、`id` 这些**名字是 API 文档规定的事实，不是推导出来的**——所有人都是查文档、抄示例，或者让 AI 写第一版再跑一次看真实输出，没人靠猜。你需要记住的是第一节那条链路（模型只出请求、代码负责执行、结果要回传），字段名属于随时可查的语法。想马上看到真实结构，去做第一条练习。

另外 `content` 可能是 `null`：模型这一轮只想调工具，没什么话要说。

请求体里还有一行 `"thinking": {"type": "disabled"}`，看着像装饰，其实是在绕开一个具体的坑：**DeepSeek 在 thinking 模式下带 `tools` 时，要求把每一轮的 `reasoning_content` 原样回传，否则会返回 400**。这一节不打算引入思考链，所以直接关掉它。你暂时照抄这一行就行，等对消息结构更熟了再回来动它。

### 四、闭环骨架：`run_agent_turn()`（必须理解）

```python
for _ in range(MAX_TOOL_ROUNDS):
    assistant_message = call_llm(api_key=api_key, messages=messages)
    tool_calls = assistant_message.get("tool_calls") or []

    if not tool_calls:                      # 模型不再点菜 → 这就是最终答复
        return assistant_message.get("content") or "模型没有返回内容。"

    messages.append({                       # ① 记下模型自己的工具调用意图
        "role": "assistant",
        "content": assistant_message.get("content"),
        "tool_calls": tool_calls,
    })

    for tool_call in tool_calls:
        tool_result = execute_tool_call(tool_call)
        messages.append({                   # ② 把执行结果作为 tool 消息回传
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": json.dumps(tool_result, ensure_ascii=False),
        })
```

（上面省掉了三行打印，代码里还有 `[工具调用]` / `[工具参数]` / `[工具结果]`。）

**这二十行就是整个 Tool Calling 的核心。** 其他函数都是在它周围加东西——`TOOLS` 是它的输入，`call_llm()` 是它的传输，`execute_tool_call()` 是它的执行分支。只有两个动作，但每一处都有理由：

**① 为什么要把 `tool_calls` 写回历史？** 因为下一轮请求时，模型需要看到“我上一步决定调什么、参数是什么”，才能接着往下推理。消息历史是模型唯一的记忆，它自己的决策也必须在里面。

**② 为什么工具结果要用 `role="tool"` 回传、还要带 `tool_call_id`？** 因为模型没有别的方式知道你执行完了、执行结果是什么。而 `tool_call_id` 是用来**配对**的——一轮里模型可能同时请求调用多个工具，模型需要知道哪条结果是哪次调用的返回值。

还有一个语言细节：`content` 字段永远要求是字符串，所以工具结果要先 `json.dumps()` 变成字符串再放进去。这里 `ensure_ascii=False` 是为了让中文在后续上下文里保持可读。

**为什么 `not tool_calls` 就结束？** 模型的输出只有两种形态：要工具，或不要工具。不要工具时 `content` 就是最终答复，循环可以退出。这个判断也是后面 `demo5`、`demo6` 那个 ReAct 循环的原型。

**为什么需要 `MAX_TOOL_ROUNDS` 上限？** 万一模型反复返回损坏或截断的参数，循环可能永远退不出来。上限是保命用的。

**为什么这里的失败是 `return` 而不是抛异常**（对比 `demo2` 里的 `RuntimeError`）？因为这一节是单次问答，答完就退，没有“下一轮”可保护，所以直接把提示文字当结果返回就够了。

### 五、执行分发：`execute_tool_call()`（半模板）

```python
name = tool_call["function"]["name"]
raw_arguments = tool_call["function"]["arguments"]

try:
    arguments = json.loads(raw_arguments)          # 字符串 → 字典
except json.JSONDecodeError as exc:
    return {"ok": False, "error": f"参数不是合法 JSON：{exc}，请重新给出完整参数。"}

if name == "add":
    return add(arguments["a"], arguments["b"])

return {"ok": False, "error": f"未知工具：{name}"}
```

这个函数做的事：**把模型给的名字加上参数，路由到本地真正的函数**。骨架是“取名字 → 解析参数 → 按名字分发”，换个工具只改中间那两行。现在只有一个工具，所以用 `if` 就够了；工具一多，`demo6` 会把它换成一张“工具注册表”。

这里有个很实用的设计：**失败时返回一个 `{"ok": False, "error": ...}` 的字典，而不是抛异常。** 注意那句错误信息不是写给你看的，是**写给模型看的**——“请重新给出完整参数”是给模型的一次自我修正机会。如果直接抛异常，程序崩了，模型永远不知道自己给错了。**把错误变成对话的一部分**，这是 Agent 里一个反复出现的模式，后面的工具都会这么写。

### 六、`main()` 和 `demo2` 的差别

这一节的主体极简，因为前面两节已经把外壳讲完了：

```python
question = input("你：").strip()
if not question:
    raise SystemExit("没有输入内容。")

print(f"\n助手：{run_agent_turn(api_key=api_key, question=question)}")
```

对比 `demo2` 少了一大块东西，值得说清少的是什么：

|              | demo2                        | demo3                        |
| ------------ | ---------------------------- | ---------------------------- |
| 交互形态     | `while True` 循环          | 单次问答                     |
| 历史管理     | 每次追加 user / assistant    | 每次调用重新建 `messages`  |
| 记忆         | 有（保留最近 4 轮）          | 没有                         |
| 工具         | 没有                         | 有                           |

**这不是退步，是分离关注点。** `demo2` 解决“怎么持续对话”，`demo3` 解决“怎么让模型动手”。把两者叠在一起，你很难分清哪段代码是为哪个问题服务的。想让它变成持续对话也简单——把 `run_agent_turn()` 里的 `messages` 提到循环外面，就回到 `demo2` 的结构了。

还有一个细节：`raise SystemExit("...")` 会打印消息并以非零状态退出。用 `SystemExit` 而不是 `RuntimeError`，是因为“用户没输入”不是一个错误，只是没东西可做。真正缺 `DEEPSEEK_API_KEY` 时才抛 `RuntimeError`。

## 本节新增能力

- 定义 `tools` schema
- 让模型自动决定是否调用工具
- 执行本地工具函数
- 把工具执行结果再反馈给模型，让模型生成最终回复

## 内置工具函数

- `add(a, b)`

## 学习重点

- `TOOLS`：工具 schema 的骨架长什么样（模板，照抄）
- `execute_tool_call()`：如何解析模型生成的 JSON 参数
- `run_agent_turn()`：工具调用和模型回复如何形成闭环（必须理解）

这一节非常关键，因为它会让你看到一个事实：Agent 之所以“像代理”，不是因为它会聊天，而是因为它有了可以执行的动作空间。

## 建议练习

- 在 `call_llm()` 的 `return` 之前临时加一句 `print(json.dumps(response.json(), ensure_ascii=False, indent=2))`，跑一次“帮我算 3 + 5”，亲眼看清 `tool_calls`、`function.arguments` 返回时的真实结构，看完把这一行删掉
- 让它算一组大数的和，确认模型真的调了工具而不是心算
- 把 system prompt 里“必须调用 add 工具”那句删掉，看模型会不会直接心算，摸清 `description` 和 system prompt 的边界
- 新增一个工具，比如 `multiply(a, b)`，观察模型在两个工具之间怎么选
- 故意让它算一个除不尽的除法，看模型是对参数还是对工具挑错
- 把 `MAX_TOOL_ROUNDS` 改成 `1`，看模型在工具执行完之前就被截断会发生什么

## 与上一节相比多了什么

`demo2` 里模型只能说，`demo3` 里模型第一次具备了“行动能力”。从这一步开始，Agent 才真正从聊天程序走向“可执行任务”的系统。

## 附录：以后要给 Agent 一个“真实副作用”的工具时

这一节刻意把工具收窄成纯计算，所以“安全边界”的话题还没有出现。等你真要给 Agent 一个会动磁盘或网络的工具（写文件、发请求、删数据）时，就必须补上一整套防护，其中最小的一套是：

- **限制作用范围**：只允许操作一个指定目录，比如 `demo5/generated_files`
- **规范化路径再检查包含关系**：先用 `resolve()` 把 `..` 和符号链接展开，再判断目标是否落在允许的目录内。**顺序不能反**——先检查字符串前缀、后 resolve，会被 `notes/../../outside.md` 这类路径绕过
- **把失败也变成对话**：文件不存在、没有权限，都返回结构化的错误让模型自己调整，而不是让程序崩掉

下面这份实现现在住在 `demo5/tools.py`（和 `read_text_file`、`list_files` 放一起），`demo4/planning_demo.py` 里也有一份：

```python
def resolve_safe_path(relative_path: str) -> Path:
    cleaned_path = relative_path.strip().replace("\\", "/")   # 统一 Windows 反斜杠
    if not cleaned_path:
        raise ValueError("relative_path 不能为空。")

    relative = Path(cleaned_path)
    if relative.is_absolute():
        raise ValueError("relative_path 不能是绝对路径。")     # 第一层：拒绝绝对路径

    target = (GENERATED_FILES_DIR / relative).resolve()       # 第二层：归一化后做包含性检查
    base_dir = GENERATED_FILES_DIR.resolve()

    if target != base_dir and base_dir not in target.parents:
        raise ValueError("不允许访问 demo5/generated_files 目录之外的路径。")

    return target
```

- **`base_dir not in target.parents`** 是“包含性检查”：`target` 的祖先目录里必须有 `base_dir`，这才说明它真的落在允许的目录内。
- **`target != base_dir`** 这个额外条件是为了放行“刚好等于目录本身”的情况（虽然写文件时会失败，但那是另一类错误）。

真正动手写盘的部分长这样：

```python
GENERATED_FILES_DIR.mkdir(parents=True, exist_ok=True)
target_path.parent.mkdir(parents=True, exist_ok=True)

existed_before = target_path.exists()
if existed_before and not overwrite:
    return {
        "ok": False,
        "error": "文件已存在，且 overwrite 为 False。",
        "path": str(target_path),
    }

target_path.write_text(content, encoding="utf-8")
return {
    "ok": True,
    "path": str(target_path),
    "characters_written": len(content),
}
```

- **磁盘写入发生在这几行，而不是在模型那里**，回到第一节那句话。
- 两次 `mkdir`：一次保证根目录存在，一次保证 `notes/` 这样的子目录存在。`parents=True` 表示沿途缺失的目录一起建，`exist_ok=True` 表示已存在也不报错。
- `overwrite=False` 时拒绝覆盖，让“意外覆盖已有文件”变成一个可以被模型看见的错误，而不是静默的破坏。
- 返回值是一个描述结果的字典。它会先被 `json.dumps()` 成字符串，再作为 `role="tool"` 的内容发回模型——**所以“模型怎么知道成功了”，答案就是这个字典。** 配套的还有 `demo5` system prompt 里那句“不要假装工具已经执行成功，除非你已经看到了真实的 tool 结果”：一个负责让模型别乱说，一个负责给模型判断依据。

这类检查在安全上叫“路径穿越防护”。一句原则：**只要工具的参数来自模型或用户，就必须假设它是恶意的。**

[返回首页](../README.md) | [上一节：demo2](../demo2/README.md) | [下一节：demo4](../demo4/README.md)
