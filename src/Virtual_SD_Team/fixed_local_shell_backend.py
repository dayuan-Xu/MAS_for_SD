"""修复 Windows 编码问题的 LocalShellBackend"""
import subprocess
from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import ExecuteResponse


class FixedLocalShellBackend(LocalShellBackend):
    """修复 Windows 下 subprocess 编码问题的 Backend
    
    重写 execute 方法，强制使用 UTF-8 编码解码子进程输出，
    避免 Windows 中文系统下 GBK 解码导致的 UnicodeDecodeError。
    """
    
    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        """重写 execute 方法，强制使用 UTF-8 编码
        
        Args:
            command: 要执行的 shell 命令
            timeout: 超时时间（秒）
            
        Returns:
            ExecuteResponse: 包含命令执行结果
        """
        if not command or not isinstance(command, str):
            return ExecuteResponse(
                output="Error: Command must be a non-empty string.",
                exit_code=1,
                truncated=False,
            )

        effective_timeout = timeout if timeout is not None else self._default_timeout
        if effective_timeout <= 0:
            msg = f"timeout must be positive, got {effective_timeout}"
            raise ValueError(msg)

        try:
            result = subprocess.run(
                command,
                check=False,
                shell=True,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                env=self._env,
                cwd=str(self.cwd),
                encoding='utf-8',  # 强制使用 UTF-8 编码
                errors='replace',  # 遇到无法解码的字符用替换符代替，避免崩溃
            )

            # Combine stdout and stderr
            output_parts = []
            if result.stdout:
                output_parts.append(result.stdout)
            if result.stderr:
                stderr_lines = result.stderr.strip().split("\n")
                output_parts.extend(f"[stderr] {line}" for line in stderr_lines)

            output = "\n".join(output_parts) if output_parts else "<no output>"

            # Check for truncation
            truncated = False
            if len(output) > self._max_output_bytes:
                output = output[: self._max_output_bytes]
                output += f"\n\n... Output truncated at {self._max_output_bytes} bytes."
                truncated = True

            # Add exit code info if non-zero
            if result.returncode != 0:
                output = f"{output.rstrip()}\n\nExit code: {result.returncode}"

            return ExecuteResponse(
                output=output,
                exit_code=result.returncode,
                truncated=truncated,
            )

        except subprocess.TimeoutExpired:
            if timeout is not None:
                msg = f"Error: Command timed out after {effective_timeout} seconds (custom timeout). The command may be stuck or require more time."
            else:
                msg = f"Error: Command timed out after {effective_timeout} seconds. For long-running commands, re-run using the timeout parameter."
            return ExecuteResponse(
                output=msg,
                exit_code=124,
                truncated=False,
            )
        except Exception as e:
            return ExecuteResponse(
                output=f"Error executing command ({type(e).__name__}): {e}",
                exit_code=1,
                truncated=False,
            )
