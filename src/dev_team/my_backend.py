# 导入必要的模块
import base64
import json
import logging
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing_extensions import override

from agentbay import (
    AgentBay,
    CommandResult,
    ContextSync,
    CreateSessionParams,
    DownloadResult,
    SessionResult,
    UploadResult,
)
from deepagents.backends.protocol import (
    ExecuteResponse,
    FileData,
    FileDownloadResponse,
    FileOperationError,
    FileUploadResponse,
    ReadResult,
)
from deepagents.backends.sandbox import BaseSandbox
from deepagents.backends.utils import _get_file_type

from src.config.settings import settings
from src.dev_team.team_config import (
    AGENTBAY_IMAGE_ID,
    CONTEXT_MOUNT_PATH_PREFIX_OF_NEW_TASK_CONTEXT_BOX,
)
from src.utils.common import (
    map_agentbay_error_to_file_operation_error,
    process_command_parts,
    should_skip_path,
    to_snake_case,
    write_content_to_file,
)

logger = logging.getLogger(__name__)


class SandboxSessionExpiredError(RuntimeError):
    """沙盒会话过期异常

    当 AgentBay 沙盒会话达到最长运行时间限制时抛出。
    此异常在抛出前已完成成果物下载和会话清理。
    """

    def __init__(
        self,
        message: str,
        session_id: str | None = None,
        elapsed_minutes: float | None = None,
    ):
        super().__init__(message)
        self.session_id = session_id
        self.elapsed_minutes = elapsed_minutes


class SandboxSessionCreateError(RuntimeError):
    """沙盒会话创建异常

    当为某个thread id而多次尝试创建 AgentBay 沙盒会话失败时抛出。
    """

    def __init__(self, message: str, thread_id: str | None = None):
        super().__init__(message)
        self.thread_id = thread_id


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


