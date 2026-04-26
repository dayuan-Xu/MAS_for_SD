from pathlib import Path

import logging
import threading
from agentbay import AgentBay, CreateSessionParams, SessionResult, ContextSync, Session, ContextService, SyncPolicy
from datetime import datetime
from deepagents.backends.protocol import ExecuteResponse, FileDownloadResponse, FileUploadResponse
from deepagents.backends.sandbox import BaseSandbox
from typing import Any

from src.config.settings import settings
from src.paths import AGENTBAY_BASED_AGENT_RESOURCES_PATH

logger = logging.getLogger(__name__)

# ========== 常量定义 ==========
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


def _collect_local_files(
        local_dir: Path,
        include_patterns: list[str] | None = None
) -> list[tuple[Path, str]]:
    """收集本地目录下指定文件夹的所有文件及其相对路径。
    
    Args:
        local_dir: 本地根目录
        include_patterns: 要包含的子文件夹名称列表，如 ['memory', 'skills']
                         如果为 None，则包含所有文件
    
    Returns:
        列表，每个元素为 (本地文件路径, 相对路径字符串)
    """
    collected_files = []

    if include_patterns:
        # 只收集指定子文件夹中的文件
        for pattern in include_patterns:
            target_dir = local_dir / pattern
            if target_dir.exists() and target_dir.is_dir():
                for file_path in target_dir.rglob('*'):
                    if file_path.is_file():
                        relative_path = file_path.relative_to(local_dir)
                        rel_path_str = relative_path.as_posix()
                        collected_files.append((file_path, rel_path_str))
            else:
                logger.warning(f"⚠️  警告: 指定的文件夹不存在: {target_dir}")
    else:
        # 收集所有文件（原有行为）
        for file_path in local_dir.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(local_dir)
                rel_path_str = relative_path.as_posix()
                collected_files.append((file_path, rel_path_str))

    return collected_files


def _build_cloud_file_index(agent_bay: AgentBay, context_id: str) -> dict[str, Any]:
    """构建云端文件的索引字典，用于快速查找。
    
    Returns:
        字典，键为文件相对路径，值为文件元数据对象
    """
    cloud_file_index = {}
    list_result = agent_bay.context.list_files(
        context_id=context_id,
        parent_folder_path="/",
        page_number=1,
        page_size=1000
    )

    if list_result.success:
        for entry in list_result.entries:
            # entry.file_path 已经是相对于根目录的路径
            cloud_file_index[entry.file_path] = entry

    return cloud_file_index


def _upload_files_to_session(
        session: Session,
        files_to_sync: list[tuple[Path, str]],
        mount_path: str
) -> int:
    """将文件列表上传到会话中的指定挂载路径。
    
    ⭐ 优化：使用 AgentBay 原生的 upload_file() API，而不是 write_file()
    
    Args:
        session: AgentBay 会话对象
        files_to_sync: 待同步文件列表 [(本地路径, 相对路径), ...]
        mount_path: 云端挂载路径
    
    Returns:
        成功上传的文件数量
    """
    synced_count = 0

    for local_file, rel_path in files_to_sync:
        # ⭐ 关键修复：确保路径始终使用正斜杠（跨平台兼容）
        # 在 Windows 上，Path 对象转字符串会使用反斜杠，需要强制转换为正斜杠
        target_path = (Path(mount_path) / rel_path).as_posix()

        try:
            # 确保父目录存在
            parent_dir = str(Path(target_path).parent)
            if parent_dir and parent_dir != '.':
                session.file_system.create_directory(parent_dir)

            # ⭐ 关键优化：使用原生 upload_file API（支持二进制文件）
            upload_result = session.file_system.upload_file(
                local_path=str(local_file),
                remote_path=target_path
            )

            if upload_result.success:
                synced_count += 1
                logger.debug(f"✅ Uploaded: {local_file} -> {target_path}")
            else:
                error_msg = getattr(upload_result, 'error', 'Unknown error')
                logger.warning(f"✗ 上传失败 {rel_path}: {error_msg}")

        except Exception as e:
            logger.error(f"✗ 同步异常 {rel_path}: {e}")

    return synced_count


