---
name: software-function-verification
description: Use this skill for software function verification（especially for UI interaction operations correctness verification）.
license: MIT
compatibility: None
metadata:
  author: boss
  version: "6.0"
---

对于Web应用 UI 验证，你拥有完整的浏览器自动化能力：

| 功能 | 对应工具 |
|------|----------|
| 打开网页/导航 | `page_use_navigate` |
| 查看页面元素 | `page_use_observe` |
| 执行交互（点击、输入） | `page_use_act` |
| 验证结果 | `page_use_extract`  |

**典型工作流：**
```
启动浏览器 → 导航到Web应用 → 找到元素 → 执行操作 → 验证页面状态变化
```

对于桌面GUI应用 UI 验证，你具备一定的桌面窗口控制能力：

| 功能 | 对应工具                                                                           |
|------|--------------------------------------------------------------------------------|
| 列出所有窗口 | `list_root_windows`                                                            |
| 获取活跃窗口信息 | `get_active_window`                                                            |
| 窗口操作（最大化/最小化/关闭） | `maximize_window`, `minimize_window`, `close_window`                           |
| 鼠标操作 | `click_mouse`, `move_mouse`, `drag_mouse` |
| 键盘操作 | `press_keys`, `input_text`                                                     |

**典型工作流：**
```
启动应用 → 获取窗口列表 → 聚焦目标窗口 → 模拟鼠标键盘操作 → 观察软件运行日志和键鼠工具调用返回结果
```

---