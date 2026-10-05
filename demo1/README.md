[返回首页](../README.md) | [下一节：demo2](../demo2/README.md)

# demo1：Hello World

这是整个教程的起点，目标只有一个：把一次最基础的大模型调用跑通。

`hello_world.py` 刻意写得很干净、几乎没有注释——这一节的讲解全部放在这份 README 里，代码只保留结构。建议对照着读。

## 本节目标

- 理解一次最小 LLM 调用需要哪些消息和参数
- 学会用 `requests` 请求 DeepSeek Chat API
- 看懂模型响应里的内容和 token 使用情况

## 入口文件

- [hello_world.py](hello_world.py)

## 运行方式

先确保已经安装根依赖，并配置好 `DEEPSEEK_API_KEY`。

推荐在仓库根目录的 `.env` 里填好（做法见[首页的环境准备](../README.md)）：

```dotenv
DEEPSEEK_API_KEY=你的 DeepSeek API Key
```

`hello_world.py` 会自己读取这个文件。如果你更想临时试一下，也可以只在当前终端会话里设置，效果一样：

```powershell
$env:DEEPSEEK_API_KEY="你的 API Key"
```

然后在本项目根目录下，运行：

```bash
python demo1/hello_world.py
```

## 代码走读

### 一、环境变量是怎么进来的

```python
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
```

这行在文件顶部、任何函数运行之前执行，作用是把仓库根目录的 `.env` 读进进程环境变量。所以后面 `os.getenv("DEEPSEEK_API_KEY")` 才能拿到值。

三个细节值得留意：

- 路径是用 `Path(__file__)` 拼出来的，**不依赖你在哪个目录执行命令**。如果写成 `load_dotenv(".env")`，那么你从别的目录运行就会读不到。
- .resolve()拆成绝对路径，然后单个.parent代表本文件所处的文件夹，再加一个.parent代表本文件夹的上一级文件夹，那就是.env所在之处，每个项目的.env路径可能都不一致，自己调整。
- `load_dotenv()` 默认**不覆盖已经存在的变量**。所以临时 `$env:DEEPSEEK_API_KEY="..."` 设的值会优先于 `.env`，方便你换个 Key 做对比测试。如果需要覆盖，可以在load_dotenv()加上`override=True`，这就是覆写变量。

### 二、消息是怎么组织的：`build_messages()`

```python
[
    {
        "role": "system",
        "content": (
            "你是一个面向初学者的 Python 和 agent 助手。"
            "回答时尽量简洁、友好，并在必要时给出清晰步骤。"
        ),
    },
    {
        "role": "user",
        "content": "请用一句话介绍什么是 Agent，并给一个生活中的类比。",
    },
]
```

一次调用要发的是一个**消息列表**，每条消息只有两个键：

| 键          | 含义                                                                               |
| ----------- | ---------------------------------------------------------------------------------- |
| `role`    | 谁在说话。`system` 是给模型设定的角色和行为准则，`user` 是用户提出的问题或请求 |
| `content` | 说的话本身                                                                         |

`system` 的权重不低，它决定了回答的语气、详略和边界。这一节后面第一个练习就是改它。

现在列表里只有两条消息，后面每一节都会往这里加东西：`demo2` 加 `assistant`（模型自己的历史回复，这就是"记忆"），`demo3` 加 `tool`（工具执行结果）。

### 三、一次请求包含什么：`call_llm()`

```python
def call_llm(api_key: str, messages: list[dict[str, str]]) -> dict:
    response = requests.post(
        API_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={
            "model": MODEL_NAME,
            "messages": messages,
            "stream": False,
            "thinking": {"type": "disabled"},
            "max_tokens": 200,
            "temperature": 0.7,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()
```

这个函数只有五个动作：组装请求 → 发出去 → 检查有没有出错 → 解析回来的数据 → 返回。下面按这个顺序拆开讲。

#### 3.1 先建立一件事：HTTP 请求就是四样东西

一个 HTTP 请求由四部分组成，`requests.post()` 的参数和它们一一对应：