def sync_local_to_context(
        api_key: str,
        context_name: str,
        local_dir: str,
        mount_path: str = "/tmp/persistent/sync_target",
        image_id: str = "linux_latest",
        include_folders: list[str] | None = None
) -> bool:
    """验证并同步本地文件夹到云端持久化上下文 (Context)。
    
    工作流程：
    1. 获取或创建 Context（云端存储容器）
    2. 扫描本地指定文件夹，构建待同步列表
    3. 创建临时会话，挂载 Context
    4. 上传所有文件到云端
    5. 删除会话并同步数据到 OSS
    
    Args:
        api_key: AgentBay API密钥
        context_name: Context 的名称（如 "team-skills"）
        local_dir: 本地源文件夹路径
        mount_path: Context 在会话中的挂载路径
        image_id: 临时会话使用的镜像ID
        include_folders: local_dir下要同步的子文件夹名称列表，如 ['memory', 'skills']
                        如果为 None，则同步 local_dir 下的所有文件
    
    Returns:
        bool: 是否成功完成同步
    """
    logger.info(f"🚀 开始同步: {local_dir} -> Context '{context_name}'")

    if include_folders:
        logger.info(f"📂 将同步以下文件夹: {', '.join(include_folders)}")
    else:
        logger.info(f"📂 将同步整个目录")

    # 验证本地目录存在
    local_path = Path(local_dir)
    if not local_path.exists():
        logger.error(f"❌ 错误: 本地目录不存在: {local_dir}")
        return False

    try:
        # ========== 第1步：初始化 AgentBay 并获取 Context ==========
        agent_bay = AgentBay(api_key=api_key)

        get_result = agent_bay.context.get(context_name, create=True)
        if not get_result.success or not get_result.context:
            raise RuntimeError(f"Failed to get/create context: {get_result.error_message}")

        context = get_result.context
        logger.info(f"✅ Context ID: {context.id}")

        # ========== 第2步：收集本地文件 ==========
        local_files = _collect_local_files(local_path, include_folders)

        if not local_files:
            logger.info(f"✨ 未发现需要同步的文件。")
            return True

        logger.info(f"📁 发现 {len(local_files)} 个待同步文件")

        # ========== 第3步：创建会话并上传文件 ==========
        logger.info(f"🔗 创建临时会话进行文件同步...")
        context_sync = ContextSync.new(context.id, mount_path)
        params = CreateSessionParams(image_id=image_id, context_syncs=[context_sync])
        session_result = agent_bay.create(params)

        if not session_result.success or not session_result.session:
            raise RuntimeError(f"Failed to create session: {session_result.error_message}")

        session = session_result.session
        logger.info(f"✅ 会话创建成功: {session.session_id}")

        # 上传所有文件
        synced_count = _upload_files_to_session(session, local_files, mount_path)

        # ========== 第4步：清理会话并同步到 OSS ==========
        logger.info(f"💾 正在同步会话中的context box数据到OSS...")
        agent_bay.delete(session, sync_context=True)  # sync_context=True 确保数据写入 OSS

        logger.info(f"✅ 同步完成，同步用的会话也已经删除！共处理 {synced_count}/{len(local_files)} 个文件。")
        return True

    except Exception as e:
        logger.error(f"❌ 同步过程出错: {str(e)}", exc_info=True)
        return False


CONTEXT_NAME_OF_AGENT_RESOURCES = "agent-resources"  # 该存储盒的名称，内含'/skills'、'/memory'两个文件夹
CONTEXT_MOUNT_PATH_OF_AGENT_RESOURCES = "/tmp/persistent/agent_workspace"  # 该存储盒在会话环境中挂载到的目录

