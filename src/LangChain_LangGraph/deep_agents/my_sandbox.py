from deepagents.backends.sandbox import BaseSandbox
from deepagents.backends.protocol import ExecuteResponse, FileDownloadResponse, FileUploadResponse

# 该类通过本地docker容器实现execute工具（既shell命令执行工具）、文件上传下载工具。
class MySandbox(BaseSandbox):
    def execute(
            self,
            command: str,
            *,
            timeout: int | None = None,
    ) -> ExecuteResponse:
        """Execute a command in the sandbox and return ExecuteResponse.

        Args:
            command: Full shell command string to execute.
            timeout: Maximum time in seconds to wait for the command to complete.

                If None, uses the backend's default timeout.

        Returns:
            ExecuteResponse with combined output, exit code, and truncation flag.
        """
        pass

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        pass

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        pass

    @property
    def id(self) -> str:
        pass

