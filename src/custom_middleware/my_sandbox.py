from pathlib import Path

from agentbay import AgentBay, CreateSessionParams, SessionResult, ContextSync, Session
from deepagents.backends.protocol import ExecuteResponse, FileDownloadResponse, FileUploadResponse
from deepagents.backends.sandbox import BaseSandbox
from typing import Any

from src.config.settings import settings
from src.paths import DEV_TEAM_SKILLS_PATH, LOCAL_AGENT_WORKSPACE


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
    files = []

    if include_patterns:
        # 只收集指定子文件夹中的文件
        for pattern in include_patterns:
            target_dir = local_dir / pattern
            if target_dir.exists() and target_dir.is_dir():
                for file_path in target_dir.rglob('*'):
                    if file_path.is_file():
                        relative_path = file_path.relative_to(local_dir)
                        rel_path_str = relative_path.as_posix()
                        files.append((file_path, rel_path_str))
            else:
                print(f"⚠️  警告: 指定的文件夹不存在: {target_dir}")
    else:
        # 收集所有文件（原有行为）
        for file_path in local_dir.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(local_dir)
                rel_path_str = relative_path.as_posix()
                files.append((file_path, rel_path_str))

    return files


def _build_cloud_file_index(agent_bay: AgentBay, context_id: str) -> dict[str, Any]:
    """构建云端文件的索引字典，用于快速查找。
    
    Returns:
        字典，键为文件相对路径，值为文件元数据对象
    """
    cloud_files = {}
    list_result = agent_bay.context.list_files(
        context_id=context_id,
        parent_folder_path="/",
        page_number=1,
        page_size=1000
    )

    if list_result.success:
        for entry in list_result.entries:
            # entry.file_path 已经是相对于根目录的路径
            cloud_files[entry.file_path] = entry

    return cloud_files


