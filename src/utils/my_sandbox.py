import logging
import os
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

from agentbay import AgentBay, CreateSessionParams, SessionResult, ContextSync, ContextService
from deepagents.backends.protocol import ExecuteResponse, FileDownloadResponse, FileUploadResponse
from deepagents.backends.sandbox import BaseSandbox

from src.config.settings import settings

logger = logging.getLogger(__name__)

# ========== 常量定义 ==========

CONTEXT_MOUNT_PATH_PREFIX_OF_NEW_TASK = "/tmp/persistent/agent_workspace/warehouse"  # 开发新任务时，将新任务工作空间挂载到该目录下

# 文件扩展名分类
TEXT_FILE_EXTENSIONS = {
    '.txt', '.md', '.py', '.js', '.ts', '.html', '.css', '.json', '.yaml', '.yml',
    '.xml', '.csv', '.log', '.ini', '.cfg', '.conf', '.sh', '.bat'
}

# 需要排除的目录名称
EXCLUDED_DIRS = {
    '__pycache__',
    '.pytest_cache',
    'node_modules',
    'dist',
    'build',
    '.git',
    '.venv',
    'venv',
    'env',
    '.idea',
    '.vscode',
    '*.egg-info',
}

# 需要排除的文件扩展名
EXCLUDED_FILE_EXTENSIONS = {
    '.pyc',
    '.pyo',
    '.pyd',
    '.so',
    '.dll',
    '.exe',
    '.log',
    '.tmp',
    '.temp',
    '.swp',
    '.swo',
    '.DS_Store',
    '.coverage',
}

# 保留的隐藏文件
PRESERVED_HIDDEN_FILES = {'.env', '.gitignore', '.dockerignore'}


def _to_snake_case(name: str) -> str:
    """将任务名称转换为蛇形命名（snake_case）。
    
    转换规则：
    1. 将所有字符转为小写
    2. 将空格、连字符等非字母数字字符替换为下划线
    3. 去除连续的下划线
    4. 去除首尾的下划线
    
    Args:
        name: 原始任务名称，如 "Snake game", "Excel data process"
    
    Returns:
        蛇形命名的字符串，如 "snake_game", "excel_data_process"
    
    Examples:
        >>> _to_snake_case("Snake game")
        'snake_game'
        >>> _to_snake_case("Excel data process")
        'excel_data_process'
        >>> _to_snake_case("CRUD manage")
        'crud_manage'
    """
    import re
    # 转为小写
    name = name.lower()
    # 将空格、连字符等非字母数字字符替换为下划线
    name = re.sub(r'[^a-z0-9]+', '_', name)
    # 去除连续的下划线
    name = re.sub(r'_+', '_', name)
    # 去除首尾的下划线
    name = name.strip('_')
    return name


def _should_skip_path(relative_path: Path) -> bool:
    """判断是否应该跳过该路径（不下载）。

    使用黑名单机制排除中间产物、缓存、临时文件等。

    Args:
        relative_path: 相对于任务根目录的路径

    Returns:
        bool: True 表示应该跳过，False 表示应该下载
    """
    name = relative_path.name

    # 检查是否在排除目录中
    for part in relative_path.parts:
        if part in EXCLUDED_DIRS:
            return True

    # 检查文件扩展名
    if name.endswith(tuple(EXCLUDED_FILE_EXTENSIONS)):
        return True

    # 特殊文件模式：排除隐藏文件（除了常见的配置文件）
    if name.startswith('.') and name not in PRESERVED_HIDDEN_FILES:
        return True

    return False


def _write_content_to_file(local_path: Path, content: bytes) -> None:
    """将字节内容写入本地文件，根据文件类型自动选择文本或二进制模式。
    
    Args:
        local_path: 本地文件路径
        content: 文件内容（字节）
    """
    # 确保父目录存在
    local_path.parent.mkdir(parents=True, exist_ok=True)

    # 根据文件类型选择写入方式
    file_ext = local_path.suffix.lower()

    if file_ext in TEXT_FILE_EXTENSIONS:
        # 文本文件：尝试 UTF-8 解码
        try:
            local_path.write_text(content.decode('utf-8'), encoding='utf-8')
        except UnicodeDecodeError:
            # 如果解码失败，当作二进制文件处理
            local_path.write_bytes(content)
    else:
        # 二进制文件：直接写入 bytes
        local_path.write_bytes(content)