| 部分       | 是什么                                     | 在这里                     |
| ---------- | ------------------------------------------ | -------------------------- |
| 方法 + URL | 对哪个地址、做什么动作                     | `requests.post(API_URL)` |
| headers    | 关于这次请求的**附加说明**，不是内容 | `headers={...}`          |
| body       | 真正要传输的数据                           | `json={...}`             |
| 超时       | 等多久算失败                               | `timeout=60`             |

模型的正文参数全部装在 body 里。换句话说，**body 里是"内容"，headers 里是"关于内容的说明"**。

body 里这几个参数：

| 参数            | 本节取值                      | 作用                                                         |
| --------------- | ----------------------------- | ------------------------------------------------------------ |
| `model`       | `deepseek-flash`            | 用哪个模型（`deepseek-v4-flash` 是已退役的旧名，仍能调用） |
| `messages`    | `build_messages()` 的返回值 | 这次要发送的对话                                             |
| `stream`      | `False`                     | 非流式输出，一次性返回完整结果，方便先看全貌                 |
| `thinking`    | `{"type": "disabled"}`      | 关掉模型的思考模式，让返回更接近普通聊天模型                 |
| `max_tokens`  | `200`                       | 限制输出长度，避免教程示例返回太长                           |
| `temperature` | `0.7`                       | 控制随机性，适度降低能让教程输出更稳定                       |

`thinking` 那行值得留意：思考模式**默认是开启的**，而且开启后 `temperature` 会失效（官方文档明确说不支持该参数，设了不报错但无效）。所以这行不是装饰，它正是 `temperature` 能生效的前提。

#### 3.2 `requests.post()` 的参数

| 参数           | 类型         | 作用                                                                                                                         |
| -------------- | ------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| 第一个位置参数 | `str`      | 请求地址。`requests.post(url, ...)` 等价于 `requests.request("POST", url, ...)`，前者只是后者的快捷写法                  |
| `headers`    | `dict`     | 请求头                                                                                                                       |
| `json`       | dict 或 list | 请求体。传 Python 对象即可，**requests 会自动把它序列化成 JSON 文本**，并把 `Content-Type` 设成 `application/json` |
| `timeout`    | 数字         | 等待响应的秒数。超时会直接抛异常，避免程序永远卡住                                                                           |

这里有个值得知道的细节：既然 `json=` 会自动设置 `Content-Type: application/json`，那代码里手写的那个 `"Content-Type": "application/json"` 其实是**冗余的**，删掉也不影响运行。留着的价值是让你一眼看到这次请求带了什么头——读别人的代码时会经常见到这种"显式写出来"的风格。如果改用 `data=` 传字符串，requests 就不会替你做这两件事，那时 `Content-Type` 就必须自己写。

#### 3.3 `headers` 到底是什么

先把概念讲清楚：**headers 不参与"内容"，它是关于这次请求本身的说明。**

类比寄快递：body 是包裹里的东西，headers 是贴在箱子外面的面单——收件人是谁、里面是什么、要怎么处理。快递公司会**先看面单，再决定要不要拆包裹**。HTTP 服务器也是一样。

这个请求里有两个头：

| 头                | 取值                 | 作用                                                                                                       |
| ----------------- | -------------------- | ---------------------------------------------------------------------------------------------------------- |
| `Content-Type`  | `application/json` | 告诉服务器："我发给你的 body 是 JSON，请按 JSON 解析。" 不带或写错，服务器可能把 body 当成一整段普通字符串 |
| `Authorization` | `Bearer sk-...`    | 告诉服务器："我是谁、我有没有权限。" 这是**鉴权**，没有它连门都进不去                                |

`Authorization` 的值有固定格式：`Bearer` + 一个空格 + 你的 Key。`Bearer` 是一种鉴权方案的名称，字面意思是"持有者"——谁拿着这个 token，谁就被当作这个身份。DeepSeek 用的是这一套；换到别的服务时要看它的文档，可能是 `Bearer`，也可能是 `Basic`（用户名密码的 base64）或其他方案。

