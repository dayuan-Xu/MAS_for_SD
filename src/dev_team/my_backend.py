# 导入必要的模块
import base64
import json
import logging
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

from agentbay import AgentBay, CreateSessionParams, SessionResult, ContextSync, ContextService, CommandResult, \
    UploadResult, DownloadResult, Session
from deepagents.backends.protocol import ExecuteResponse, FileDownloadResponse, FileUploadResponse
from deepagents.backends.protocol import ReadResult, FileData
from deepagents.backends.sandbox import BaseSandbox
from deepagents.backends.utils import _get_file_type

from src.config.config_logging import setup_logging
from src.config.settings import settings
from src.dev_team.team_config import CONTEXT_MOUNT_PATH_PREFIX_OF_NEW_TASK_CONTEXT_BOX, AGENTBAY_IMAGE_ID
from src.paths import LOCAL_WAREHOUSE_PATH
from src.utils.common import to_snake_case, should_skip_path, write_content_to_file, process_command_parts, \
    map_agentbay_error_to_file_operation_error

logger = logging.getLogger(__name__)

# ========== 常量定义 ==========
READ_COMMAND_TEMPLATE = """python3 -c "
import os, sys, base64, json

MAX_OUTPUT_BYTES = 500 * 1024
MAX_BINARY_BYTES = 500 * 1024
TRUNCATION_MSG = '\\n\\n' + (
    '[Output was truncated due to size limits. '
    'This paginated read result exceeded the sandbox stdout limit. '
    'Continue reading with a larger offset or smaller limit to inspect the rest of the file.]'
)

path = base64.b64decode('{path_b64}').decode('utf-8')

if not os.path.isfile(path):
    print(json.dumps({{'error': 'file_not_found'}}))
    sys.exit(0)

if os.path.getsize(path) == 0:
    print(json.dumps({{'encoding': 'utf-8', 'content': 'System reminder: File exists but has empty contents'}}))
    sys.exit(0)

file_type = '{file_type}'
if file_type != 'text':
    file_size = os.path.getsize(path)
    if file_size > MAX_BINARY_BYTES:
        print(json.dumps({{'error': 'Binary file exceeds maximum preview size of ' + str(MAX_BINARY_BYTES) + ' bytes'}}))
        sys.exit(0)
    with open(path, 'rb') as f:
        raw = f.read()
    print(json.dumps({{'encoding': 'base64', 'content': base64.b64encode(raw).decode('ascii')}}))
    sys.exit(0)

with open(path, 'rb') as f:
    raw_prefix = f.read(8192)

try:
    raw_prefix.decode('utf-8', errors='replace')
except Exception as e:
    error_msg = '尝试读取text类型文件的前8192个字节并用utf-8解码，但是出现严重错误：' + str(e) + '，本次将会将返回该文件的前8192个字节的base64字符串'
    print(json.dumps({{
        'error': error_msg,
        'encoding': 'base64',
        'content': base64.b64encode(raw_prefix).decode('ascii')
    }}))
    sys.exit(0)

offset = {offset}
limit = {limit}
line_count = 0
returned_lines = 0
truncated = False
parts = []
current_bytes = 0
msg_bytes = len(TRUNCATION_MSG.encode('utf-8'))
effective_limit = MAX_OUTPUT_BYTES - msg_bytes

with open(path, 'r', encoding='utf-8', newline=None) as f:
    for raw_line in f:
        line_count += 1
        if line_count <= offset:
            continue
        if returned_lines >= limit:
            break

        line = raw_line.rstrip('\\n').rstrip('\\r')
        piece = line if returned_lines == 0 else '\\n' + line
        piece_bytes = len(piece.encode('utf-8'))
        if current_bytes + piece_bytes > effective_limit:
            truncated = True
            remaining_bytes = effective_limit - current_bytes
            if remaining_bytes > 0:
                prefix = piece.encode('utf-8')[:remaining_bytes].decode('utf-8', errors='ignore')
                if prefix:
                    parts.append(prefix)
                    current_bytes += len(prefix.encode('utf-8'))
            break

        parts.append(piece)
        current_bytes += piece_bytes
        returned_lines += 1

if returned_lines == 0 and not truncated:
    print(json.dumps({{'error': 'Line offset ' + str(offset) + ' exceeds file length (' + str(line_count) + ' lines)'}}))
    sys.exit(0)

text = ''.join(parts)
if truncated:
    text += TRUNCATION_MSG

print(json.dumps({{'encoding': 'utf-8', 'content': text}}))
" 2>&1"""


