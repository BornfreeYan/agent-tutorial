[返回首页](../README.md) | [上一节：demo1](../demo1/README.md) | [下一节：demo3](../demo3/README.md)

# demo2：Memory Demo

这一节开始进入“像 Agent 一点”的形态：程序不再只做一次调用，而是进入交互循环，并保留对话历史。

和 `demo1` 一样，`memory_demo.py` 刻意写得很干净、几乎没有注释——讲解全部放在这份 README 里。

## 本节目标

- 理解多轮对话为什么本质上是维护 `messages`
- 学会把历史轮次不断放回上下文
- 理解短期记忆和消息裁剪的意义

## 入口文件

- [memory_demo.py](memory_demo.py)

## 运行方式

和 `demo1` 共用同一个环境变量，仓库根目录的 `.env` 里填好 `DEEPSEEK_API_KEY` 即可（做法见[首页的环境准备](../README.md)）。临时用 PowerShell 设置也一样有效。

然后在本项目根目录下，运行：

```bash
python demo2/memory_demo.py
```

启动后会进入交互循环，输入 `exit` 或 `quit` 结束。

## 代码走读

### 一、这一节最核心的一句话

**`messages` 这个列表，既是"记忆"，也是"下一次请求要发送的内容"——它们是同一个东西。**

`demo1` 里你已经知道模型没有状态：请求发出去、返回、结束，它不记得任何事。那么"多轮对话"是怎么实现的？答案是——**客户端自己把历史攒起来，每轮都完整重发一遍**。所谓 memory，在这一节里就是"保留上下文"这个动作本身，没有别的机制。

想清楚这一点，后面所有"记忆"相关的东西（更长的历史、摘要压缩、向量检索的外部记忆）都只是在这个基础上做取舍。

### 二、`create_system_message()`

```python
{"role": "system", "content": "你是一个面向初学者的 Python 和 agent 助手。..."}
```

它返回的是一条普通的 system 消息，单独抽成函数是因为它在整个会话里**只创建一次、永远留在列表的第 0 位**。后面裁剪历史时，`trim_messages()` 会把 system 之外的消息裁掉，但这条永远保留——所以人设不会因为对话变长而丢失。

它的内容里有一句"如果用户的问题依赖上文，请结合对话历史继续回答"。这类引导不是必须的，但在做实验时有用：它让模型更愿意利用你发过去的历史。

### 三、`call_llm()`：和 `demo1` 的两处差别

请求部分和 `demo1` 完全一样（同样的 headers、同样的 body 参数、同样先 `raise_for_status()` 再解析），只有两处不同：

1. **`messages` 是完整历史**。`demo1` 是固定的两条消息；这里传进去的是"system + 最近若干轮 user/assistant"，所以模型能看到之前聊过什么。
2. **返回值类型从 `dict` 变成了 `str`**。`demo1` 把整个响应字典返回出去，是为了让你在 `main()` 里观察 `usage`；这一节只关心回复正文，所以直接在函数里取到 `choices[0].message.content` 再返回。

注意 `max_tokens` 从 200 调到了 300。这类数值没有标准答案，够用就行。

### 四、`trim_messages()`：为什么要裁剪，怎么裁

```python
def trim_messages(messages, max_turns):
    system_message = messages[0]
    recent_messages = messages[1:]
    max_message_count = max_turns * 2
    if len(recent_messages) > max_message_count:
        recent_messages = recent_messages[-max_message_count:]
    return [system_message, *recent_messages]
```

**为什么要裁**：历史越长，发出去的 token 越多——成本和响应时间都会跟着涨，而且最终会撞上模型的上下文上限。裁剪是"短期记忆"最朴素的一种实现：只记最近几轮，更早的就忘掉。

**裁的策略**：永久保留第 0 条的 system，其余只留最近的 `max_turns * 2` 条。这里乘 2 是因为**一轮对话是两条消息**——一条 user，一条 assistant。所以 `MAX_TURNS = 4` 实际保留约 8 条非 system 消息。

**三个 Python 用法**：

| 写法                                | 含义                                                                                             |
| ----------------------------------- | ------------------------------------------------------------------------------------------------ |
| `messages[1:]`                    | 切片，取第 1 条到最后一条（跳过 system）                                                          |
| `recent_messages[-max_message_count:]` | 负索引切片：取**最后** N 条。这是"保留最近 N 条"最常见的写法                              |
| `[system_message, *recent_messages]` | `*` 把列表拆开再拼进新列表，等价于 `[system_message] + recent_messages`，但更直观地表达"这条 + 其余" |