# 该类通过无影agentbay的session实现sandbox backend
# 目前仅仅支持linux session，因为agentbay仅linux_latest镜像预装了python命令
# BaseSandbox通过调用self.execute方法执行python3 -c "python脚本"来提供文件系统接口
class LinuxSandboxBackend(BaseSandbox):
    """基于无影AgentBay实现的云沙盒后端。 注意！沙盒会话最长运行时间需要在镜像中配置，的确为linux_latest配置了2h最长会话运行时间。

    该类通过无影AgentBay的session提供真正的云端沙盒环境，
    所有文件操作和命令执行都在云端进行，而非本地。
    """

    def __init__(
        self,
        *,
        task_name: str = "",
        task_context_box_name: str = "",
        local_dir_for_task_products: Path,
        image_id: str = AGENTBAY_IMAGE_ID,
        api_key: str = settings.WUYING_AGENTBAY_API_KEY,
        idle_timeout: int = 30 * 60,
    ):
        """初始化LinuxSandboxBackend的静态资源。

        Args:
            task_name: 当前软件开发任务的名称，用于创建持久化的存储盒，持久化保存智能体的文件写入操作（允许智能体可以访问该沙盒）。因此可以后续下载当前软件的成果物文件到本地
            api_key: AgentBay API密钥
            image_id: 沙盒镜像ID
            idle_timeout: 云端会话空闲自动释放时间（秒），默认1h（60*60秒），太短的话，很有可能在等待智能体输出大块内容（这需要llm耗费10min左右来输出3.8万个字符）之前，该会话就会被自动释放了！！！
            :param local_dir_for_task_products:
        """
        self.task_name = task_name

        if not task_context_box_name:
            raise ValueError("创建Sandbox 实例必须传入一个任务上下文盒子名称")

        self.task_context_box_name = task_context_box_name
        self.task_context_box_id = None  # 存本次开发时所用的任务上下文盒子的ID

        self.local_dir_for_task_products = local_dir_for_task_products
        self.agentbay = AgentBay(api_key=api_key)
        self.context_service = self.agentbay.context
        self.image_id = image_id
        self.sandbox_type = "linux"

        self._idle_timeout = idle_timeout
        self._sandbox_max_running_time_str = (
            "3 hours"  # 当前镜像的最长持续运行时间（字符串描述）
        )
        self._sandbox_max_running_time_seconds = 3 * 60 * 60  # 3小时转换为秒
        self.time_for_products_download = (
            10  # 在达到当前镜像的最长持续运行时间的10 分钟前主动提前释放沙盒会话
        )

        # 确定当前 task的context box 在sandbox中的挂载路径
        self._task_context_box_mount_path_prefix = (
            CONTEXT_MOUNT_PATH_PREFIX_OF_NEW_TASK_CONTEXT_BOX[f"{self.sandbox_type}"]
        )
        self._task_context_box_leaf_dir_name = (
            to_snake_case(task_name) if task_name else ""
        )
        self.task_context_box_mount_path = f"{self._task_context_box_mount_path_prefix}/{self._task_context_box_leaf_dir_name}"
        logger.info(
            f"当前Task Context Box 的云端挂载路径为{self.task_context_box_mount_path}\n"
            f"智能体必须在该路径下进行开发、文件写入，否则任务成果物无法下载到本地！"
        )

        my_context_syncs = self._get_context_syncs()

        for i, ctx_sync in enumerate(my_context_syncs):
            logger.debug(f"    [{i}] 存储盒 ID: {ctx_sync.context_id}")

        params = CreateSessionParams(
            image_id=self.image_id,
            context_syncs=my_context_syncs,
            idle_release_timeout=self._idle_timeout,
        )

        # 开始创建会话
        try:
            max_retries = 25
            retry_delay = 5  # 初始重试延迟5秒
            for attempt in range(max_retries):
                # 创建会话，该会话具备持久化数据
                result: SessionResult = self.agentbay.create(params)

                if result.success:
                    # 打印会话成功创建的信息
                    self.session = result.session
                    self._session_id = self.session.session_id
                    self.sandbox_id = self._session_id

                    # 记录会话创建时间
                    self._session_start_time = datetime.now()
                    logger.info(
                        f"\n"
                        f"✅ AgentBay 会话创建成功, SessionId={self._session_id}\n"
                        f"🕒 会话创建时间: {self._session_start_time.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    break
                else:
                    # 判断是否可重试
                    error_msg = getattr(result, "error_message", "未知错误")
                    # 检查是否是资源不足的错误
                    if (
                        "All candidate AppInstanceGroups have no idle AppInstances now, please retry later"
                        in error_msg
                    ):
                        if attempt < max_retries - 1:  # 不是最后一次尝试
                            logger.warning(
                                f"⚠️ AgentBay 资源不足，第 {attempt + 1} 次重试，等待 {retry_delay} 秒后重试...\n"
                                f"错误详情:\n{error_msg}"
                            )
                            time.sleep(retry_delay)
                            retry_delay *= 2  # 指数退避策略
                            continue
                        else:
                            logger.error(
                                f"❌ AgentBay 资源不足，已达到最大重试次数 {max_retries}，放弃重试"
                            )
                            raise SandboxSessionCreateError(
                                f"为线程 {self.thread_id} 多次尝试创建 AgentBay 会话失败，资源不足",
                                thread_id=self.thread_id,
                            )
                    else:
                        # 非资源不足的错误，直接抛出
                        raise RuntimeError(
                            f"尝试创建 AgentBay 会话时发生未预期的异常: {error_msg}"
                        )

        except SandboxSessionCreateError as e:
            # 为线程创建会话失败，直接抛出异常
            raise e

        except Exception as e:
            # 其他类型的异常，直接抛出
            logger.error(f"❌ 创建会话时发生未预期的异常: {e}", exc_info=True)
            raise

        logger.info(f"{self.__class__.__name__}  实例初始化完成")

    def get_existing_task_context(self):
        """获取或创建当前任务的 Context。"""
        res = self.context_service.get(self.task_context_box_name, create=False)
        if not res.success:
            logger.error(
                f"❌ 获取任务存储盒失败: {res.error_message}, 存储盒名: {self.task_context_box_name}"
            )
            return None
        logger.info(
            f"✅ 本次软件开发所用任务存储盒获取成功: {res.context.id}, 存储盒名: {self.task_context_box_name}"
        )  # type: ignore

        return res.context

    def _get_task_context_sync(self) -> ContextSync:
        """获取当前任务的 Context同步配置。"""
        task_context_1 = self.get_existing_task_context()
        self.task_context_box_id = task_context_1.id  # type: ignore
        return ContextSync.new(
            context_id=task_context_1.id,  # type: ignore
            path=self.task_context_box_mount_path,
        )

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

    @property
    def id(self) -> str:
        """Unique identifier for the sandbox backend."""
        if self.session is None:
            raise RuntimeError("Session not initialized")
        return self.session.session_id

    def check_session_remaining_time(self):
        """检查会话剩余时间，如果接近最大运行时间则提前清理并抛出异常。

        ⚠️ 在通过当前对象的_session属性调用AgentBay MCP 工具前必须调用此方法，以防止会话过期导致操作失败。

        Raises:
            SandboxSessionExpiredError: 当会话剩余时间不足10分钟时抛出
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
            raise SandboxSessionExpiredError(
                f"⚠️ 沙盒会话已被主动提前断开，并且距离断开已经过了一段时间！\n"
                f"   - 最大运行时间: {self._sandbox_max_running_time_str} ({self._sandbox_max_running_time_seconds}秒)\n"
                f"   - 已运行时间: {elapsed_seconds / 60:.1f} 分钟\n"
                f"   - 会话已经过期了{(-remaining_seconds) / 60} 分钟 {(-remaining_seconds) % 60} 秒\n",
                session_id=self._session_id,
                elapsed_minutes=elapsed_seconds / 60,
            )

        # 如果剩余时间不足10分钟=10*60秒，提前清理并抛出异常
        time_threshold_seconds = self.time_for_products_download * 60
        if 0 <= remaining_seconds <= time_threshold_seconds:
            remaining_minutes = remaining_seconds / 60

            logger.debug(
                f"🕒 会话运行状态: 已运行 {elapsed_seconds / 60:.1f} 分钟, 剩余 {remaining_minutes:.1f} 分钟"
            )
            if self.session is not None:
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
                    self.download_task_artifacts(self.local_dir_for_task_products)
                    self.delete_session()
                    logger.info(
                        "✅ 为避免会话突然过期导致沙盒软件成果物无法及时下载到本地，已主动清理成功即将过期的会话"
                    )
                except Exception as e:
                    logger.warning(
                        f"⚠️ 为避免会话突然过期导致沙盒软件成果物无法及时下载到本地，主动清理会话时出现异常: {e}"
                    )

                else:
                    raise SandboxSessionExpiredError(
                        error_msg,
                        session_id=self._session_id,
                        elapsed_minutes=elapsed_seconds / 60,
                    )
            elif self._session_id is None:
                # 已经释放掉，但是还有工具调用正在执行，则抛出异常给ToolRetryMiddleware的钩子函数
                raise SandboxSessionExpiredError(
                    f"⚠️ 沙盒会话已被主动提前断开！\n"
                    f"   - 最大运行时间: {self._sandbox_max_running_time_str} ({self._sandbox_max_running_time_seconds}秒)\n"
                    f"   - 已运行时间: {elapsed_seconds / 60:.1f} 分钟\n",
                    session_id=self._session_id,
                    elapsed_minutes=elapsed_seconds / 60,
                )

    @property
    def sandbox_expired(self) -> bool:
        """判断沙盒会话是否已过期

        Returns:
            True: 会话已过期或已被清理
            False: 会话正常运行中
        """
        if self._session_id is None or self.session is None:
            return True

        elapsed_seconds = (datetime.now() - self._session_start_time).total_seconds()
        return elapsed_seconds >= self._sandbox_max_running_time_seconds

    @override
    def execute(
        self,
        command: str,
        *,
        timeout: int | None = None,
    ) -> ExecuteResponse:
        """Execute a command in the sandbox and return ExecuteResponse.

        确保云端 Python 脚本使用 UTF-8 编码执行。
        BaseSandbox提供的ls、read、edit、grep、glob方法（这些方法支撑了LangChain文件系统中间件的ls、read、edit、grep、glob工具）的实现都是基于该方法。
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
        if "python" in command.lower():

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
                if command.strip().lower().startswith("python"):
                    command = f"set PYTHONUTF8=1 && {command}"
                    logger.debug(
                        f"🔧 已为 Python 命令添加 UTF-8 编码环境变量 (Windows)"
                    )

        # agentbay execute工具默认的超时时间是50秒
        command_result: CommandResult = self.session.command.execute_command(
            command, timeout_ms=timeout_ms
        )

        output = command_result.output  # shell命令执行后的stdout+stderr
        exit_code = command_result.exit_code

        if not command_result.success:
            error_msg = command_result.error_message
            output = error_msg
            if r'"system_error":"Command timed out"' in error_msg:
                output = f"shell命令执行超时（timeout={timeout}），请为本次shell命令（{command}）设置更大的timeout后重试！"

            if "HTTP request failed with code: 404" in error_msg:
                # 表明当前当前沙盒Session已被释放。
                output = f"当前沙盒会话已被释放（删除），请停止开发并请示人类下一步行动"

            logger.error(
                f"❌ session.command.execute_command 执行失败:\n"
                f"失败的shell命令：\n"
                f"{command}\n"
                f"超时时间设置：{timeout} 秒\n"
                f"智能体所见的shell工具执行结果：\n"
                f"{output}\n"
                f"API返回的错误消息：\n"
                f"{error_msg}\n"
            )
            return ExecuteResponse(output=output, exit_code=exit_code, truncated=False)

        logger.debug(
            f"✅ session.command.execute_command 执行成功\n"
            f"执行的命令：\n"
            f"{command}\n"
            f"超时时间设置：{timeout} 秒\n"
            f"命令执行结果：\n"
            f"{output}"
        )

        return ExecuteResponse(output=output, exit_code=exit_code, truncated=False)

    @override
    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """Upload multiple files to the sandbox.

        使用 AgentBay 原生的 upload_file() API，而不是 write_file()
        通过临时文件桥接 bytes → 本地文件 → 云端

        LangChain BaseSandbox的write、edit方法（这两个方法支撑了LangChain文件系统中间件的write file工具和edit file工具）底层会调用该方法。
        """
        # 在下载文件前检查会话剩余时间
        self.check_session_remaining_time()

        responses = []
        for file_path, content in files:
            temp_file_path = None
            logger.debug(f"📤 正在上传文件: {file_path} ({len(content)} 字节)")

            # 确保父目录存在
            parent_dir = str(Path(file_path).parent)
            if parent_dir and parent_dir != ".":
                self.session.file_system.create_directory(parent_dir)

            # 创建临时文件，使用 AgentBay 原生 upload_file API
            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False, suffix=".tmp"
            ) as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name

            # 使用 AgentBay 原生 upload_file API（支持二进制文件）
            upload_result: UploadResult = self.session.file_system.upload_file(
                local_path=temp_file_path, remote_path=file_path
            )

            if upload_result.success:
                logger.debug(f"✅ 上传成功: {file_path}")
                responses.append(FileUploadResponse(path=file_path))
            else:
                error_msg = getattr(upload_result, "error_message", "未知错误")
                logger.error(
                    f"❌ session.file_system.upload_file 执行失败:\n目标文件路径 {file_path},\n错误: {error_msg}"
                )
                # 清理临时文件
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                    except Exception as e:
                        logger.warning(
                            f"⚠️ Failed to clean up temp file: {temp_file_path}, Error: {e}"
                        )

                # 尝试将 AgentBay 错误映射到标准 FileOperationError
                standardized_error = map_agentbay_error_to_file_operation_error(
                    error_msg
                )
                if not isinstance(standardized_error, FileOperationError):
                    standardized_error = error_msg
                responses.append(
                    FileUploadResponse(path=file_path, error=standardized_error)
                )
        return responses

    @override
    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """Download multiple files from the sandbox.

        优化：使用 AgentBay 原生的 download_file() API，而不是 read_file()
        通过临时文件桥接 云端 → 本地文件 → bytes

        LangChain BaseSandbox似乎没有调用该方法的，不确定LangChain 文件系统中间件是否会调用该方法。。
        """
        # 在下载文件前检查会话剩余时间
        self.check_session_remaining_time()

        responses = []
        for file_path in paths:
            temp_file_path = None
            logger.debug(f"📥 正在下载文件: {file_path}")

            # 关键优化：创建临时文件，使用 AgentBay 原生 download_file API
            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False, suffix=".tmp"
            ) as temp_file:
                temp_file_path = temp_file.name

            # 使用 AgentBay 原生 download_file API（支持二进制文件）
            download_result: DownloadResult = self.session.file_system.download_file(
                remote_path=file_path, local_path=temp_file_path
            )

            if download_result.success:
                # 读取临时文件为 bytes
                with open(temp_file_path, "rb") as f:
                    content = f.read()

                logger.debug(f"✅ 下载成功: {file_path} ({len(content)} 字节)")
                responses.append(FileDownloadResponse(path=file_path, content=content))
            else:
                error_msg = getattr(download_result, "error_message", "未知错误")
                logger.error(
                    f"❌ session.file_system.download_file 执行失败:\n目标文件路径 {file_path},\n错误: {error_msg}"
                )
                # 清理临时文件
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                    except Exception as e:
                        logger.warning(
                            f"⚠️ Failed to clean up temp file: {temp_file_path}, Error: {e}"
                        )

                # 尝试将 AgentBay 错误映射到标准 FileOperationError
                standardized_error = map_agentbay_error_to_file_operation_error(
                    error_msg
                )
                if not isinstance(standardized_error, FileOperationError):
                    standardized_error = error_msg
                responses.append(
                    FileDownloadResponse(path=file_path, error=standardized_error)
                )

        return responses

    # 重写父类文件系统read方法
    @override
    def read(self, file_path: str, offset: int = 0, limit: int = 2000):
        """读取文件内容，添加日志记录并处理 AgentBay 的 base64 编码响应。"""
        logger.debug(
            f"📖 [read] 读取文件: {file_path} (offset={offset}, limit={limit})"
        )

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
        output = (
            execute_result.output.rstrip()
        )  # 根据cmd的内容，output应该时JSON格式字符串

        try:
            data = json.loads(output)
        except (json.JSONDecodeError, ValueError):
            error_msg = (
                f"File '{file_path}': unexpected server response: {execute_result}"
            )
            logger.error(f"❌ [read] {error_msg}")
            return ReadResult(error=error_msg)

        if not isinstance(data, dict):
            error_msg = (
                f"File '{file_path}': unexpected server response: {execute_result}"
            )
            logger.error(f"❌ [read] {error_msg}")
            return ReadResult(error=error_msg)

        if "error" in data:
            error_msg = f"File '{file_path}': {data['error']}"
            logger.warning(
                f"⚠️ [read] 发现 REAM_COMMAND_TEMPLATE 命令打印出的错误信息 {error_msg}"
            )
            return ReadResult(error=error_msg)

        # 成功读取
        content_length = len(data["content"])
        encoding = data.get("encoding", "utf-8")
        logger.debug(
            f"✅ [read] 成功读取文件 '{file_path}' ({content_length} 字符, encoding={encoding})"
        )

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
            list_result = self.session.file_system.list_directory(cloud_dir)
            if not list_result.success:
                logger.error(
                    f"❌ session.file_system.list_directory调用失败，\n 目标路径：{cloud_dir}\n错误信息:\n {list_result.error_message}"
                )
                return 0

            if not list_result.entries:
                logger.warning(
                    f"⚠️ session.file_system.list_directory调用发现目录为空，\n目标路径：{cloud_dir}\n"
                )
                return 0

            # 打印第一个 entry 的所有属性，了解其结构
            if list_result.entries:
                first_entry = list_result.entries[0]
                logger.debug(f"🔍 DirectoryEntry 对象属性: {dir(first_entry)}")
                logger.debug(f"   - 类型: {type(first_entry)}")
                # 尝试访问常见属性
                for attr in ["path", "name", "full_path", "file_path", "entry_path"]:
                    if hasattr(first_entry, attr):
                        logger.debug(f"   - {attr}: {getattr(first_entry, attr)}")

            for entry in list_result.entries:
                # 尝试多种可能的属性名
                cloud_path = None
                for attr_name in ["path", "full_path", "file_path", "entry_path"]:
                    if hasattr(entry, attr_name):
                        cloud_path = getattr(entry, attr_name)
                        break

                # 如果找不到完整路径属性，但有 name 属性，则手动拼接完整路径
                if cloud_path is None and hasattr(entry, "name"):
                    # name 只是文件名，需要与父目录拼接
                    cloud_path = f"{cloud_dir}/{entry.name}"
                    logger.debug(f"   📝 使用 name 属性拼接路径: {cloud_path}")

                if cloud_path is None:
                    logger.error(
                        f"❌ 无法找到 entry 的路径属性，可用属性: {dir(entry)}",
                        exc_info=True,
                    )
                    continue

                # 统一使用 POSIX 路径格式（正斜杠）进行相对路径计算
                # 云端路径始终是 Linux 格式（正斜杠），不能用 Windows 的 Path 对象处理
                base_path = f"{self._task_context_box_mount_path_prefix}/{self._task_context_box_leaf_dir_name}"

                # 使用纯字符串操作计算相对路径，避免跨平台路径格式问题
                if cloud_path.startswith(base_path + "/"):
                    relative_path_str = cloud_path[len(base_path) + 1 :]
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
                        with tempfile.NamedTemporaryFile(
                            mode="wb", delete=False, suffix=".tmp"
                        ) as temp_file:
                            temp_file_path = temp_file.name

                        # 使用原生 download_file API
                        download_result = self.session.file_system.download_file(
                            remote_path=cloud_path, local_path=temp_file_path
                        )

                        if download_result.success:
                            # 读取临时文件并写入目标位置
                            with open(temp_file_path, "rb") as f:
                                file_content = f.read()

                            # 使用统一的文件写入方法
                            write_content_to_file(local_path, file_content)

                            downloaded_count += 1
                            logger.debug(f"✅ 已下载: {cloud_path} -> {local_path}")
                        else:
                            error_msg = getattr(download_result, "error", "未知错误")
                            logger.warning(
                                f"⚠️ 下载失败: {cloud_path}, 错误: {error_msg}"
                            )

                    except Exception as e:
                        logger.error(
                            f"❌ 下载异常: {cloud_path}, 错误: {e}", exc_info=True
                        )
                    finally:
                        # 清理临时文件
                        if temp_file_path and os.path.exists(temp_file_path):
                            try:
                                os.unlink(temp_file_path)
                            except Exception as e:
                                logger.warning(
                                    f"⚠️ 清理临时文件失败: {temp_file_path}, 错误: {e}"
                                )

        except Exception as e:
            logger.info(f"⚠️ 递归下载出错: {e}")

        if skipped_count > 0:
            logger.info(f"   ℹ️  已跳过 {skipped_count} 个中间产物/缓存文件")

        return downloaded_count

    def download_task_artifacts(self, local_download_dir: Path):
        """下载当前任务的所有成果物到本地目录。

        Args:
            local_download_dir: 本地下载目标目录

        Returns:
            bool: 是否成功下载
        """
        logger.info(
            f"📥 下载任务成果物, 任务存储盒子名={self.task_context_box_name}, 本地目标目录={local_download_dir}"
        )

        if not self.task_context_box_name:
            logger.warning("⚠️ 未关联任务存储盒，跳过下载")
            return

        if not self.session:
            logger.warning(
                "⚠️ 会话为None，可能是沙盒会话超过预设最大持续时间而被自动释放，无法再次下载成果物，跳过下载"
            )
            return

        try:
            cloud_path = self.task_context_box_mount_path
            logger.info(f"📂 当前软件开发任务 云端项目空间源路径: {cloud_path}")

            # 确保本地目录存在
            local_download_dir.mkdir(parents=True, exist_ok=True)

            downloaded_count = self._download_recursive(cloud_path, local_download_dir)

            logger.info(f"✅ 下载完成: 共 {downloaded_count} 个文件")
            logger.info(
                f"✅ 成功下载 {downloaded_count} 个文件到: {local_download_dir}"
            )

        except Exception as e:
            logger.error(f"❌ 下载失败: {e}", exc_info=True)
            return

    def delete_session(self):
        """清理资源，删除AgentBay会话"""
        if not self.session:
            logger.info("🧹 当前会话为None，无需清理")

        if self.session:
            logger.info(f"🧹 当前会话不为None，开始手动释放会话:\n {self}")
            try:
                # 将当前会话中对存储盒内文件的更改同步到OSS上该存储盒对应位置
                self.agentbay.delete(self.session, sync_context=True)
                logger.info("✅ 会话手动释放成功")
            except Exception as e:
                logger.warning(f"❌ 手动释放会话过程中捕获异常: {e}")
            finally:
                self.session = None
                self._session_id = None
                self.sandbox_id = None

    def __str__(self):
        return (
            f"MySandbox(\n"
            f"      task_context_box_name={self.task_context_box_name},\n"
            f"      task_context_box_id={self.task_context_box_id},\n"
            f"      image_id={self.image_id},\n"
            f"      session_id={self._session_id},\n"
            f"      sandbox_max_running_time={self._sandbox_max_running_time_str},\n"
            f"      idle_timeout={self._idle_timeout})"
        )

    def __enter__(self):
        """支持 with 语句：进入时返回实例"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持 with 语句：退出时自动清理资源"""
        if self.session:
            logger.warning(
                f"已经退出{self.__class__.__name__}的with块，但当前会话没有被杀死，由退出函数负责兜底删除该还活跃着的会话"
            )
            self.delete_session()
        if exc_type:
            logger.info(
                f"❌ {self.__class__.__name__} 运行期间发生错误: {exc_val}",
                exc_info=True,
            )
        return False  # 不吞掉异常
