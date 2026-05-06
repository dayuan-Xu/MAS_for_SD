---
name: software-function-verification
description: Use this skill for software function verification.
license: MIT
compatibility: None
metadata:
  author: boss
  version: "6.0"
---

## 工具优先级排序（从高到低）

### 🔴 核心工具（测试执行必需）

| 优先级 | 工具 | 用途 | 使用建议 |
|--------|------|------|----------|
| 1 | `page_use_extract` | 提取页面文本内容，验证功能是否正常 | **首选验证工具**，直接返回可读文本 |
| 2 | `page_use_observe` | 定位可交互元素（按钮、输入框等） | 执行操作前先定位元素 |
| 3 | `page_use_act` | 执行点击、输入等交互操作 | 配合observe定位的元素使用 |
| 4 | `browser_console_messages` | 捕获JS错误/日志，验证代码正确性 | 验证无控制台错误时使用 |

### 🟡 辅助工具

| 优先级 | 工具                    | 用途 | 使用建议 |
|--------|-----------------------|------|----------|
| 5 | `page_use_navigate`   | 打开被测页面 | 初始加载页面时使用 |
| 6 | `execute`             | 启动本地服务器 | Web文件需HTTP访问时使用 |


### 🟢 低频/慎用工具

| 工具                       | 原因                                                    |
|--------------------------|-------------------------------------------------------|
| `page_use_screenshot`    | 返回base64，无法直接解读，效率低。建议转向`browser_snapshot` 将快照保存到md文件 |
| `page_use_close_session` | 仅测试结束时使用                                              | |

### ⚫ 本次测试禁用工具

| 工具 | 原因 |
|------|------|
| `create_sandbox` | 本次测试禁止新建sandbox |
| `task` | 非并行测试场景 |

---

## 核心原则

1. **验证结果用 extract**：需要判断功能是否正常时，用 `page_use_extract` 获取文本内容
2. **操作前先 observe**：执行点击等操作前，用 `page_use_observe` 定位元素
3. **避免无意义的截图**：截图返回base64文本无法解读，不作为主要验证手段
4. **验证JS正确性**：使用 `browser_console_messages` 检查控制台错误

---

## 典型测试流程

```
1. page_use_navigate          # 打开被测页面
2. page_use_observe           # 定位需要交互的元素
3. page_use_act               # 执行操作（点击、输入等）
4. page_use_extract           # 验证操作结果/提取验证信息
5. browser_console_messages    # 检查是否有JS错误（可选）
```

---

## 工具选择决策树

```
需要验证功能？
├─ 是 → page_use_extract（提取文本内容）
│
├─ 需要操作元素？
│   ├─ 是 → page_use_observe（定位元素）→ page_use_act（执行操作）
│   │
│   └─ 需要截图取证？
│       └─ 是 → page_use_screenshot（截图保存）
│
└─ 检查代码错误？
    └─ 是 → browser_console_messages
```

---

## 注意事项

- `page_use_screenshot` 返回的是base64编码的图片数据，无法解读其内容
- 如果需要验证文本内容，优先使用 `page_use_extract`
- 如果需要定位元素，优先使用 `page_use_observe`