# 该类通过无影agentbay的session实现sandbox backend
class MySandbox(BaseSandbox):
    """基于无影AgentBay实现的云沙盒后端。

        该类通过无影AgentBay的session提供真正的云端沙盒环境，
        所有文件操作和命令执行都在云端进行，而非本地。
        """

    def __init__(self,
                 *,
                 task_name: str = "",
                 reuse_existing: bool = True,
                 api_key: str = settings.WUYING_AGENTBAY_API_KEY,
                 image_id: str = "linux_latest",
                 idle_timeout: int = 60 * 60):
        """初始化MySandbox。

        Args:
            task_name: 当前软件开发任务的名称，用于创建持久化的存储盒，持久化保存智能体的文件写入操作（允许智能体可以访问该沙盒）。因此可以后续下载当前软件的成果物文件到本地
            reuse_existing: 针对当前task_name，是否复用已有的 Context（支持棕地开发）
            api_key: AgentBay API密钥
            image_id: 沙盒镜像ID
            idle_timeout: 云端会话空闲自动释放时间（秒），默认1h（60*60秒），太短的话，很有可能在等待智能体输出大块内容（这需要llm耗费10min左右来输出3.8万个字符）之前，该会话就会被自动释放了！！！
        """
        self.task_name = task_name  # 公开属性，供外部访问
        self._task_name_snake_case = _to_snake_case(task_name) if task_name else ""
        self.reuse_existing = reuse_existing
        self._agent_bay = AgentBay(api_key=api_key)
        self._image_id = image_id
        self._idle_timeout = idle_timeout
        self._session = None
        self._session_id = None  # 用于暂停会话后，重新连接该会话（目前未实现会话暂停）
        self._task_context_box_id = None  # 存储任务上下文盒子的ID

        self._initialize_session()  # 创建会话

        # 添加线程锁保护，防止并发竞态条件导致重复创建会话
        self._session_lock = threading.Lock()  # 线程锁，确保只有一个线程执行初始化

        # 会话检查缓存机制，避免频繁调用 API
        self._last_session_check_time = 0
        self._session_check_interval = 60  # 60秒内不重复检查会话有效性（平衡防护与性能）
        self._session_check_cache_valid = False  # 缓存是否有效

    def _get_task_context_sync(self) -> ContextSync | None:
        """获取或创建当前任务的 Context。将self.task_name作为访问存储盒的标识符。
        
        Returns:
            ContextSync | None: 如果存在 task_name，返回配置好的上下文同步对象；否则返回 None
        """
        if not self.task_name:
            return None

        context_service: ContextService = self._agent_bay.context
        task_context = None
        logger.info(f"🔍 检查任务存储盒: {self.task_name}")
        get_result = context_service.get(self.task_name)

        # 情况 1: 复用现存 context
        if get_result.success and self.reuse_existing and get_result.context is not None:
            task_context = get_result.context
            logger.info(f"📦 复用现有任务存储盒: {self.task_name}")

        # 情况 2: 不重用，创建带时间戳的新 context
        elif get_result.success and not self.reuse_existing:
            new_name = f"{self.task_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            old_name = self.task_name
            self.task_name = new_name
            logger.warning(
                f"❗ 任务存储盒 '{old_name}' 已存在，创建新的: '{new_name}'"
            )
            create_result = context_service.create(new_name)

            if not create_result.success or not create_result.context:
                logger.error(f"❌ 创建存储盒失败: {create_result.error_message}", exc_info=True)
                raise RuntimeError(f"创建存储盒失败: {create_result.error_message}")

            task_context = create_result.context
            logger.info(f"✅ 任务存储盒创建成功: {task_context.id}, 任务名: {self.task_name}")

        # 情况 3: 不存在，创建全新的 context
        elif not get_result.success:
            logger.info(f"📦 为任务创建新存储盒: {self.task_name}")
            create_result = context_service.create(self.task_name)

            if not create_result.success or not create_result.context:
                logger.error(f"❌ 创建存储盒失败: {create_result.error_message}", exc_info=True)
                raise RuntimeError(f"创建存储盒失败: {create_result.error_message}")

            task_context = create_result.context
            logger.info(f"✅ 新任务存储盒创建成功: {task_context.id}, 任务名: {self.task_name}")

        # 确定该 context 的挂载路径
        context_mount_path = f"{CONTEXT_MOUNT_PATH_PREFIX_OF_NEW_TASK}/{self._task_name_snake_case}"
        # ⭐ 保存 context ID，供外部访问
        self._task_context_box_id = task_context.id
        return ContextSync.new(task_context.id, context_mount_path)

    def _get_context_syncs(self) -> list[ContextSync]:
        """获取所有需要挂载的 Context 同步配置。
        
        Returns:
            list[ContextSync]: 包含 agent 资源 context 和（可选的）task context
        """
        my_context_syncs = []

        # 1. 添加任务 context（如果存在 task_name）
        task_sync = self._get_task_context_sync()
        if task_sync is not None:
            my_context_syncs.append(task_sync)

        return my_context_syncs

    def _initialize_session(self):
        """创建AgentBay会话并挂载持久化存储盒"""
        # 获得过激活的会话
        if self._session_id:
            logger.info(f"♻️ 复用现有会话: {self._session_id}")
            self._session = self._agent_bay.get(self._session_id).session
            if self._session is None:
                logger.error(f"❌ 获取会话失败: {self._session_id}", exc_info=True)
                raise RuntimeError(f"获取会话失败: {self._session_id}")
            logger.info(f"✅ 会话复用成功, SessionId={self._session.session_id}")

        logger.info(f"🚀 初始化会话... 任务名={self.task_name}, 镜像ID={self._image_id}")

        # 获取持久化存储盒。
        # 若想同步内部已经有内容的context box，
        # 会在同步它时遇到错误（Wait OSS credential timeout (>10s)），
        # 因此只选择为task创建一个task context box
        my_context_syncs = self._get_context_syncs()

        # 创建会话，该会话具备持久化数据
        logger.info("🔗 创建带存储盒的会话...")
        logger.debug(f"  - 镜像 ID: {self._image_id}")
        logger.debug(f"  - 存储盒同步数量: {len(my_context_syncs)}")
        for i, ctx_sync in enumerate(my_context_syncs):
            logger.debug(f"    [{i}] 存储盒 ID: {ctx_sync.context_id}")
        logger.debug(f"  - 空闲超时: {self._idle_timeout}s")

        params = CreateSessionParams(
            image_id=self._image_id,
            context_syncs=my_context_syncs,
            idle_release_timeout=self._idle_timeout  # 关键：设置云端空闲超时
        )

        logger.info("📡 调用 agent_bay.create() API...")
        result: SessionResult = self._agent_bay.create(params)
        logger.info(f"📡 agent_bay.create() 返回: 成功标志={result.success}")

        if not result.success or result.session is None:
            error_msg = getattr(result, 'error_message', '未知错误')
            logger.error(f"❌ 创建会话失败: {error_msg}", exc_info=True)
            logger.error(f"   结果对象: {result}")
            raise RuntimeError(f"创建 AgentBay 会话失败: {error_msg}")

        self._session = result.session
        self._session_id = self._session.session_id
        # 打印创建成功的会话信息
        logger.info(
            f"✅ 会话创建成功, SessionId={self._session.session_id}, 空闲超时={self._idle_timeout}s")

    def check_session(self, max_retries: int = 3, backoff_factor: float = 1.0):
        """ 检查会话有效性，如未创建则初始化（失效则抛致命错误）
        
        ⭐ 关键修复：使用双重检查锁定模式（Double-Checked Locking）防止并发竞态条件
        ⭐ 新增优化：
          1. 添加指数退避重试机制处理 LOCK_FAILED 错误
          2. 添加会话检查缓存，5秒内不重复调用 API
        
        Args:
            max_retries: 最大重试次数，默认3次
            backoff_factor: 退避因子，用于计算等待时间，默认1.0秒
        
        工作原理：
        1. 第一次检查（不加锁）：如果会话已存在，直接验证并返回（高性能路径）
        2. 第二次检查（加锁后）：防止在等待锁的过程中，其他线程已完成初始化
        3. 锁的互斥性保证：同一时刻只有一个线程能执行初始化代码
        
        Raises:
            RuntimeError: 会话已失效，程序必须终止
        """
        logger.info(f"🔍 检查会话有效性: {self._session_id}")

        # ===== 优化1：会话检查缓存机制 =====
        current_time = time.time()
        if (self._session is not None and
                self._session_check_cache_valid and
                current_time - self._last_session_check_time < self._session_check_interval):
            logger.debug(f"⚡ 使用缓存的会话状态（距离上次检查 {current_time - self._last_session_check_time:.1f}秒）")
            return

        # ===== 快速路径：如果会话已存在，直接验证有效性（避免不必要的锁竞争）=====
        if self._session is not None:
            # ⭐ 新增：带重试机制的会话检查
            for attempt in range(max_retries):
                try:
                    info_result = self._session.info()

                    if info_result.success:
                        # 会话正常，更新缓存
                        self._last_session_check_time = time.time()
                        self._session_check_cache_valid = True
                        logger.info(f"✅ 会话 {self._session_id}  仍然有效，因为session.info()返回成功信息！")
                        return

                    # 会话已被云端自动释放，这是致命错误！
                    logger.error(
                        f"\n    ❌ [致命错误] 会话 {self._session_id} 已被云端自动释放！\n"
                        f"   原因: {info_result.error_message}\n"
                        f"   此错误不可恢复 - 开发流程必须终止。"
                        , exc_info=True
                    )
                    raise RuntimeError(
                        f"[致命错误] 任务 '{self.task_name}' 的会话已被 AgentBay 云端自动释放。\n"
                        f"这通常发生在会话超过空闲超时时间 ({self._idle_timeout}s) 时。\n"
                        f"开发流程无法继续。请使用新会话重新启动。"
                    )

                except Exception as e:
                    error_msg = str(e)
                    # 检查是否是 LOCK_FAILED 错误
                    if "LOCK_FAILED" in error_msg and attempt < max_retries - 1:
                        wait_time = backoff_factor * (2 ** attempt)
                        logger.warning(
                            f"⚠️  会话锁冲突 (尝试 {attempt + 1}/{max_retries})，{wait_time:.1f}秒后重试...\n"
                            f"   错误: {error_msg}"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        # 非 LOCK_FAILED 错误或已达到最大重试次数，重新抛出异常
                        logger.error(f"❌ 会话检查失败: {error_msg}", exc_info=True)
                        raise

        # ===== 慢速路径：需要初始化，使用锁保护 =====
        with self._session_lock:
            # 双重检查：获取锁后再次确认是否需要初始化
            # （可能在你等待锁的过程中，其他线程已经完成了初始化）
            if self._session is not None:
                logger.debug("⏳ 其他线程已在等待锁期间完成初始化，直接复用")
                # 更新缓存时间
                self._last_session_check_time = time.time()
                self._session_check_cache_valid = True
                return

            # ⭐ 到这里，确定只有当前线程在执行初始化（锁的互斥性保证）
            logger.warning(
                "\n" + "=" * 60 + "\n"
                                  "❗ [MySandbox] 会话未初始化，正在创建新会话...\n" +
                "=" * 60 + "\n"
            )

            try:
                self._initialize_session()
                logger.debug("✅ 会话初始化完成")
                # 初始化成功后，更新缓存
                self._last_session_check_time = time.time()
                self._session_check_cache_valid = True
            except Exception as e:
                logger.error(f"❌ 会话初始化失败: {e}", exc_info=True)
                raise

    def execute(
            self,
            command: str,
            *,
            timeout: int | None = None,
    ) -> ExecuteResponse:
        """Execute a command in the sandbox and return ExecuteResponse.
        
        ⭐ 关键修复：确保云端 Python 脚本使用 UTF-8 编码执行
        ⭐ 懒检查策略：不主动检查会话，让操作本身验证会话有效性
        """
        # ⭐ 移除主动检查：self.check_session()
        # 如果会话未初始化或已失效，下面的 API 调用会自然抛出异常
        try:
            # Convert timeout from seconds (protocol) to milliseconds (AgentBay)
            timeout_ms = int(timeout * 1000) if timeout is not None else None

            # ⭐ 关键修复：为 Python 命令添加 UTF-8 编码环境变量
            # 检测是否是 Python 命令（由 BaseSandbox.read/ls/grep/glob 等方法生成）
            # 使用更宽松的检测：只要命令中包含 'python' 就添加环境变量
            if 'python' in command.lower():
                # 在命令前添加 PYTHONUTF8=1，确保 Python 使用 UTF-8 编码
                command = f"PYTHONUTF8=1 {command}"
                logger.debug(f"🔧 已为 Python 命令添加 UTF-8 编码环境变量")

            # agentbay execute工具默认50秒超时
            result = self._session.command.execute_command(command, timeout_ms=timeout_ms)

            output = getattr(result, 'output', '')
            success = getattr(result, 'success', False)
            exit_code = getattr(result, 'exit_code', 0 if success else 1)

            return ExecuteResponse(
                output=output,
                exit_code=exit_code,
                truncated=False
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ AgentBay 沙盒命令执行失败: {error_msg}", exc_info=True)
            return ExecuteResponse(
                output=f"Error executing command: {error_msg}",
                exit_code=1,
                truncated=False
            )

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """Upload multiple files to the sandbox.
        
        ⭐ 优化：使用 AgentBay 原生的 upload_file() API，而不是 write_file()
        通过临时文件桥接 bytes → 本地文件 → 云端
        ⭐ 懒检查策略：不主动检查会话，让操作本身验证会话有效性
        """
        # ⭐ 移除主动检查：self.check_session()
        responses = []
        for file_path, content in files:
            temp_file_path = None
            try:
                logger.debug(f"📤 正在上传文件: {file_path} ({len(content)} 字节)")

                # 确保父目录存在
                parent_dir = str(Path(file_path).parent)
                if parent_dir and parent_dir != '.':
                    self._session.file_system.create_directory(parent_dir)

                # ⭐ 关键优化：创建临时文件，使用 AgentBay 原生 upload_file API
                with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.tmp') as temp_file:
                    temp_file.write(content)
                    temp_file_path = temp_file.name

                # 使用 AgentBay 原生 upload_file API（支持二进制文件）
                upload_result = self._session.file_system.upload_file(
                    local_path=temp_file_path,
                    remote_path=file_path
                )

                if upload_result.success:
                    logger.debug(f"✅ 上传成功: {file_path}")
                    responses.append(FileUploadResponse(path=file_path))
                else:
                    error_msg = getattr(upload_result, 'error', '未知错误')
                    logger.error(f"❌ 上传失败: {file_path}, 错误: {error_msg}", exc_info=True)
                    responses.append(FileUploadResponse(
                        path=file_path,
                        error=f"上传失败: {error_msg}"
                    ))

            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ AgentBay 沙盒上传异常: {file_path}, 错误: {error_msg}", exc_info=True)
                responses.append(FileUploadResponse(
                    path=file_path,
                    error=error_msg
                ))
            finally:
                # 清理临时文件
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to clean up temp file: {temp_file_path}, Error: {e}")

        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """Download multiple files from the sandbox.
        
        ⭐ 优化：使用 AgentBay 原生的 download_file() API，而不是 read_file()
        通过临时文件桥接 云端 → 本地文件 → bytes
        ⭐ 懒检查策略：不主动检查会话，让操作本身验证会话有效性
        """
        # ⭐ 移除主动检查：self.check_session()
        responses = []
        for file_path in paths:
            temp_file_path = None
            try:
                logger.debug(f"📥 正在下载文件: {file_path}")

                # ⭐ 关键优化：创建临时文件，使用 AgentBay 原生 download_file API
                with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.tmp') as temp_file:
                    temp_file_path = temp_file.name

                # 使用 AgentBay 原生 download_file API（支持二进制文件）
                download_result = self._session.file_system.download_file(
                    remote_path=file_path,
                    local_path=temp_file_path
                )

                if download_result.success:
                    # 读取临时文件为 bytes
                    with open(temp_file_path, 'rb') as f:
                        content = f.read()

                    logger.debug(f"✅ 下载成功: {file_path} ({len(content)} 字节)")
                    responses.append(FileDownloadResponse(
                        path=file_path,
                        content=content
                    ))
                else:
                    error_msg = getattr(download_result, 'error', '未知错误')
                    logger.error(f"❌ 下载失败: {file_path}, 错误: {error_msg}", exc_info=True)
                    responses.append(FileDownloadResponse(
                        path=file_path,
                        error=f"下载失败: {error_msg}"
                    ))

            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ AgentBay 沙盒下载异常: {file_path}, 错误: {error_msg}", exc_info=True)
                responses.append(FileDownloadResponse(
                    path=file_path,
                    error=error_msg
                ))
            finally:
                # 清理临时文件
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to clean up temp file: {temp_file_path}, Error: {e}")

        return responses

    @property
    def task_context_box_id(self) -> str | None:
        """获取任务存储盒盒子的ID。
        
        Returns:
            str | None: 任务存储盒盒子的ID，如果未设置则返回None
        """
        return self._task_context_box_id

    @property
    def id(self) -> str:
        """Unique identifier for the sandbox backend."""
        if self._session is None:
            raise RuntimeError("Session not initialized")
        return self._session.session_id

    def __enter__(self):
        """支持 with 语句：进入时返回实例"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持 with 语句：退出时自动清理资源"""
        self.delete_session()
        if exc_type:
            logger.info(f"❌ 沙盒运行期间发生错误: {exc_val}")
        return False  # 不吞掉异常

    def delete_session(self):
        """清理资源，删除AgentBay会话"""
        if self._session:
            logger.info(f"🧹 当前会话不为None，开始手动释放会话, SessionId={self._session.session_id}")
            try:
                # 将当前会话中对存储盒内文件的更改同步到OSS上该存储盒对应位置
                self._agent_bay.delete(self._session, sync_context=True)
                logger.info("✅ 会话手动释放成功")
            except Exception as e:
                logger.warning(f"❌ 手动释放会话过程中捕获异常: {e}")
            finally:
                self._session = None

    def download_task_artifacts(self, local_download_dir: Path) -> bool:
        """下载当前任务的所有成果物到本地目录。
        
        Args:
            local_download_dir: 本地下载目标目录
            
        Returns:
            bool: 是否成功下载
        """
        logger.info(
            f"📥 下载任务成果物, 任务名={self.task_name}, 本地目标目录={local_download_dir}")

        if not self.task_name:
            logger.warning("⚠️ 未关联任务名，跳过下载")
            return False

        if not self._session:
            logger.error("❌ 会话不存在，跳过下载", exc_info=True)
            logger.info("会话不存在，无法下载成果物")
            return False

        try:
            # ⭐ 关键修复：构造云端挂载路径，处理空格和大小写问题
            # AgentBay 可能会将任务名中的空格转换为下划线，或进行其他格式化

            # ⭐ 关键修复：使用蛇形命名的任务名构造云端路径
            cloud_path = f"{CONTEXT_MOUNT_PATH_PREFIX_OF_NEW_TASK}/{self._task_name_snake_case}"
            logger.info(f"📂 云端源路径: {cloud_path}")

            # 确保本地目录存在
            local_download_dir.mkdir(parents=True, exist_ok=True)

            # 先尝试原始路径
            downloaded_count = self._download_recursive(cloud_path, local_download_dir)

            logger.info(f"✅ 下载完成: 共 {downloaded_count} 个文件")
            logger.info(f"✅ 成功下载 {downloaded_count} 个文件到: {local_download_dir}")
            return True

        except Exception as e:
            logger.error(f"❌ 下载失败: {e}", exc_info=True)
            return False

    def _download_recursive(self, cloud_dir: str, local_dir: Path) -> int:
        """递归下载云端目录到本地（智能过滤中间产物）。
        
        ⭐ 优化：使用 AgentBay 原生的 download_file() API，而不是 read_file()
        
        Args:
            cloud_dir: 云端目录路径
            local_dir: 本地目标目录
            
        Returns:
            下载的文件数量
        """
        import tempfile
        import os

        downloaded_count = 0
        skipped_count = 0

        try:
            list_result = self._session.file_system.list_directory(cloud_dir)
            if not list_result.success or not list_result.entries:
                return 0

            # ⭐ 调试：打印第一个 entry 的所有属性，了解其结构
            if list_result.entries:
                first_entry = list_result.entries[0]
                logger.debug(f"🔍 DirectoryEntry 对象属性: {dir(first_entry)}")
                logger.debug(f"   - 类型: {type(first_entry)}")
                # 尝试访问常见属性
                for attr in ['path', 'name', 'full_path', 'file_path', 'entry_path']:
                    if hasattr(first_entry, attr):
                        logger.debug(f"   - {attr}: {getattr(first_entry, attr)}")

            for entry in list_result.entries:
                # ⭐ 修复：尝试多种可能的属性名
                cloud_path = None
                for attr_name in ['path', 'full_path', 'file_path', 'entry_path']:
                    if hasattr(entry, attr_name):
                        cloud_path = getattr(entry, attr_name)
                        break

                # 如果找不到完整路径属性，但有 name 属性，则手动拼接完整路径
                if cloud_path is None and hasattr(entry, 'name'):
                    # name 只是文件名，需要与父目录拼接
                    cloud_path = f"{cloud_dir}/{entry.name}"
                    logger.debug(f"   📝 使用 name 属性拼接路径: {cloud_path}")

                if cloud_path is None:
                    logger.error(f"❌ 无法找到 entry 的路径属性，可用属性: {dir(entry)}", exc_info=True)
                    continue

                # ⭐ 关键修复：统一使用 POSIX 路径格式（正斜杠）进行相对路径计算
                # 云端路径始终是 Linux 格式（正斜杠），不能用 Windows 的 Path 对象处理
                base_path = f"{CONTEXT_MOUNT_PATH_PREFIX_OF_NEW_TASK}/{self._task_name_snake_case}"

                # 使用纯字符串操作计算相对路径，避免跨平台路径格式问题
                if cloud_path.startswith(base_path + '/'):
                    relative_path_str = cloud_path[len(base_path) + 1:]
                elif cloud_path == base_path:
                    continue  # 跳过基础路径本身
                else:
                    logger.warning(f"⚠️ 路径不匹配: {cloud_path} 不以 {base_path} 开头")
                    continue

                # 现在才转换为 Path 对象用于本地文件系统操作
                relative_path = Path(relative_path_str)

                # ⭐ 检查是否应该跳过
                if _should_skip_path(relative_path):
                    skipped_count += 1
                    continue

                local_path = local_dir / relative_path

                if entry.is_directory:
                    # 递归下载子目录
                    local_path.mkdir(parents=True, exist_ok=True)
                    downloaded_count += self._download_recursive(cloud_path, local_dir)
                else:
                    # ⭐ 关键优化：使用临时文件 + download_file() API
                    temp_file_path = None
                    try:
                        # 创建临时文件
                        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.tmp') as temp_file:
                            temp_file_path = temp_file.name

                        # 使用原生 download_file API
                        download_result = self._session.file_system.download_file(
                            remote_path=cloud_path,
                            local_path=temp_file_path
                        )

                        if download_result.success:
                            # 读取临时文件并写入目标位置
                            with open(temp_file_path, 'rb') as f:
                                file_content = f.read()

                            # ⭐ 使用统一的文件写入方法
                            _write_content_to_file(local_path, file_content)

                            downloaded_count += 1
                            logger.debug(f"✅ 已下载: {cloud_path} -> {local_path}")
                        else:
                            error_msg = getattr(download_result, 'error', '未知错误')
                            logger.warning(f"⚠️ 下载失败: {cloud_path}, 错误: {error_msg}")

                    except Exception as e:
                        logger.error(f"❌ 下载异常: {cloud_path}, 错误: {e}", exc_info=True)
                    finally:
                        # 清理临时文件
                        if temp_file_path and os.path.exists(temp_file_path):
                            try:
                                os.unlink(temp_file_path)
                            except Exception as e:
                                logger.warning(f"⚠️ 清理临时文件失败: {temp_file_path}, 错误: {e}")

        except Exception as e:
            logger.info(f"⚠️ 递归下载出错: {e}")

        if skipped_count > 0:
            logger.info(f"   ℹ️  已跳过 {skipped_count} 个中间产物/缓存文件")

        return downloaded_count

    def __del__(self):
        """析构函数：作为最后一道防线确保资源被清理"""
        self.delete_session()


if __name__ == "__main__":
    # 并不需要浪费资源在同步和当前软件开发任务无关的存储盒上
    # # 0. 创建agent resources存储盒并上传资源
    # init_remote_agent_resources()

    # # 1. 使用 with 语句测试沙盒，确保资源自动释放
    # logger.info("\n--- 开始沙盒功能测试 ---")
    # with MySandbox() as sandbox:
    #     logger.info(f"🆔 Sandbox ID: {sandbox.id}")
    #
    #     # 3. 测试命令执行（包含超时逻辑）
    #     logger.info(sandbox.execute("pwd"))
    #     logger.info(sandbox.execute("echo 'Test command execution'"))
    #
    #     # 4. 测试文件上传（包含二进制兼容逻辑）
    #     logger.info(sandbox.upload_files([("test.txt", b"Hello, World!")]))
    #
    #     # 验证文件是否真的存在
    #     logger.info(sandbox.execute("cat /home/wuying/test.txt"))
    #     # 增加这一行来查看文件到底在哪
    #     logger.info(sandbox.execute("ls -l /home/wuying/test.txt"))
    #     logger.info(sandbox.execute("cat /home/wuying/test.txt"))
    # logger.info("--- 测试结束，资源应已自动释放 ---")
    pass
