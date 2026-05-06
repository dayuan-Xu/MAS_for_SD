# MCP 工具列表文档 
## 整体说明
所有工具均依赖 `sandbox_id`（由 `create_sandbox` 创建获取），按服务模块分类，包含工具名称、功能描述、入参说明。

## 目录
1. [沙箱基础服务](#1-沙箱基础服务-mcp-server)
2. [Playwright 浏览器操作](#2-playwright-浏览器操作-playwright)
3. [应用进程管理](#3-应用进程管理-wuying_app)
4. [浏览器智能代理](#4-浏览器智能代理-wuying_browser_agent)
5. [CDP 浏览器控制](#5-cdp-浏览器控制-wuying_cdp_mcp_server)
6. [代码运行服务](#6-代码运行服务-wuying_codespace)
7. [文件系统操作](#7-文件系统操作-wuying_filesystem)
8. [Shell 命令执行](#8-shell-命令执行-wuying_shell)
9. [系统监控](#9-系统监控-wuying_system)
10. [桌面UI键鼠窗口控制](#10-桌面ui键鼠窗口控制-wuying_ui)
11. [截图捕获](#11-截图捕获-wuying_capture)

---

## 1. 沙箱基础服务（mcp-server）
### create_sandbox------完全不需要，一次任务的沙盒由程序自主创建，会自动告知每个智能体。
- 描述：创建新 Agentbay 沙箱，返回沙箱 ID
- 入参：无

### get_sandbox_url-----完全不需要，程序自主创建沙盒时可以自动获知资源URL
- 描述：获取无影 MCP 运行时访问 URL，单次使用后过期
- 入参：
  - `sandbox_id`：沙箱唯一标识，来自 create_sandbox

### system_screenshot-----完全不需要
- 描述：全屏截图并返回可分享链接，链接64分钟后过期
- 入参：
  - `sandbox_id`：沙箱ID

### kill_sandbox-----完全不需要，程序自主释放沙盒
- 描述：任务结束后释放沙箱资源
- 入参：
  - `sandbox_id`：沙箱ID

---

## 2. Playwright 浏览器操作（playwright）
### browser_run_code
- 描述：运行 Playwright JS 代码片段
- 入参：`sandbox_id`、`code`（Playwright 异步页面函数）

### browser_evaluate
- 描述：在页面/元素上执行 JS 表达式
- 入参：`sandbox_id`、`function`、`ref`、`element`

### browser_tabs
- 描述：浏览器标签页管理（列表/新建/关闭/切换）
- 入参：`sandbox_id`、`action`、`index`

### browser_fill_form
- 描述：批量填充表单字段（文本框/复选框/单选框/下拉框等）
- 入参：`sandbox_id`、`fields`（表单字段数组）

### browser_take_screenshot
- 描述：页面/元素截图，支持全屏、指定格式、元素截取
- 入参：`sandbox_id`、`ref`、`element`、`filename`、`fullPage`、`type`

### browser_wait_for
- 描述：等待文本出现/消失或固定延时等待
- 入参：`sandbox_id`、`text`、`textGone`、`time`

### browser_select_option
- 描述：下拉框选项选择
- 入参：`sandbox_id`、`element`、`ref`、`values`

### browser_type
- 描述：向可编辑元素输入文本，支持逐字输入、回车提交
- 入参：`sandbox_id`、`element`、`ref`、`text`、`submit`、`slowly`

### browser_hover
- 描述：鼠标悬浮页面元素
- 入参：`sandbox_id`、`element`、`ref`

### browser_drag
- 描述：元素拖拽（起点→终点）
- 入参：`sandbox_id`、`startElement`、`startRef`、`endElement`、`endRef`

### browser_click
- 描述：页面元素点击，支持左右中键、双击、组合键
- 入参：`sandbox_id`、`element`、`ref`、`button`、`doubleClick`、`modifiers`

### browser_snapshot
- 描述：捕获页面无障碍快照，比普通截图更适合页面结构解析
- 入参：`sandbox_id`、`filename`

### browser_network_requests
- 描述：获取页面加载后的所有网络请求
- 入参：`sandbox_id`、`includeStatic`（是否包含静态资源）

### browser_navigate_back
- 描述：浏览器后退上一页
- 入参：`sandbox_id`

### browser_navigate
- 描述：跳转到指定 URL
- 入参：`sandbox_id`、`url`

### browser_press_key
- 描述：键盘按键按下
- 入参：`sandbox_id`、`key`

### browser_install
- 描述：安装配置中指定的浏览器依赖
- 入参：`sandbox_id`

### browser_file_upload
- 描述：上传单个/多个文件
- 入参：`sandbox_id`、`paths`（文件路径数组）

### browser_handle_dialog
- 描述：处理页面弹窗（确认/取消/输入弹窗文本）
- 入参：`sandbox_id`、`accept`、`promptText`

### browser_console_messages
- 描述：获取浏览器控制台日志，支持按日志级别过滤
- 入参：`sandbox_id`、`level`

### browser_resize
- 描述：修改浏览器窗口分辨率
- 入参：`sandbox_id`、`width`、`height`

### browser_close
- 描述：关闭当前页面
- 入参：`sandbox_id`

---

## 3. 应用进程管理（wuying_app）
### start_app
- 描述：通过启动命令拉起应用，支持指定工作目录
- 入参：`sandbox_id`、`start_cmd`、`work_directory`、`activity`

### stop_app_by_cmd
- 描述：通过停止命令终止应用
- 入参：`sandbox_id`、`stop_cmd`

### stop_app_by_pid
- 描述：通过进程PID强制终止进程
- 入参：`sandbox_id`、`pid`

### stop_app_by_pname
- 描述：通过进程名终止所有同名进程
- 入参：`sandbox_id`、`pname`

### get_installed_apps
- 描述：获取系统已安装应用列表，支持过滤开始菜单/桌面程序、排除系统应用
- 入参：`sandbox_id`、`desktop`、`start_menu`、`ignore_system_app`

### list_visible_apps
- 描述：列出所有带可见窗口的应用及进程信息
- 入参：`sandbox_id`

---

## 4. 浏览器智能代理（wuying_browser_agent）
### page_use_navigate
- 描述：浏览器跳转URL，支持新标签页打开
- 入参：`sandbox_id`、`url`、`new_tab`

### page_use_observe
- 描述：查找页面可交互UI元素并给出操作建议
- 入参：`sandbox_id`、`instruction`、`selector`、`use_vision` 等

### page_use_observe_async
- 描述：异步查找可交互元素，返回 task_id 用于轮询结果
- 入参：同 page_use_observe

### page_use_get_observe_result
- 描述：获取异步元素查找任务结果
- 入参：`sandbox_id`、`task_id`

### page_use_extract
- 描述：从页面提取结构化/非结构化数据
- 入参：`sandbox_id`、`instruction`、`field_schema`、`selector` 等

### page_use_extract_async
- 描述：异步页面数据提取，返回 task_id
- 入参：同 page_use_extract

### page_use_get_extract_result
- 描述：获取异步数据提取任务结果
- 入参：`sandbox_id`、`task_id`

### page_use_act
- 描述：执行页面交互动作，阻塞直至完成
- 入参：`sandbox_id`、`action`、`variables`、`use_vision` 等

### page_use_act_async
- 描述：异步执行页面动作，返回 task_id
- 入参：同 page_use_act

### page_use_get_act_result
- 描述：获取异步页面动作执行结果
- 入参：`sandbox_id`、`task_id`

### page_use_login
- 描述：按配置执行网站登录操作
- 入参：`sandbox_id`、`login_config`、`timeout` 等

### page_use_screenshot
- 描述：智能页面截图，支持裁剪、全屏、画质设置
- 入参：`sandbox_id`、`full_page`、`clip`、`quality` 等

### page_use_close_session
- 描述：关闭浏览器代理会话，销毁浏览器进程

### browser_use_create_planner_task
- 描述：创建任务规划，拆解复杂任务为步骤
- 入参：`sandbox_id`、`task`

### browser_use_execute_task
- 描述：自然语言执行复杂浏览器任务
- 入参：`sandbox_id`、`task`、`use_vision` 等

### browser_use_get_task_status
- 描述：查询任务执行状态
- 入参：`sandbox_id`、`task_id`

### browser_use_terminate_task
- 描述：终止正在运行的任务
- 入参：`sandbox_id`、`task_id`

---

## 5. CDP 浏览器控制（wuying_cdp_mcp_server）
### startChromeByCdp
- 描述：启动Chrome并创建CDP调试WebSocket端口，支持指纹、代理、插件等配置
- 入参：`sandbox_id`、浏览器完整配置对象

### stopChrome
- 描述：关闭Chrome浏览器
- 入参：`sandbox_id`

### solve_captcha
- 描述：解决页面验证码（图片/RecaptchaV2/Cloudflare）
- 入参：`sandbox_id`、`pageId`、`captcha_type`、`timeout`

---

## 6. 代码运行服务（wuying_codespace）
### run_code
- 描述：沙箱内运行 Python/JS/R/Java 代码，支持超时限制
- 入参：`sandbox_id`、`code`、`language`、`timeout_s`

---

## 7. 文件系统操作（wuying_filesystem）
- `read_file`：读取文件（支持偏移、二进制/文本格式）
- `read_multiple_files`：批量读取多个文件
- `write_file`：新建/写入文件，支持覆盖/追加、自动创建父目录
- `edit_file`：按文本行匹配编辑文件，返回差异
- `copy_file`：复制文件/目录，支持覆盖控制
- `move_file`：移动/重命名文件/目录
- `delete_file`：删除文件/目录（递归删除）
- `create_directory`：创建多级目录
- `list_directory`：列出目录文件结构
- `get_file_info`：获取文件元数据（大小、时间、权限）
- `search_files`：通配符递归搜索文件
- `get_file_change`：监听目录文件变动事件

所有文件工具必传：`sandbox_id`、文件路径相关参数

---

## 8. Shell 命令执行（wuying_shell）
### shell
- 描述：执行系统Shell命令，支持工作目录、环境变量、超时
- 入参：`sandbox_id`、`command`、`cwd`、`envs`、`timeout_ms`

---

## 9. 系统监控（wuying_system）
### get_metrics
- 描述：获取CPU、内存、磁盘、网络系统监控指标
- 入参：`sandbox_id`

---

## 10. 桌面UI键鼠窗口控制（wuying_ui）
### 鼠标控制
- `move_mouse`：移动鼠标到指定坐标
- `click_mouse`：指定坐标点击（左/右/中/双击）
- `drag_mouse`：鼠标拖拽
- `scroll`：鼠标滚轮滚动

### 键盘控制
- `press_keys`：按下组合键
- `release_keys`：释放按键
- `input_text`：输入文本

### 窗口管理
- `list_root_windows`：列出所有顶层窗口信息
- `get_active_window`：获取当前激活窗口
- `activate_window`：激活指定窗口
- `close_window`：关闭窗口
- `minimize_window`：最小化窗口
- `maximize_window`：最大化窗口
- `restore_window`：还原窗口
- `resize_window`：修改窗口尺寸
- `fullscreen_window`：窗口全屏

### 系统UI信息
- `get_cursor_position`：获取鼠标坐标
- `get_screen_size`：获取屏幕分辨率与缩放
- `focus_mode`：开启/关闭应用焦点独占模式

所有UI工具必传：`sandbox_id`

---

## 11. 截图捕获（wuying_capture）
### screenshot
- 描述：捕获整个桌面并返回Base64图片
- 入参：`sandbox_id`、`format`（png/jpeg）
