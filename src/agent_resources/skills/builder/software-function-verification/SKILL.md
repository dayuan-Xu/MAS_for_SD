---
name: software-function-verification
description: Use this skill when you are doing software function verification（especially for UI interaction operations correctness verification）.
license: MIT
compatibility: None
metadata:
  author: boss
  version: "6.0"
---

## 对于Web应用 UI 验证，你拥有完整的浏览器自动化能力：

### 1. 页面级操作工具（推荐优先使用）

| 工具 | 功能 | 适用场景 |
|------|------|----------|
| `sandbox_page_use_navigate` | 导航到URL | 打开应用页面 |
| `sandbox_page_use_observe` | 观察页面元素 | 查找可交互的输入框、按钮 |
| `sandbox_page_use_extract` | 提取页面内容 | 验证结果、检查提示信息 |
| `sandbox_page_use_act` | 执行交互操作 | 点击、输入等复合操作 |

### 2. 底层浏览器工具（辅助使用）

| 工具 | 功能 | 适用场景 |
|------|------|----------|
| `sandbox_browser_click` | 点击元素 | 直接点击指定元素 |
| `sandbox_browser_type` | 输入文本 | 向输入框填入文字 |
| `sandbox_browser_wait_for` | 等待时间 | 等待页面刷新/加载 |
| `sandbox_browser_evaluate` | 执行JS代码 | 处理复杂交互、动态值设置 |
| `sandbox_browser_press_key` | 按键操作 | 刷新页面(F5)等 |

### 3. 典型工作流
```
启动浏览器 → 导航到Web应用 → 找到元素 → 执行操作 → 验证页面状态变化
```

### 4. 工具使用经验
1. 优先使用页面级工具。
   - `sandbox_page_use_*` 系列工具更智能，能自动处理元素定位
   - 只有当页面级工具不满足需求时，才使用底层工具

2. 等待页面加载很重要。
    ```python
    # 导航后等待页面完全加载
    sandbox_browser_wait_for(time=3)  # 等待3秒
    ```

3. JavaScript注入解决复杂问题。
    比如当某表单值无法通过常规方式设置时：
    ```javascript
    // 直接操作DOM设置值并触发事件
    input.value = '张三';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    ```

## 对于桌面GUI应用 UI 验证，你具备一定的桌面窗口控制能力：

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