CONTEXT_MOUNT_PATH_PREFIX_OF_NEW_TASK = "/tmp/persistent/agent_workspace/warehouse"  # 开发新任务时，将新任务工作空间挂载到该目录下


def init_remote_agent_resources(
        api_key: str = settings.WUYING_AGENTBAY_API_KEY,
        local_agent_resources_dir=AGENTBAY_BASED_AGENT_RESOURCES_PATH,
        include_folders: list[str] | None = None
):
    """将本地智能体开发团队的运行时资源上传到云端存储盒。
    
    Args:
        api_key: AgentBay API密钥
        local_agent_resources_dir: 保存智能体运行时所需资源的本地文件路径
        include_folders: 要同步的子文件夹列表，如 ['memory', 'skills']；如果明确传入 None，则同步整个工作空间
    
    示例:
        # 只同步 memory 和 skills 文件夹
        init_remote_agent_resoureces(include_folders=['memory', 'skills'])
        
        # 同步整个运行时资源
        init_remote_agent_resources()
    """
    return sync_local_to_context(
        api_key=api_key,
        context_name=CONTEXT_NAME_OF_AGENT_RESOURCES,
        local_dir=local_agent_resources_dir,
        mount_path=CONTEXT_MOUNT_PATH_OF_AGENT_RESOURCES,
        include_folders=include_folders
    )


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
        self.reuse_existing = reuse_existing
        self._agent_bay = AgentBay(api_key=api_key)
        self._image_id = image_id
        self._idle_timeout = idle_timeout
        self._session = None
        self._session_id = None  # 用于重连本次创建的会话

        # ⭐ 关键修复：添加线程锁保护，防止并发竞态条件导致重复创建会话
        self._session_lock = threading.Lock()  # 线程锁，确保只有一个线程执行初始化

        # 注意：这里不再立即调用 _initialize_session()，而是等到第一次使用时再创建

    def _get_agent_resources_context_sync(self) -> ContextSync:
        """获取智能体运行时资源的 Context。
        
        ⚠️ 重要：该方法仅获取已存在的 Context，不会自动创建。
        必须在调用 MySandbox 之前，手动调用 init_remote_agent_resources() 确保 Context 已创建并上传资源。
        
        Returns:
            ContextSync: 配置好的上下文同步对象
            
        Raises:
            RuntimeError: 如果 Context 不存在
        """
        context_service: ContextService = self._agent_bay.context
        logger.info("🔍 获取智能体资源上下文...")

        # 尝试获取已存在的 Context（不自动创建）
        get_result = context_service.get(CONTEXT_NAME_OF_AGENT_RESOURCES, create=False)

        if not get_result.success or not get_result.context:
            error_msg = get_result.error_message if get_result.error_message else "未找到上下文"
            logger.error(
                f"❌ 智能体资源上下文 '{CONTEXT_NAME_OF_AGENT_RESOURCES}' 不存在！\n"
                f"   错误信息: {error_msg}\n"
                f"   解决方案: 请在创建 MySandbox 实例之前调用 init_remote_agent_resources()\n"
                f"   示例:\n"
                f"       from src.utils.my_sandbox import init_remote_agent_resources\n"
                f"       init_remote_agent_resources()  # 先初始化上下文\n"
                f"       sandbox = MySandbox(task_name='...')  # 再创建沙盒"
            )
            raise RuntimeError(
                f"未找到智能体资源上下文 '{CONTEXT_NAME_OF_AGENT_RESOURCES}'。"
                f"请在创建 MySandbox 之前调用 init_remote_agent_resources()。"
                f"错误信息: {error_msg}"
            )

        agent_resources_context = get_result.context
        logger.info(f"✅ 智能体资源上下文加载成功, SDKCtx ID: {agent_resources_context.id}")
        return ContextSync.new(agent_resources_context.id, CONTEXT_MOUNT_PATH_OF_AGENT_RESOURCES, SyncPolicy.default())

    def _get_task_context_sync(self) -> ContextSync | None:
        """获取或创建当前任务的 Context。
        
        Returns:
            ContextSync | None: 如果存在 task_name，返回配置好的上下文同步对象；否则返回 None
        """
        if not self.task_name:
            return None

        context_service: ContextService = self._agent_bay.context
        task_context = None
        logger.info(f"🔍 检查任务上下文: {self.task_name}")
        get_result = context_service.get(self.task_name)

        # 情况 1: 复用现存 context
        if get_result.success and self.reuse_existing and get_result.context is not None:
            task_context = get_result.context
            logger.info(f"📦 复用现有任务上下文: {self.task_name}")

        # 情况 2: 不重用，创建带时间戳的新 context
        elif get_result.success and not self.reuse_existing:
            new_name = f"{self.task_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            old_name = self.task_name
            self.task_name = new_name
            logger.warning(
                f"❗ 任务上下文 '{old_name}' 已存在，创建新的: '{new_name}'"
            )
            create_result = context_service.create(new_name)

            if not create_result.success or not create_result.context:
                logger.error(f"❌ 创建上下文失败: {create_result.error_message}")
                raise RuntimeError(f"创建上下文失败: {create_result.error_message}")

            task_context = create_result.context
            logger.info(f"✅ 任务上下文创建成功: {task_context.id}, 任务名: {self.task_name}")

        # 情况 3: 不存在，创建全新的 context
        elif not get_result.success:
            logger.info(f"📦 为任务创建新上下文: {self.task_name}")
            create_result = context_service.create(self.task_name)

            if not create_result.success or not create_result.context:
                logger.error(f"❌ 创建上下文失败: {create_result.error_message}")
                raise RuntimeError(f"创建上下文失败: {create_result.error_message}")

            task_context = create_result.context
            logger.info(f"✅ 新任务上下文创建成功: {task_context.id}, 任务名: {self.task_name}")

        # 确定该 context 的挂载路径
        context_mount_path = f"{CONTEXT_MOUNT_PATH_PREFIX_OF_NEW_TASK}/{self.task_name}"
        return ContextSync.new(task_context.id, context_mount_path)

    def _get_context_syncs(self) -> list[ContextSync]:
        """获取所有需要挂载的 Context 同步配置。
        
        Returns:
            list[ContextSync]: 包含 agent 资源 context 和（可选的）task context
        """
        my_context_syncs = []

        # 不再这么做，而是采用组合式后端，基于路径前缀，将文件操作路由到不同的后端！

        # # 1. 添加智能体运行时资源 context
        # agent_resources_sync = self._get_agent_resources_context_sync()
        # my_context_syncs.append(agent_resources_sync)

        # 2. 添加任务 context（如果存在 task_name）
        task_sync = self._get_task_context_sync()
        if task_sync is not None:
            my_context_syncs.append(task_sync)

        return my_context_syncs

    def _initialize_session(self):
        """创建AgentBay会话并挂载持久化上下文"""
        # 获得过激活的会话
        if self._session_id:
            logger.info(f"♻️ 复用现有会话: {self._session_id}")
            self._session = self._agent_bay.get(self._session_id).session
            if self._session is None:
                logger.error(f"❌ 获取会话失败: {self._session_id}")
                raise RuntimeError(f"获取会话失败: {self._session_id}")
            logger.info(f"✅ 会话复用成功, SessionId={self._session.session_id}")

        logger.info(f"🚀 初始化会话... 任务名={self.task_name}, 镜像ID={self._image_id}")

        # 获取持久化上下文。
        # 若想同步内部已经有内容的context box，
        # 会在同步它时遇到错误（Wait OSS credential timeout (>10s)），
        # 因此只选择为task创建一个task context box
        my_context_syncs = self._get_context_syncs()

        # 创建会话，该会话具备持久化数据
        logger.info("🔗 创建带上下文的会话...")
        logger.debug(f"  - 镜像 ID: {self._image_id}")
        logger.debug(f"  - 上下文同步数量: {len(my_context_syncs)}")
        for i, ctx_sync in enumerate(my_context_syncs):
            logger.debug(f"    [{i}] 上下文 ID: {ctx_sync.context_id}")
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
            logger.error(f"❌ 创建会话失败: {error_msg}")
            logger.error(f"   结果对象: {result}")
            raise RuntimeError(f"创建 AgentBay 会话失败: {error_msg}")

        self._session = result.session
        self._session_id = self._session.session_id
        # 打印创建成功的会话信息
        logger.info(
            f"✅ 会话创建成功, SessionId={self._session.session_id}, 空闲超时={self._idle_timeout}s")

    def check_session(self):
        """ 检查会话有效性，如未创建则初始化（失效则抛致命错误）
        
        ⭐ 关键修复：使用双重检查锁定模式（Double-Checked Locking）防止并发竞态条件
        
        工作原理：
        1. 第一次检查（不加锁）：如果会话已存在，直接验证并返回（高性能路径）
        2. 第二次检查（加锁后）：防止在等待锁的过程中，其他线程已完成初始化
        3. 锁的互斥性保证：同一时刻只有一个线程能执行初始化代码
        
        Raises:
            RuntimeError: 会话已失效，程序必须终止
        """
        logger.info(f"🔍 检查会话有效性: {self._session_id}")
        # ===== 快速路径：如果会话已存在，直接验证有效性（避免不必要的锁竞争）=====
        if self._session is not None:
            info_result = self._session.info()

            if info_result.success:
                # 会话正常，无需操作
                logger.info(f"✅ 会话 {self._session_id}  仍然有效，因为session.info()返回成功信息！")
                return

            # 会话已被云端自动释放，这是致命错误！
            logger.error(
                f"❌ [致命错误] 会话 {self._session_id} 已被云端自动释放！\n"
                f"   原因: {info_result.error_message}\n"
                f"   此错误不可恢复 - 开发流程必须终止。"
            )
            raise RuntimeError(
                f"[致命错误] 任务 '{self.task_name}' 的会话已被 AgentBay 云端自动释放。\n"
                f"这通常发生在会话超过空闲超时时间 ({self._idle_timeout}s) 时。\n"
                f"开发流程无法继续。请使用新会话重新启动。"
            )

        # ===== 慢速路径：需要初始化，使用锁保护 =====
        with self._session_lock:
            # 双重检查：获取锁后再次确认是否需要初始化
            # （可能在你等待锁的过程中，其他线程已经完成了初始化）
            if self._session is not None:
                logger.debug("⏳ 其他线程已在等待锁期间完成初始化，直接复用")
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
            except Exception as e:
                logger.error(f"❌ 会话初始化失败: {e}")
                raise

    def execute(
            self,
            command: str,
            *,
            timeout: int | None = None,
    ) -> ExecuteResponse:
        """Execute a command in the sandbox and return ExecuteResponse.
        
        ⭐ 关键修复：确保云端 Python 脚本使用 UTF-8 编码执行
        """
        self.check_session()  # 获取或创建有效会话
        try:
            # Convert timeout from seconds (protocol) to milliseconds (AgentBay)
            timeout_ms = int(timeout * 1000) if timeout is not None else None

            # ⭐ 关键修复：为 Python 命令添加 UTF-8 编码环境变量
            # 检测是否是 Python 命令（由 BaseSandbox.read/ls/grep/glob 等方法生成）
            # 使用更宽松的检测：只要命令中包含 'python' 就添加环境变量
            if 'python' in command.lower():
                # 在命令前添加 PYTHONUTF8=1，确保 Python 使用 UTF-8 编码
                command = f"PYTHONUTF8=1 {command}"
                logger.debug(f"🔧 Added PYTHONUTF8=1 to Python command")

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
            logger.error(f"❌ Command execution failed: {e}")
            return ExecuteResponse(
                output=f"Error executing command: {str(e)}",
                exit_code=1,
                truncated=False
            )

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """Upload multiple files to the sandbox.
        
        ⭐ 优化：使用 AgentBay 原生的 upload_file() API，而不是 write_file()
        通过临时文件桥接 bytes → 本地文件 → 云端
        """
        self.check_session()  # 获取或创建有效会话
        responses = []
        import tempfile
        import os

        for file_path, content in files:
            temp_file_path = None
            try:
                logger.debug(f"📤 Uploading file: {file_path} ({len(content)} bytes)")

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
                    logger.debug(f"✅ Upload successful: {file_path}")
                    responses.append(FileUploadResponse(path=file_path))
                else:
                    error_msg = getattr(upload_result, 'error', 'Unknown error')
                    logger.error(f"❌ Upload failed: {file_path}, Error: {error_msg}")
                    responses.append(FileUploadResponse(
                        path=file_path,
                        error=f"Upload failed: {error_msg}"
                    ))

            except Exception as e:
                logger.error(f"❌ Upload exception: {file_path}, Error: {e}")
                import traceback
                traceback.print_exc()
                responses.append(FileUploadResponse(
                    path=file_path,
                    error=str(e)
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
        """
        self.check_session()  # 获取或创建有效会话
        responses = []
        import tempfile
        import os

        for file_path in paths:
            temp_file_path = None
            try:
                logger.debug(f"📥 Downloading file: {file_path}")

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

                    logger.debug(f"✅ Download successful: {file_path} ({len(content)} bytes)")
                    responses.append(FileDownloadResponse(
                        path=file_path,
                        content=content
                    ))
                else:
                    error_msg = getattr(download_result, 'error', 'Unknown error')
                    logger.error(f"❌ Download failed: {file_path}, Error: {error_msg}")
                    responses.append(FileDownloadResponse(
                        path=file_path,
                        error=f"Download failed: {error_msg}"
                    ))

            except Exception as e:
                logger.error(f"❌ Download exception: {file_path}, Error: {e}")
                import traceback
                traceback.print_exc()
                responses.append(FileDownloadResponse(
                    path=file_path,
                    error=str(e)
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
        self.cleanup()
        if exc_type:
            logger.info(f"❌ 沙盒运行期间发生错误: {exc_val}")
        return False  # 不吞掉异常

    def cleanup(self):
        """清理资源，删除AgentBay会话"""
        if self._session:
            logger.info(f"🧹 清理会话, SessionId={self._session.session_id}")
            try:
                # 将当前会话中对存储盒内文件的更改同步到OSS上该存储盒对应位置
                self._agent_bay.delete(self._session, sync_context=True)
                logger.info("✅ 会话清理成功")
            except Exception as e:
                logger.warning(f"❌ 清理过程中捕获异常: {e}")
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
            logger.error("❌ 会话不存在，跳过下载")
            logger.info("会话不存在，无法下载成果物")
            return False

        try:
            # 构造云端挂载路径
            cloud_path = f"{CONTEXT_MOUNT_PATH_PREFIX_OF_NEW_TASK}/{self.task_name}"
            logger.info(f"📂 云端源路径: {cloud_path}")

            # 确保本地目录存在
            local_download_dir.mkdir(parents=True, exist_ok=True)

            # 递归下载所有文件
            downloaded_count = self._download_recursive(cloud_path, local_download_dir)
            logger.info(f"✅ 下载完成: 共 {downloaded_count} 个文件")
            logger.info(f"✅ 成功下载 {downloaded_count} 个文件到: {local_download_dir}")
            return True

        except Exception as e:
            logger.error(f"❌ 下载失败: {e}")
            import traceback
            traceback.print_exc()
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

            for entry in list_result.entries:
                cloud_path = entry.path
                # 计算相对路径
                relative_path = Path(cloud_path).relative_to(CONTEXT_MOUNT_PATH_PREFIX_OF_NEW_TASK)

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
                        logger.error(f"❌ 下载异常: {cloud_path}, 错误: {e}")
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
        self.cleanup()


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