如果这个头写错或漏了，你会在 `raise_for_status()` 那里**立刻收到 401**，而不是收到一个含糊的"模型答不上来"。这正是把鉴权和内容分开的价值：错误类型一眼可分。

#### 3.4 `response` 是什么

`requests.post()` 的返回值不是"模型回复"，而是一个 `Response` 对象——它是**这一次 HTTP 交互的完整记录**。最常用的四样：

| 属性 / 方法              | 内容                                                           |
| ------------------------ | -------------------------------------------------------------- |
| `response.status_code` | 状态码，比如`200`、`401`、`429`                          |
| `response.headers`     | 服务端返回的响应头                                             |
| `response.text`        | 响应体，**原始字符串**。对这次调用来说就是一坨 JSON 文本 |
| `response.json()`      | 把响应体按 JSON 解析成 Python 对象（字典 / 列表）              |

#### 3.5 `raise_for_status()` 为什么值得单独记

HTTP 状态码分五段，第一位数就说明了结果：

| 段  | 含义                   | 你会碰到的                                                                 |
| --- | ---------------------- | -------------------------------------------------------------------------- |
| 2xx | 成功                   | `200` 正常返回                                                           |
| 4xx | **你**这边的问题 | `400` 参数写错、`401` Key 错或没带、`402` 余额不足、`429` 触发限流 |
| 5xx | **服务端**的问题 | `500`、`503`，一般稍后重试                                             |

`raise_for_status()` 就一句话：**状态码不是 2xx，就抛异常。**

不写它会怎样？`requests` 不会因为 401 或 429 报错，你的程序会继续往下走，然后 `response.json()` 照样能解析出一段"错误信息"的 JSON，你的代码把它当成正常回复打印出来。**错误会以最难排查的方式出现在很远的地方。** 所以这是一个必须养成的习惯：

> 拿到 response，先 `raise_for_status()`，再解析。

它抛出的异常类型是 `requests.exceptions.HTTPError`（它是 `requests.exceptions.RequestException` 的子类），异常信息里带着状态码和 URL，方便排查。

一个容易误解的点：`raise_for_status()` **只检查 HTTP 状态码**，管不了网络层的问题。连不上服务器、DNS 解析失败、超时，这些会在 `requests.post()` 那一行就抛异常（`ConnectionError`、`Timeout` 等），根本走不到这里。

#### 3.6 `response.json()` 的方向：是"解析回复"，不是"发给模型"

这里纠正一个理解：**`response.json()` 不是在给模型发数据，方向恰好相反——它是把模型的回复解析出来。**

完整时序是这样的：

1. 你把字典交给 `json=`，requests 把它**序列化**成 JSON 文本，随请求发出去（这一步发生在 `requests.post()` 内部）
2. 服务器（模型侧）读请求、生成回复，把结果**以 JSON 文本的形式**放进响应体
3. 你这一侧拿到的 `response.text` 就是那段**字符串**，此刻它还是"死"的文本
4. `response.json()` 把这个字符串**解析**回 Python 字典

所以 `result` 是一个 Python 字典，后面才能用 `result["choices"][0]` 这种下标去取。一次往返的完整形状是：

```text
字典 --json= 序列化--> JSON 文本 --网络--> 服务器
                                            |
字典 <--response.json() 解析-- JSON 文本 <--服务器
```

如果响应体不是合法 JSON，`response.json()` 会抛 `requests.exceptions.JSONDecodeError`（它是 `json.JSONDecodeError` 的子类）。

#### 3.7 `json.dumps()` 在 `main()` 里干什么

```python
print(json.dumps(messages, ensure_ascii=False, indent=2))
```

`json.dumps` 和上一条的 `response.json()` 是**一对反操作**：

| 函数                          | 方向                              |
| ----------------------------- | --------------------------------- |
| `json.dumps(obj)`           | Python 对象 →**JSON 文本** |
| `json.loads(text)`          | JSON 文本 → Python 对象          |
| `json.dump` / `json.load` | 同上，只是直接读写文件对象        |