# 该类通过无影agentbay的session实现sandbox backend，目前仅仅支持linux session，因为agentbay仅linux_latest镜像预装了python命令
# 而BaseSandbox通过调用self.execute方法执行python3 -c "python脚本"来提供文件系统接口
class LinuxSandboxBackend(BaseSandbox):
    """基于无影AgentBay实现的云沙盒后端。 注意！沙盒会话最长运行时间需要在镜像中配置，的确为linux_latest配置了2h最长会话运行时间。

    该类通过无影AgentBay的session提供真正的云端沙盒环境，
    所有文件操作和命令执行都在云端进行，而非本地。
    """

    def __init__(self,
                 *,
                 task_name: str = "",
                 image_id: str = AGENTBAY_IMAGE_ID,
                 reuse_existing_task_context_box: bool = True,
                 api_key: str = settings.WUYING_AGENTBAY_API_KEY,
                 idle_timeout: int = 60 * 60):
        """初始化MySandbox。

        Args:
            task_name: 当前软件开发任务的名称，用于创建持久化的存储盒，持久化保存智能体的文件写入操作（允许智能体可以访问该沙盒）。因此可以后续下载当前软件的成果物文件到本地
            reuse_existing_task_context_box: 针对当前task_name，是否复用已有的 Context（支持棕地开发）
            api_key: AgentBay API密钥
            image_id: 沙盒镜像ID
            idle_timeout: 云端会话空闲自动释放时间（秒），默认1h（60*60秒），太短的话，很有可能在等待智能体输出大块内容（这需要llm耗费10min左右来输出3.8万个字符）之前，该会话就会被自动释放了！！！
        """
        logger.info(f"开始初始化 {self.__class__.__name__}  实例")
        self.task_name = task_name  # 公开属性，供外部访问
        self._task_context_box_leaf_dir_name = to_snake_case(task_name) if task_name else ""
        self.reuse_existing = reuse_existing_task_context_box
        self.agentbay = AgentBay(api_key=api_key)
        self.image_id = image_id
        self.sandbox_type = "linux"

        self._idle_timeout = idle_timeout
        self._sandbox_max_running_time_str = "3 hours"  # 当前镜像的最长持续运行时间（字符串描述）
        self._sandbox_max_running_time_seconds = 3 * 60 * 60  # 3小时转换为秒
        self.time_for_products_download = 10  # 在达到当前镜像的最长持续运行时间的10 分钟前主动提前释放沙盒会话
        self._session_start_time = None  # 会话创建时间戳
        self._session: Session = None  # 初始化为None，释放后也应该赋值为None
        self._session_id = None  # 用于暂停会话后，重新连接该会话（目前未实现会话暂停）。初始化为None
        self.sandbox_id = None  # 即self._session_id，用于向智能体开发团队暴露其各种AgentBay MCP工具的的执行环境
        self.task_context_box_id = None  # 存储任务上下文盒子的ID

        # 明确定义 task_context_box_name 初始值为task_name
        self.task_context_box_name = task_name

        # 确定当前 task的context box 在sandbox中的挂载路径
        self._task_context_box_mount_path_prefix = CONTEXT_MOUNT_PATH_PREFIX_OF_NEW_TASK_CONTEXT_BOX[
            f'{self.sandbox_type}']
        self.task_context_box_mount_path = f"{self._task_context_box_mount_path_prefix}/{self._task_context_box_leaf_dir_name}"
        logger.info(
            f"当前Task Context Box 的云端挂载路径为{self.task_context_box_mount_path}\n智能体必须在该路径下进行开发、文件写入，否则任务成果物无法下载到本地！")

        self._initialize_session()  # 创建会话

        logger.info(f"✅ {self.__class__.__name__} 实例初始化完成")
        logger.info(f"\n{self}")

    @property
    def id(self) -> str:
        """Unique identifier for the sandbox backend."""
        if self._session is None:
            raise RuntimeError("Session not initialized")
        return self._session.session_id

    def check_session_remaining_time(self):
        """检查会话剩余时间，如果接近最大运行时间则提前清理并抛出异常。

        ⚠️ 在通过当前对象的_session属性调用AgentBay MCP 工具前必须调用此方法，以防止会话过期导致操作失败。

        Raises:
            RuntimeError: 当会话剩余时间不足10分钟时抛出
        """
        if self._session_start_time is None:
            logger.warning("⚠️ 会话创建时间未记录，跳过时间检查")
            return

        # 计算已运行时间
        elapsed_time = datetime.now() - self._session_start_time
        elapsed_seconds = elapsed_time.total_seconds()

        # 计算剩余时间
        remaining_seconds = self._sandbox_max_running_time_seconds - elapsed_seconds

        if remaining_seconds < 0:
            # 会话已过期，但是还有工具调用在执行，则抛出异常给ToolRetryMiddleware的钩子函数
            raise RuntimeError(f"⚠️ 沙盒会话已被主动提前断开并且距离断开已经过了一段时间！\n"
                               f"   - 最大运行时间: {self._sandbox_max_running_time_str} ({self._sandbox_max_running_time_seconds}秒)\n"
                               f"   - 已运行时间: {elapsed_seconds / 60:.1f} 分钟\n"
                               f"   - 会话已经过期了{(-remaining_seconds) / 60} 分钟 {(-remaining_seconds) % 60} 秒\n")

        # 如果剩余时间不足10分钟=10*60秒，提前清理并抛出异常
        time_threshold_seconds = self.time_for_products_download * 60
        if 0 <= remaining_seconds <= time_threshold_seconds:
            remaining_minutes = remaining_seconds / 60

            logger.debug(f"🕒 会话运行状态: 已运行 {elapsed_seconds / 60:.1f} 分钟, 剩余 {remaining_minutes:.1f} 分钟")
            if self._session is not None:
                # 第一次检测到应该释放，那就释放。
                error_msg = (
                    f"沙盒会话即将达到最大运行时间限制！\n"
                    f"   - 最大运行时间: {self._sandbox_max_running_time_str} ({self._sandbox_max_running_time_seconds}秒)\n"
                    f"   - 已运行时间: {elapsed_seconds / 60:.1f} 分钟\n"
                    f"   - 剩余时间: {remaining_minutes:.1f} 分钟\n"
                    f"   - 会话ID: {self._session_id}\n"
                    f"为避免会话突然过期导致沙盒软件成果物无法及时下载到本地，将主动提前断开当前沙盒会话。"
                )

                logger.error(f"❌ {error_msg}")

                # 主动删除会话，同步数据到 OSS
                try:
                    self.download_task_artifacts(LOCAL_WAREHOUSE_PATH / self.task_name)
                    self.delete_session()
                    logger.info("✅ 为避免会话突然过期导致沙盒软件成果物无法及时下载到本地，已主动清理成功即将过期的会话")
                except Exception as e:
                    logger.warning(
                        f"⚠️ 为避免会话突然过期导致沙盒软件成果物无法及时下载到本地，主动清理会话时出现异常: {e}")

                else:
                    raise RuntimeError(error_msg)
            elif self._session_id is None:
                # 已经释放掉，但是还有工具调用正在执行，则抛出异常给ToolRetryMiddleware的钩子函数
                raise RuntimeError(f"⚠️ 沙盒会话已被主动提前断开！\n"
                                   f"   - 最大运行时间: {self._sandbox_max_running_time_str} ({self._sandbox_max_running_time_seconds}秒)\n"
                                   f"   - 已运行时间: {elapsed_seconds / 60:.1f} 分钟\n")

    def execute(
            self,
            command: str,
            *,
            timeout: int | None = None,
    ) -> ExecuteResponse:
        """Execute a command in the sandbox and return ExecuteResponse.

        确保云端 Python 脚本使用 UTF-8 编码执行
        """
        # 在下载文件前检查会话剩余时间
        self.check_session_remaining_time()

        # 如果智能体调用execute工具时没有传入timeout参数，那么默认timeout是50秒
        if timeout is None:
            timeout = 50

        # Convert timeout from seconds (protocol) to milliseconds (AgentBay)
        timeout_ms = int(timeout * 1000)

        # 为 Python 命令添加 UTF-8 编码环境变量,以便智能体调用read、ls、grep、glob工具时看到正确的文字输出。
        # 检测是否是 Python 命令(已知 BaseSandbox.read/ls/grep/glob 等方法执行时,底层会调用execute方法执行python代码,方式大致为python -c "python代码")
        # 关键修复：只在 python/python3 命令前添加环境变量，而不是在整个命令前添加
        if 'python' in command.lower():

            if self.sandbox_type == "linux":
                # Linux/Unix: 使用正则表达式找到所有 python/python3 命令并在其前添加 PYTHONUTF8=1
                # 策略：将命令按 && || ; | 分割，对每个子命令检查是否以 python 开头
                modified_command = process_command_parts(command)

                if modified_command != command:
                    logger.debug(f"🔧 已为 Python 命令添加 UTF-8 编码环境变量")
                    logger.debug(f"   原始命令: {command}")
                    logger.debug(f"   修改后: {modified_command}")
                    command = modified_command

            elif self.sandbox_type == "windows":
                # Windows CMD: 需要在每个 python 命令前添加 set PYTHONUTF8=1 &&
                # 但 Windows 下处理更复杂，简单起见，如果命令以 python 开头则添加
                if command.strip().lower().startswith('python'):
                    command = f"set PYTHONUTF8=1 && {command}"
                    logger.debug(f"🔧 已为 Python 命令添加 UTF-8 编码环境变量 (Windows)")

        # agentbay execute工具默认的超时时间是50秒
        command_result: CommandResult = self._session.command.execute_command(command, timeout_ms=timeout_ms)

        output = command_result.output  # shell命令执行后的stdout+stderr
        exit_code = command_result.exit_code

        if not command_result.success:
            error_msg = command_result.error_message
            output = error_msg
            if r'"system_error":"Command timed out"' in error_msg:
                output = f"shell命令执行超时（timeout={timeout}），请为本次shell命令（{command}）设置更大的timeout后重试！"

            logger.error(
                f"❌ session.command.execute_command 执行失败:\n"
                f"失败的shell命令：\n"
                f"{command}\n"
                f"超时时间设置：{timeout} 秒\n"
                f"智能体所见的shell工具执行结果：\n"
                f"{output}\n"
                f"API返回的错误消息：\n"
                f"{error_msg}\n")
            return ExecuteResponse(
                output=output,
                exit_code=exit_code,
                truncated=False
            )

        logger.debug(f"✅ session.command.execute_command 执行成功\n"
                     f"执行的命令：\n"
                     f"{command}\n"
                     f"超时时间设置：{timeout} 秒\n"
                     f"命令执行结果：\n"
                     f"{output}")

        return ExecuteResponse(
            output=output,
            exit_code=exit_code,
            truncated=False
        )

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """Upload multiple files to the sandbox.
        
        使用 AgentBay 原生的 upload_file() API，而不是 write_file()
        通过临时文件桥接 bytes → 本地文件 → 云端
        """
        # 在下载文件前检查会话剩余时间
        self.check_session_remaining_time()

        responses = []
        for file_path, content in files:
            temp_file_path = None
            logger.debug(f"📤 正在上传文件: {file_path} ({len(content)} 字节)")

            # 确保父目录存在
            parent_dir = str(Path(file_path).parent)
            if parent_dir and parent_dir != '.':
                self._session.file_system.create_directory(parent_dir)

            # 创建临时文件，使用 AgentBay 原生 upload_file API
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.tmp') as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name

            # 使用 AgentBay 原生 upload_file API（支持二进制文件）
            upload_result: UploadResult = self._session.file_system.upload_file(
                local_path=temp_file_path,
                remote_path=file_path
            )

            if upload_result.success:
                logger.debug(f"✅ 上传成功: {file_path}")
                responses.append(FileUploadResponse(path=file_path))
            else:
                error_msg = getattr(upload_result, 'error_message', '未知错误')
                logger.error(
                    f"❌ session.file_system.upload_file 执行失败:\n目标文件路径 {file_path},\n错误: {error_msg}")
                # 清理临时文件
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to clean up temp file: {temp_file_path}, Error: {e}")

                # 将 AgentBay 错误映射到标准 FileOperationError
                standardized_error = map_agentbay_error_to_file_operation_error(error_msg)
                responses.append(FileUploadResponse(
                    path=file_path,
                    error=standardized_error
                ))
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """Download multiple files from the sandbox.
        
        优化：使用 AgentBay 原生的 download_file() API，而不是 read_file()
        通过临时文件桥接 云端 → 本地文件 → bytes
        """
        # 在下载文件前检查会话剩余时间
        self.check_session_remaining_time()

        responses = []
        for file_path in paths:
            temp_file_path = None
            logger.debug(f"📥 正在下载文件: {file_path}")

            # 关键优化：创建临时文件，使用 AgentBay 原生 download_file API
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.tmp') as temp_file:
                temp_file_path = temp_file.name

            # 使用 AgentBay 原生 download_file API（支持二进制文件）
            download_result: DownloadResult = self._session.file_system.download_file(
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
                error_msg = getattr(download_result, 'error_message', '未知错误')
                logger.error(
                    f"❌ session.file_system.download_file 执行失败:\n目标文件路径 {file_path},\n错误: {error_msg}")
                # 清理临时文件
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to clean up temp file: {temp_file_path}, Error: {e}")

                # 将 AgentBay 错误映射到标准 FileOperationError
                standardized_error = map_agentbay_error_to_file_operation_error(error_msg)
                responses.append(FileDownloadResponse(
                    path=file_path,
                    error=standardized_error
                ))

        return responses

    def _get_task_context_sync(self) -> ContextSync | None:
        """获取或创建当前任务的 Context。

        Returns:
            ContextSync | None: 如果存在 task_name，返回配置好的上下文同步对象；否则返回 None
        """
        if not self.task_context_box_name:
            return None

        context_service: ContextService = self.agentbay.context
        task_context = None
        logger.info(f"🔍 检查任务存储盒是否存在: {self.task_context_box_name}")
        get_result = context_service.get(self.task_context_box_name)

        # 情况 1: 复用现存 context
        if get_result.success and self.reuse_existing and get_result.context is not None:
            task_context = get_result.context
            logger.info(f"{self.task_context_box_name} 已经存在，复用现有任务存储盒。")

        # 情况 2: 不重用，创建带时间戳的新 context
        elif get_result.success and not self.reuse_existing:
            new_name = f"{self.task_context_box_name}_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}"
            old_name = self.task_context_box_name
            # 更新任务存储盒名
            self.task_context_box_name = new_name
            logger.warning(
                f"❗ 任务存储盒 '{old_name}' 已存在，创建新的: '{new_name}'"
            )
            create_result = context_service.create(new_name)

            if not create_result.success or not create_result.context:
                logger.error(f"❌ 创建存储盒失败: {create_result.error_message}", exc_info=True)
                raise RuntimeError(f"创建存储盒失败: {create_result.error_message}")

            task_context = create_result.context
            logger.info(f"✅ 任务存储盒创建成功: {task_context.id}, 存储盒名: {self.task_context_box_name}")

        # 情况 3: 不存在，创建全新的 context
        elif not get_result.success:
            logger.info(f"为任务创建新存储盒: {self.task_context_box_name}")
            create_result = context_service.create(self.task_context_box_name)

            if not create_result.success or not create_result.context:
                logger.error(f"❌ 创建存储盒失败: {create_result.error_message}", exc_info=True)
                raise RuntimeError(f"创建存储盒失败: {create_result.error_message}")

            task_context = create_result.context
            logger.info(f"✅ 新任务存储盒创建成功: {task_context.id}, 存储盒名: {self.task_context_box_name}")

        # 保存 context ID，供外部访问
        self.task_context_box_id = task_context.id
        return ContextSync.new(task_context.id, self.task_context_box_mount_path)

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

        max_retries = 3
        retry_delay = 5  # 初始重试延迟5秒

        for attempt in range(max_retries):
            try:
                # 获得过激活的会话
                if self._session_id:
                    logger.info(f"♻️ 当前沙盒的_session_id不为空，复用该暂停状态下的会话: {self._session_id}")
                    self._session = self.agentbay.get(self._session_id).session
                    if self._session is None:
                        logger.error(f"❌ 获取活跃会话失败: {self._session_id}", exc_info=True)
                        raise RuntimeError(f"获取会话失败: {self._session_id}")
                    logger.info(f"✅ 会话复用成功, SessionId={self._session.session_id}")
                    return

                # 获取持久化存储盒。
                # 若想同步内部已经有内容的context box，
                # 会在同步它时遇到错误（Wait OSS credential timeout (>10s)），
                # 因此只选择为task创建一个task context box
                my_context_syncs = self._get_context_syncs()

                # 创建会话，该会话具备持久化数据
                logger.info(
                    f"🚀 开始创建会话 Session，IMAGEID={self.image_id}，Task name={self.task_name}")

                for i, ctx_sync in enumerate(my_context_syncs):
                    logger.debug(f"    [{i}] 存储盒 ID: {ctx_sync.context_id}")

                params = CreateSessionParams(
                    image_id=self.image_id,
                    context_syncs=my_context_syncs,
                    idle_release_timeout=self._idle_timeout  # 关键：设置云端空闲超时
                )

                result: SessionResult = self.agentbay.create(params)

                if not result.success or result.session is None:
                    error_msg = getattr(result, 'error_message', '未知错误')
                    logger.error(f"❌ 创建会话 Session 失败: {error_msg}", exc_info=True)
                    logger.error(f"   结果对象: {result}")
                    raise RuntimeError(f"创建 AgentBay Session 失败: {error_msg}")

                # 打印会话成功创建的信息
                self._session = result.session
                self._session_id = self._session.session_id
                logger.info(f"✅ AgentBay 会话创建成功, SessionId={self._session_id}")
                self.sandbox_id = self._session_id

                # 记录会话创建时间
                self._session_start_time = datetime.now()
                logger.info(f"🕒 会话创建时间: {self._session_start_time.strftime('%Y-%m-%d %H:%M:%S')}")

                return

            except RuntimeError as e:
                error_msg = str(e)
                # 检查是否是资源不足的错误
                if ("create wuying resource failed" in error_msg and
                        ("code: 400" in error_msg or "code: 500" in error_msg) and
                        "All candidate AppInstanceGroups have no idle AppInstances now" in error_msg):

                    if attempt < max_retries - 1:  # 不是最后一次尝试
                        logger.warning(f"⚠️ AgentBay 资源不足，第 {attempt + 1} 次重试，等待 {retry_delay} 秒后重试...")
                        logger.warning(f"   错误详情: {error_msg}")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避策略
                    else:
                        logger.error(f"❌ AgentBay 资源不足，已达到最大重试次数 {max_retries}，放弃重试")
                        logger.error(f"   最终错误: {error_msg}")
                        raise  # 重新抛出异常
                else:
                    # 非资源不足的错误，直接抛出
                    raise
            except Exception as e:
                # 其他类型的异常，直接抛出
                logger.error(f"❌ 创建会话时发生未预期的异常: {e}", exc_info=True)
                raise

    # 重写父类文件系统read方法
    def read(self, file_path: str, offset: int = 0, limit: int = 2000):
        """读取文件内容，添加日志记录并处理 AgentBay 的 base64 编码响应。"""
        logger.debug(f"📖 [read] 读取文件: {file_path} (offset={offset}, limit={limit})")

        # 获取文件类型
        file_type = _get_file_type(file_path)
        logger.debug(f"LangChain BaseSandbox 判断该文件的类型为: {file_type}")
        path_b64 = base64.b64encode(file_path.encode("utf-8")).decode("ascii")

        # 构造命令（与 BaseSandbox.read() 相同）
        cmd = READ_COMMAND_TEMPLATE.format(
            path_b64=path_b64,
            file_type=file_type,
            offset=int(offset),
            limit=int(limit),
        )

        # 执行命令
        execute_result = self.execute(cmd)
        output = execute_result.output.rstrip()  # 根据cmd的内容，output应该时JSON格式字符串

        try:
            data = json.loads(output)
        except (json.JSONDecodeError, ValueError):
            error_msg = f"File '{file_path}': unexpected server response: {execute_result}"
            logger.error(f"❌ [read] {error_msg}")
            return ReadResult(error=error_msg)

        if not isinstance(data, dict):
            error_msg = f"File '{file_path}': unexpected server response: {execute_result}"
            logger.error(f"❌ [read] {error_msg}")
            return ReadResult(error=error_msg)

        if "error" in data:
            error_msg = f"File '{file_path}': {data['error']}"
            logger.warning(f"⚠️ [read] 发现 REAM_COMMAND_TEMPLATE 命令打印出的错误信息 {error_msg}")
            return ReadResult(error=error_msg)

        # 成功读取
        content_length = len(data["content"])
        encoding = data.get("encoding", "utf-8")
        logger.debug(f"✅ [read] 成功读取文件 '{file_path}' ({content_length} 字符, encoding={encoding})")

        return ReadResult(
            file_data=FileData(
                content=data["content"],
                encoding=encoding,
            )
        )

    def _download_recursive(self, cloud_dir: str, local_dir: Path) -> int:
        """递归下载云端目录到本地（智能过滤中间产物）。

        使用 AgentBay 原生的 download_file() API，而不是 read_file()

        Args:
            cloud_dir: 云端目录路径
            local_dir: 本地目标目录

        Returns:
            下载的文件数量
        """

        downloaded_count = 0
        skipped_count = 0

        try:
            list_result = self._session.file_system.list_directory(cloud_dir)
            if not list_result.success or not list_result.entries:
                logger.error(
                    f"❌ session.file_system.list_directory调用失败，\n 目标路径：{cloud_dir}\n错误信息:\n {list_result.error_message}")
                return 0

            # 打印第一个 entry 的所有属性，了解其结构
            if list_result.entries:
                first_entry = list_result.entries[0]
                logger.debug(f"🔍 DirectoryEntry 对象属性: {dir(first_entry)}")
                logger.debug(f"   - 类型: {type(first_entry)}")
                # 尝试访问常见属性
                for attr in ['path', 'name', 'full_path', 'file_path', 'entry_path']:
                    if hasattr(first_entry, attr):
                        logger.debug(f"   - {attr}: {getattr(first_entry, attr)}")

            for entry in list_result.entries:
                # 尝试多种可能的属性名
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

                # 统一使用 POSIX 路径格式（正斜杠）进行相对路径计算
                # 云端路径始终是 Linux 格式（正斜杠），不能用 Windows 的 Path 对象处理
                base_path = f"{self._task_context_box_mount_path_prefix}/{self._task_context_box_leaf_dir_name}"

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

                # 检查是否应该跳过
                if should_skip_path(relative_path):
                    skipped_count += 1
                    continue

                local_path = local_dir / relative_path

                if entry.is_directory:
                    # 递归下载子目录
                    local_path.mkdir(parents=True, exist_ok=True)
                    downloaded_count += self._download_recursive(cloud_path, local_dir)
                else:
                    # 使用临时文件 + download_file() API
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

                            # 使用统一的文件写入方法
                            write_content_to_file(local_path, file_content)

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

    def download_task_artifacts(self, local_download_dir: Path) -> int:
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
            return -1

        if not self._session:
            logger.error("❌ 会话不存在，跳过下载", exc_info=True)
            logger.info("会话不存在，无法下载成果物")
            return -1

        try:
            cloud_path = self.task_context_box_mount_path
            logger.info(f"📂 当前软件开发任务 云端项目空间源路径: {cloud_path}")

            # 确保本地目录存在
            local_download_dir.mkdir(parents=True, exist_ok=True)

            downloaded_count = self._download_recursive(cloud_path, local_download_dir)

            logger.info(f"✅ 下载完成: 共 {downloaded_count} 个文件")
            logger.info(f"✅ 成功下载 {downloaded_count} 个文件到: {local_download_dir}")
            return downloaded_count

        except Exception as e:
            logger.error(f"❌ 下载失败: {e}", exc_info=True)
            return -2

    def delete_session(self):
        """清理资源，删除AgentBay会话"""
        if not self._session:
            logger.info("🧹 当前会话为None，无需清理")

        if self._session:
            logger.info(f"🧹 当前会话不为None，开始手动释放会话:\n {self}")
            try:
                # 将当前会话中对存储盒内文件的更改同步到OSS上该存储盒对应位置
                self.agentbay.delete(self._session, sync_context=True)
                logger.info("✅ 会话手动释放成功")
            except Exception as e:
                logger.warning(f"❌ 手动释放会话过程中捕获异常: {e}")
            finally:
                self._session = None
                self._session_id = None
                self.sandbox_id = None

    def __str__(self):
        return (f"MySandbox(\n"
                f"      task_name={self.task_name},\n"
                f"      image_id={self.image_id},\n"
                f"      session_id={self._session_id},\n"
                f"      reuse_existing_task_context_box={self.reuse_existing},\n"
                f"      task_context_box_id={self.task_context_box_id},\n"
                f"      task_context_box_name={self.task_context_box_name},\n"
                f"      sandbox_max_running_time={self._sandbox_max_running_time_str},\n"
                f"      idle_timeout={self._idle_timeout})")

    def __enter__(self):
        """支持 with 语句：进入时返回实例"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持 with 语句：退出时自动清理资源"""
        if self._session:
            logger.warning(
                f"已经退出{self.__class__.__name__}的with块，但当前会话没有被杀死，由退出函数负责兜底删除该还活跃着的会话")
            self.delete_session()
        if exc_type:
            logger.info(f"❌ {self.__class__.__name__} 运行期间发生错误: {exc_val}", exc_info=True)
        return False  # 不吞掉异常


def download_artifacts_manually(task_name_: str):
    """手动下载task context box到本地"""
    local_download_dir = f"./warehouse/{task_name_}/manually_download/"
    logger.info(f"开始手动下载任务 {task_name_} 的成果物到 {local_download_dir}")
    with LinuxSandboxBackend(task_name=task_name_) as sandbox_:
        path = Path(local_download_dir)
        sandbox_.download_task_artifacts(path)


if __name__ == "__main__":
    setup_logging()

    # # 1. 使用 with 语句测试沙盒，确保资源自动释放
    # logger.info("\n--- 开始沙盒后端功能测试 ---")
    # with LinuxSandboxBackend(task_name="Agent test") as sandbox_test:
    #     # 测试命令执行（包含超时逻辑）
    #     # sandbox_test.execute("pwd")
    #     # sandbox_test.execute("echo 'Test command execution' > /home/wuying/test.txt && echo 'command execution success!'")
    #     # sandbox_test.execute("ls -l /home/wuying/test.txt")
    #     # sandbox_test.execute("cat /home/wuying/test.txt")
    #     sandbox_test.execute(
    #         "pip3 install streamlit -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 60 > /home/wuying/install.log 2>&1",
    #         timeout=300)
    #     sandbox_test.execute("cat /home/wuying/install.log")
    #
    #     # # 测试文件上传（包含二进制兼容逻辑）
    #     # sandbox.upload_files([("test1.txt", b"Hello, World!")])
    #
    # logger.info("---沙盒后端测试结束，资源应已自动释放 ---")

    # 2. 手动下载task context box到本地
    download_artifacts_manually("Brick breaker game")