`if len(...) > max_message_count` 这个判断只是跳过切片那一步，让意图更明确；即使去掉它，`[-N:]` 在 N 大于列表长度时也会原样返回全部元素。

但有一点要注意：**这个函数总是返回一个新列表，永远不会在原地修改。** 所以 `main()` 里必须写成 `messages = trim_messages(messages, MAX_TURNS)` 把返回值接住——如果只写 `trim_messages(messages, MAX_TURNS)` 而不赋值，`messages` 一个元素都不会变，裁剪就等于白做了。

### 五、`main()` 的循环：消息是怎么进出的

```python
messages = [create_system_message()]
while True:
    user_input = input("\n你：").strip()
    ...
    messages.append({"role": "user", "content": user_input})
    messages = trim_messages(messages, MAX_TURNS)
    answer = call_llm(api_key=api_key, messages=messages)
    print(f"\n助手：{answer}")
    messages.append({"role": "assistant", "content": answer})
    messages = trim_messages(messages, MAX_TURNS)
```

一轮完整交互有六个动作，顺序很重要：

1. **追加 user**：先把用户这句话写进记忆
2. **裁剪**：发送前裁一次，避免这次请求超长
3. **调用**：把整个列表发出去
4. **回写 assistant**：把模型回复也追加进记忆
5. **再裁剪**：回写后再裁一次，保持列表长度稳定
6. **下一轮**：回到第 1 步

**为什么第 4 步不能省**：如果不把 assistant 回复写回去，下一轮你问"展开讲讲"或"换个例子"，模型完全不知道你在指哪一句——它收到的只有 system 加你这一句问话，历史是断的。**记忆是双向的：用户说了什么要记住，模型自己说了什么也要记住。**

**为什么要裁两次**：一次在发送前（保证这次请求不超长），一次在回写后（保证列表不会无限增长）。两处看起来重复，但保护的是不同时刻的状态。

**失败回滚**：

```python
except requests.RequestException as exc:
    print(f"\n请求失败：{exc}")
    if messages[-1]["role"] == "user":
        messages.pop()
    continue
```

第 1 步已经把 user 消息写进记忆了，但这次请求失败了，模型从没"见过"它。如果不回滚，这条消息就会永久留在历史里——下一轮你重新问一遍，历史中就有了两条几乎一样的 user 消息，模型会看到一个自己从未回应过的提问。所以这里把它 `pop()` 掉。

`requests.RequestException` 是所有 requests 异常的基类（`HTTPError`、`ConnectionError`、`Timeout` 等都是它的子类），捕获它就等于"这次请求的任何失败都接住"，程序不会崩，而是回到循环让你重试。

### 六、其他几个小地方

- `input("\n你：")`：从终端读一行输入。`\n` 只是为了输出好看。
- `.strip()`：去掉首尾空白，避免你手滑敲了空格就被当成有效提问。
- `if not user_input: continue`：空输入直接重来。
- `user_input.lower() in {"exit", "quit"}`：写在一行里判断两种退出词。`lower()` 是为了让 `EXIT`、`Quit` 也能识别。

## 本节新增能力

- 维护 `messages` 列表
- 把上一轮的 `assistant` 回复也放回上下文
- 通过裁剪消息列表模拟“短期记忆”
- 观察会话变长后 token 成本和延迟的变化

## 学习重点

- `create_system_message()`：持续约束助手身份
- `trim_messages()`：如何只保留最近几轮消息
- `main()` 中的 while 循环：消息是如何追加和回写的

建议重点理解这几个事实：

- 多轮对话不神秘，本质上就是反复把历史消息一起发给模型
- 所谓 memory，在早期 demo 里主要就是“保留上下文”
- 不做裁剪，消息会越来越长，成本和延迟都会上升

## 建议练习

- 把保留轮数调大调小，观察行为变化
- 给 system message 增加更强的人设约束
- 让程序打印每轮发送给模型的消息数量
- 故意把第 4 步（回写 assistant）删掉，感受模型"失忆"后的回答差异
- 把 `MAX_TURNS` 设为 `0`，看程序会发生什么，再对比 `trim_messages()` 里的判断和 `except` 里的保护各起了什么作用

## 与上一节相比多了什么

`demo1` 只演示一次调用，`demo2` 开始引入“持续会话”这个 Agent 最常见的外壳。看懂这一节，你就已经理解了很多聊天型 Agent 的最小实现方式。

[返回首页](../README.md) | [上一节：demo1](../demo1/README.md) | [下一节：demo3](../demo3/README.md)