`dumps` 的 s 就是 string，即"输出成字符串"。所以这行**不是**"把一个 JSON 拆成数组"，而是反过来——**把一个 Python 列表渲染成人类可读的 JSON 文本**，目的仅仅是打印得好看一点。`print(messages)` 当然也能打印，但那是 Python 的格式（单引号、全挤在一行）；`json.dumps` 把它变成 JSON 标准格式。

两个参数：

| 参数                   | 默认         | 这里为什么这么写                                                       |
| ---------------------- | ------------ | ---------------------------------------------------------------------- |
| `ensure_ascii=False` | `True`     | 默认会把中文转义成`\u4f60\u597d` 这种编码，设成 `False` 才原样显示 |
| `indent=2`           | 无（不换行） | 每层缩进 2 个空格并换行，嵌套结构才看得清                              |

`ensure_ascii` 这个名字有点绕：它问的是"要不要保证输出全是 ASCII 字符"。默认 `True` 的意思是"要保证"，于是中文必须被转义成 ASCII 能表示的 `\uXXXX`。设成 `False` 就是"不用保证"，中文原样输出。

#### 3.8 这些要背下来吗

不用。需要变成肌肉记忆的只有四件事：

1. `requests.post(url, headers=..., json=..., timeout=...)` 这个调用形态——四个参数的名字和位置
2. 鉴权靠 `headers` 里的 `Authorization: Bearer <key>`
3. **拿到 response 先 `raise_for_status()`，再 `.json()`**
4. `json=`（发出去，自动序列化）和 `response.json()`（收回来，解析）是两个方向，别搞反

其余都是查文档就能恢复的记忆：具体是 400 还是 429、`Bearer` 之外的鉴权方案、`json.dumps` 还有哪些参数。真正重要的是这四条构成的**流程**：

```text
准备 headers 和 body → POST → 查状态码 → 解析
```

后面所有 demo（包括 `demo6` 的框架层）都在重复这个流程，只是包装越来越多。

最后一点：`requests` 这条路径不经过任何 SDK，所以你能清楚看到一次模型调用到底发了什么、收回了什么。这也是这一节刻意不换成官方 SDK 的原因。

### 四、响应怎么读：`main()`

```python
result["choices"][0]["message"]["content"]   # 模型回复的正文
result.get("usage")                          # 这次用掉的 token
```

DeepSeek 用的是 OpenAI 兼容格式，正文固定在这个位置上。`main()` 里打印了三段：发给模型的消息、模型回复、token 用量。第一段最有价值——它让你看到请求长什么样，而不是只看到答案。

## 本节新增能力

- 组织 `system` 和 `user` 消息
- 发起一次完整的 Chat Completions 风格请求
- 读取 `choices[0].message.content`
- 查看一次请求的 token 使用情况

## 学习重点

- `build_messages()`：消息是怎么组织的
- `call_llm()`：一次 API 请求的最小必要参数有哪些
- `main()`：如何从环境变量中读取 API Key

这一节的核心不是 Agent，而是先把“模型调用”这块地基打稳。

## 建议练习

- 改写 `system prompt`，感受它对回答风格的影响
- 改写 `user prompt`
- 把 `temperature` 分别设成 `0` 和 `1.5` 各跑一次，对比结果的稳定性
- 故意把 `.env` 里的 Key 改错一位，看 401 是怎么在 `raise_for_status()` 处抛出来的
- 把 `raise_for_status()` 那行注释掉再错跑一次，观察错误被推迟到哪一步才暴露
- 打印完整返回 JSON（`print(json.dumps(result, ensure_ascii=False, indent=2))`），理解响应结构，顺便留意 `tool_calls` 字段现在还是空的

## 和后续章节的关系

这一节还没有记忆、工具和循环。后面所有 demo，都会建立在这里这套“消息输入 -> 模型调用 -> 读取响应”的最小闭环上。

还有一点值得提前知道：**模型本身没有状态**。HTTP 请求发出去、返回、结束，它不记得你上一句说过什么。所谓"多轮对话"完全是客户端**每次把完整历史重新发一遍**——这正是 `demo2` 要解决的问题。

[返回首页](../README.md) | [下一节：demo2](../demo2/README.md)