def _upload_files_to_session(
        session: Session,
        files_to_sync: list[tuple[Path, str]],
        mount_path: str
) -> int:
    """将文件列表上传到会话中的指定挂载路径。
    
    Args:
        session: AgentBay 会话对象
        files_to_sync: 待同步文件列表 [(本地路径, 相对路径), ...]
        mount_path: 云端挂载路径
    
    Returns:
        成功上传的文件数量
    """
    synced_count = 0

    for local_file, rel_path in files_to_sync:
        # 拼接完整的云端路径
        target_path = str(Path(mount_path) / rel_path)

        try:
            # 读取本地文件内容
            content_bytes = local_file.read_bytes()

            # 确保父目录存在
            parent_dir = str(Path(target_path).parent)
            if parent_dir and parent_dir != '.':
                session.file_system.create_directory(parent_dir)

            # 转换为字符串并上传（write_file 是幂等操作）
            content_str = content_bytes.decode('utf-8', errors='replace')
            result = session.file_system.write_file(target_path, content_str)

            if result.success:
                synced_count += 1
            else:
                print(f"   ✗ 上传失败 {rel_path}: {result.error_message}")

        except Exception as e:
            print(f"   ✗ 同步异常 {rel_path}: {e}")

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
                        如果为 None，则同步整个 local_dir
    
    Returns:
        bool: 是否成功完成同步
    """
    print(f"🚀 开始同步: {local_dir} -> Context '{context_name}'")

    if include_folders:
        print(f"📂 将同步以下文件夹: {', '.join(include_folders)}")
    else:
        print(f"📂 将同步整个目录")

    # 验证本地目录存在
    local_path = Path(local_dir)
    if not local_path.exists():
        print(f"❌ 错误: 本地目录不存在: {local_dir}")
        return False

    try:
        # ========== 第1步：初始化 AgentBay 并获取 Context ==========
        agent_bay = AgentBay(api_key=api_key)

        context_result = agent_bay.context.get(context_name, create=True)
        if not context_result.success or not context_result.context:
            raise RuntimeError(f"Failed to get/create context: {context_result.error_message}")

        context = context_result.context
        print(f"✅ Context ID: {context.id}")

        # ========== 第2步：收集本地文件 ==========
        local_files = _collect_local_files(local_path, include_folders)

        if not local_files:
            print(f"✨ 未发现需要同步的文件。")
            return True

        print(f"📁 发现 {len(local_files)} 个待同步文件")

        # ========== 第3步：创建会话并上传文件 ==========
        print(f"🔗 创建临时会话进行文件同步...")
        context_sync = ContextSync.new(context.id, mount_path)
        params = CreateSessionParams(image_id=image_id, context_syncs=[context_sync])
        session_result = agent_bay.create(params)

        if not session_result.success or not session_result.session:
            raise RuntimeError(f"Failed to create session: {session_result.error_message}")

        session = session_result.session
        print(f"✅ 会话创建成功: {session.session_id}")

        # 上传所有文件
        synced_count = _upload_files_to_session(session, local_files, mount_path)

        # ========== 第4步：清理会话并同步到 OSS ==========
        print(f"💾 正在同步数据到OSS...")
        agent_bay.delete(session, sync_context=True)  # sync_context=True 确保数据写入 OSS

        print(f"✅ 同步完成！共处理 {synced_count}/{len(local_files)} 个文件。")
        return True

    except Exception as e:
        print(f"❌ 同步过程出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def setup_team_skills(
        api_key: str = settings.WUYING_AGENTBAY_API_KEY,
        skills_source_dir=DEV_TEAM_SKILLS_PATH
):
    """将团队技能文件夹同步到OSS上的context对象中。
    
    只同步 skills 文件夹，不包含其他内容。
    """
    return sync_local_to_context(
        api_key=api_key,
        context_name="team-skills",
        local_dir=skills_source_dir,
        mount_path="/tmp/persistent/team_skills",
        include_folders=None  # skills 本身就是目标文件夹，同步全部内容
    )


CONTEXT_NAME_OF_AGENT_WORKSPACE = "agent-workspace"  # 该存储盒的名称
CONTEXT_MOUNT_PATH_OF_AGENT_WORKSPACE = "/tmp/persistent/agent_workspace"  # 该存储盒在会话环境中挂载到的目录

LEADER_SKILL_PATH = "/tmp/persistent/agent_workspace/skills/leader"
ENGINEER_SKILL_PATH = "/tmp/persistent/agent_workspace/skills/engineer"
QA_ENGINEER_SKILL_PATH = "/tmp/persistent/agent_workspace/skills/QA_engineer"


def init_remote_agent_workspace(
        api_key: str = settings.WUYING_AGENTBAY_API_KEY,
        workspace_dir=LOCAL_AGENT_WORKSPACE,
        include_folders: list[str] | None = None
):
    """将本地智能体开发团队的工作空间上传到云端存储盒。
    
    Args:
        api_key: AgentBay API密钥
        workspace_dir: 本地工作空间路径
        include_folders: 要同步的子文件夹列表，如 ['memory', 'skills']；如果明确传入 None，则同步整个工作空间
    
    示例:
        # 只同步 memory 和 skills 文件夹
        init_remote_agent_workspace(include_folders=['memory', 'skills'])
        
        # 同步整个工作空间
        init_remote_agent_workspace()
    """
    return sync_local_to_context(
        api_key=api_key,
        context_name=CONTEXT_NAME_OF_AGENT_WORKSPACE,
        local_dir=workspace_dir,
        mount_path=CONTEXT_MOUNT_PATH_OF_AGENT_WORKSPACE,
        include_folders=include_folders
    )


# 该类通过无影agentbay的session实现sandbox backend
class MySandbox(BaseSandbox):
    """基于无影AgentBay实现的云沙盒后端。

        该类通过无影AgentBay的session提供真正的云端沙盒环境，
        所有文件操作和命令执行都在云端进行，而非本地。
        """

    def __init__(self, api_key: str = settings.WUYING_AGENTBAY_API_KEY, image_id: str = "linux_latest",
                 idle_timeout: int = 300):
        """初始化MySandbox。

        Args:
            api_key: AgentBay API密钥
            image_id: 沙盒镜像ID
            idle_timeout: 云端会话空闲自动释放时间（秒），默认300秒（5分钟）
        """
        self._agent_bay = AgentBay(api_key=api_key)
        self._image_id = image_id
        self._idle_timeout = idle_timeout
        self._session: Session = None
        # 注意：这里不再立即调用 _initialize_session()，而是等到第一次使用时再创建

    def _initialize_session(self):
        """创建AgentBay会话并挂载持久化上下文"""
        # 1. 获取或创建持久化上下文
        context_result = self._agent_bay.context.get(CONTEXT_NAME_OF_AGENT_WORKSPACE, create=True)
        if not context_result.success or not context_result.context:
            raise RuntimeError(f"Failed to initialize context: {context_result.error_message}")

        context = context_result.context
        context_sync = ContextSync.new(context.id, CONTEXT_MOUNT_PATH_OF_AGENT_WORKSPACE)

        # Create session with persistent data and idle timeout
        params = CreateSessionParams(
            image_id=self._image_id,
            context_syncs=[context_sync],
            idle_release_timeout=self._idle_timeout  # 关键：设置云端空闲超时
        )

        result: SessionResult = self._agent_bay.create(params)

        if not result.success or result.session is None:
            raise RuntimeError(f"Failed to create AgentBay session: {result.error_message}")

        self._session = result.session
        print(f"🚀 [MySandbox] 云端会话已启动 (ID: {self._session.session_id}, 空闲超时: {self._idle_timeout}s)")

    def _is_session_alive(self) -> bool:
        """检查当前会话是否仍然有效"""
        if self._session is None:
            return False
        try:
            # 尝试获取会话状态来验证连接
            _ = self._session.session_id
            return True
        except Exception:
            return False

    def _ensure_session(self):
        """确保会话已创建且有效（支持断线重连）"""
        if not self._is_session_alive():
            print("⚠️ [MySandbox] 检测到会话已失效或不存在，正在重新建立连接...")
            self._session = None  # 清理无效引用
            self._initialize_session()

    def execute(
            self,
            command: str,
            *,
            timeout: int | None = None,
    ) -> ExecuteResponse:
        """Execute a command in the sandbox and return ExecuteResponse."""
        self._ensure_session()  # 确保会话存在
        try:
            # Convert timeout from seconds (protocol) to milliseconds (AgentBay)
            timeout_ms = int(timeout * 1000) if timeout is not None else None
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
            return ExecuteResponse(
                output=f"Error executing command: {str(e)}",
                exit_code=1,
                truncated=False
            )

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """Upload multiple files to the sandbox."""
        self._ensure_session()  # 确保会话存在
        responses = []

        for file_path, content in files:
            try:
                # Ensure parent directory exists using pathlib
                parent_dir = str(Path(file_path).parent)
                if parent_dir and parent_dir != '.':
                    self._session.file_system.create_directory(parent_dir)

                # Handle content conversion based on type
                try:
                    # Try to decode as UTF-8 text first
                    content_str = content.decode('utf-8')
                    write_result = self._session.file_system.write_file(file_path, content_str)
                except UnicodeDecodeError:
                    # For binary files, use base64 encoding via command line
                    import base64
                    b64_content = base64.b64encode(content).decode('ascii')
                    tmp_path = f"/tmp/.deepagents_upload_{Path(file_path).name}.b64"

                    # Write base64 string
                    self._session.file_system.write_file(tmp_path, b64_content)
                    # Decode it into the target file using shell command
                    cmd_result = self._session.command.execute_command(
                        f"base64 -d {tmp_path} > {file_path} && rm {tmp_path}")

                    if cmd_result.exit_code == 0:
                        responses.append(FileUploadResponse(path=file_path))
                    else:
                        responses.append(FileUploadResponse(
                            path=file_path,
                            error=f"Binary upload failed: {cmd_result.output}"
                        ))
                    continue

                if write_result.success:
                    responses.append(FileUploadResponse(path=file_path))
                else:
                    error_msg = getattr(write_result, 'error_message', 'Unknown error')
                    responses.append(FileUploadResponse(
                        path=file_path,
                        error=error_msg
                    ))
            except Exception as e:
                responses.append(FileUploadResponse(
                    path=file_path,
                    error=str(e)
                ))

        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """Download multiple files from the sandbox."""
        self._ensure_session()  # 确保会话存在
        responses = []

        for file_path in paths:
            try:
                read_result = self._session.file_system.read_file(file_path)

                if read_result.success:
                    # Convert string content back to bytes (DeepAgents protocol requires bytes)
                    content_str = getattr(read_result, 'content', '')
                    content = content_str.encode('utf-8')
                    responses.append(FileDownloadResponse(
                        path=file_path,
                        content=content
                    ))
                else:
                    error_msg = getattr(read_result, 'error_message', 'Unknown error')
                    responses.append(FileDownloadResponse(
                        path=file_path,
                        error=error_msg
                    ))
            except Exception as e:
                responses.append(FileDownloadResponse(
                    path=file_path,
                    error=str(e)
                ))

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
            print(f"⚠️ 沙盒运行期间发生错误: {exc_val}")
        return False  # 不吞掉异常

    def cleanup(self):
        """清理资源，删除AgentBay会话"""
        if self._session:
            try:
                print(f"🧹 正在释放云端会话资源: {self._session.session_id}...")
                self._agent_bay.delete(self._session)
                print(f"✅ 会话资源已成功释放")
            except Exception as e:
                print(f"⚠️ 释放会话资源时警告: {e}")
            finally:
                self._session = None

    def __del__(self):
        """析构函数：作为最后一道防线确保资源被清理"""
        self.cleanup()


if __name__ == "__main__":
    # # 1. 先设置技能（确保 OSS 上有东西）
    # setup_team_skills()

    # # 2. 使用 with 语句测试沙盒，确保资源自动释放
    # print("\n--- 开始沙盒功能测试 ---")
    # with MySandbox() as sandbox:
    #     print(f"🆔 Sandbox ID: {sandbox.id}")
    #
    #     # 3. 测试命令执行（包含超时逻辑）
    #     print(sandbox.execute("pwd"))
    #     print(sandbox.execute("echo 'Test command execution'"))
    #
    #     # 4. 测试文件上传（包含二进制兼容逻辑）
    #     print(sandbox.upload_files([("test.txt", b"Hello, World!")]))
    #
    #     # 验证文件是否真的存在
    #     print(sandbox.execute("cat /home/wuying/test.txt"))
    #     # 增加这一行来查看文件到底在哪
    #     print(sandbox.execute("ls -l /home/wuying/test.txt"))
    #     print(sandbox.execute("cat /home/wuying/test.txt"))
    # print("--- 测试结束，资源应已自动释放 ---")

    # 测试1: 只同步 memory 和 skills 文件夹
    print("=" * 80)
    print("测试1: 选择性同步 memory 和 skills 文件夹")
    print("=" * 80)
    init_remote_agent_workspace(include_folders=['memory', 'skills'])

    # 测试2: 同步整个工作空间（取消注释以启用）
    # print("\n" + "=" * 80)
    # print("测试2: 同步整个工作空间")
    # print("=" * 80)
    # init_remote_agent_workspace(include_folders=None)
