"""Context Box 管理模块。

提供对 AgentBay Context Box（持久化存储上下文）的管理功能，包括：
1. 列出所有 Context Box 及其元信息
2. 根据 Context ID 获取 Context 对象
3. 查看 Context Box 内部文件结构
4. 下载 Context Box 中的所有文件到本地

使用示例：
    ```python
    from src.utils.context_box import ContextBoxManager
    
    # 创建管理器实例
    manager = ContextBoxManager()
    
    # 1. 列出所有 Context Box
    contexts = manager.list_all_contexts()
    for ctx in contexts:
        print(f"ID: {ctx.id}, Name: {ctx.name}, Created: {ctx.created_at}")
    
    # 2. 根据 ID 获取 Context
    context = manager.get_context_by_id("SdkCtx-04poml0ue21och2li")
    if context:
        print(f"Context Name: {context.name}")
        
        # 3. 查看内部结构
        files = manager.list_context_files(context.id, "/")
        for file_entry in files:
            print(f"  - {file_entry.file_path} ({file_entry.size} bytes)")
        
        # 4. 下载所有文件到本地
        from pathlib import Path
        local_dir = Path("./downloaded_context")
        manager.download_all_files(context.id, "/", local_dir)
    ```
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import List, Optional

from agentbay import AgentBay, Context, ContextFileEntry, ContextListParams, ContextListResult

from src.config.settings import settings

logger = logging.getLogger(__name__)


class ContextBoxManager:
    """AgentBay Context Box 管理器。
    
    提供对 Context Box 的完整管理能力，包括查询、浏览和下载功能。
    """

    def __init__(self, api_key: str = settings.WUYING_AGENTBAY_API_KEY):
        """初始化 ContextBoxManager。
        
        Args:
            api_key: AgentBay API 密钥，默认从 settings 中读取
        """
        self._agent_bay = AgentBay(api_key=api_key)
        self._context_service = self._agent_bay.context
        logger.info("✅ ContextBoxManager 初始化完成")

    def list_all_contexts(
            self,
            max_results: int = 100,
            session_id: Optional[str] = None
    ) -> List[Context]:
        """列出当前 API Key 下的所有 Context Box。
        
        Args:
            max_results: 最大返回数量，默认 100
            session_id: 可选，按 Session ID 过滤
            
        Returns:
            List[Context]: Context 对象列表，包含 id, name, created_at, last_used_at 等元信息
            
        Example:
            ```python
            manager = ContextBoxManager()
            contexts = manager.list_all_contexts(max_results=50)
            for ctx in contexts:
                print(f"ID: {ctx.id}, Name: {ctx.name}")
            ```
        """
        logger.info(f"📋 正在获取 Context Box 列表 (max_results={max_results})...")

        all_contexts: List[Context] = []
        next_token: Optional[str] = None

        try:
            while True:
                params = ContextListParams(
                    max_results=max_results,
                    next_token=next_token,
                    session_id=session_id
                )

                result: ContextListResult = self._context_service.list(params)

                if not result.success:
                    logger.error(f"❌ 获取 Context 列表失败: {result.error_message}")
                    return all_contexts

                if result.contexts:
                    all_contexts.extend(result.contexts)
                    logger.debug(f"   已获取 {len(result.contexts)} 个 Context")

                # 检查是否有更多页面
                if not result.next_token:
                    break

                next_token = result.next_token

                # 如果已经获取了足够多的结果，提前退出
                if len(all_contexts) >= max_results:
                    break

            logger.info(f"✅ 共获取 {len(all_contexts)} 个 Context Box")
            return all_contexts

        except Exception as e:
            logger.error(f"❌ 获取 Context 列表异常: {e}")
            import traceback
            traceback.print_exc()
            return all_contexts

    def get_context_by_id(self, context_id: str) -> Optional[Context]:
        """根据 Context ID 获取 Context 对象。
        
        Args:
            context_id: Context 的唯一标识符，如 "SdkCtx-04poml0ue21och2li"
            
        Returns:
            Optional[Context]: Context 对象，如果不存在则返回 None
            
        Example:
            ```python
            manager = ContextBoxManager()
            context = manager.get_context_by_id("SdkCtx-04poml0ue21och2li")
            if context:
                print(f"找到 Context: {context.name}")
            ```
        """
        logger.info(f"🔍 正在获取 Context (ID: {context_id})...")

        try:
            # 使用 get 方法通过 context_id 获取
            result = self._context_service.get(context_id=context_id)

            if result.success and result.context:
                logger.info(f"✅ 成功获取 Context: {result.context.name}")
                return result.context
            else:
                logger.warning(f"⚠️ 未找到 Context (ID: {context_id}): {result.error_message}")
                return None

        except Exception as e:
            logger.error(f"❌ 获取 Context 异常: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_context_by_name(self, name: str) -> Optional[Context]:
        """根据 Context 名称获取 Context 对象。
        
        Args:
            name: Context 的名称
            
        Returns:
            Optional[Context]: Context 对象，如果不存在则返回 None
        """
        logger.info(f"🔍 正在获取 Context (Name: {name})...")

        try:
            result = self._context_service.get(name=name)

            if result.success and result.context:
                logger.info(f"✅ 成功获取 Context: {result.context.name} (ID: {result.context.id})")
                return result.context
            else:
                logger.warning(f"⚠️ 未找到 Context (Name: {name}): {result.error_message}")
                return None

        except Exception as e:
            logger.error(f"❌ 获取 Context 异常: {e}")
            import traceback
            traceback.print_exc()
            return None

    def list_context_files(
            self,
            context_id: str,
            parent_folder_path: str = "/",
            page_size: int = 50
    ) -> List[ContextFileEntry]:
        """列出 Context Box 中指定目录下的文件和子目录。
        
        Args:
            context_id: Context 的唯一标识符
            parent_folder_path: 父目录路径，默认为根目录 "/"
            page_size: 每页返回的文件数量，默认 50
            
        Returns:
            List[ContextFileEntry]: 文件条目列表，包含 file_id, file_name, file_path, 
                                   file_type, size, gmt_create, gmt_modified, status 等信息
            
        Example:
            ```python
            manager = ContextBoxManager()
            files = manager.list_context_files("SdkCtx-xxx", "/warehouse/my_task")
            for file_entry in files:
                print(f"  {file_entry.file_path} - {file_entry.size} bytes")
            ```
        """
        logger.info(f"📂 正在列出 Context 文件 (ID: {context_id}, Path: {parent_folder_path})...")

        all_files: List[ContextFileEntry] = []
        page_number = 1

        try:
            while True:
                result = self._context_service.list_files(
                    context_id=context_id,
                    parent_folder_path=parent_folder_path,
                    page_number=page_number,
                    page_size=page_size
                )

                if not result.success:
                    logger.error(f"❌ 获取文件列表失败")
                    return all_files

                if result.entries:
                    all_files.extend(result.entries)
                    logger.debug(f"   第 {page_number} 页: {len(result.entries)} 个文件/目录")

                # 检查是否还有更多页面
                total_count = result.count or 0
                if len(all_files) >= total_count:
                    break

                page_number += 1

            logger.info(f"✅ 共获取 {len(all_files)} 个文件/目录条目")
            return all_files

        except Exception as e:
            logger.error(f"❌ 获取文件列表异常: {e}")
            import traceback
            traceback.print_exc()
            return all_files

    def download_all_files(
            self,
            context_id: str,
            remote_root_path: str = "/",
            local_download_dir: Path = None,
            overwrite: bool = False
    ) -> int:
        """下载 Context Box 中的所有文件到本地目录。
        
        Args:
            context_id: Context 的唯一标识符
            remote_root_path: 远程根目录路径，默认为 "/"
            local_download_dir: 本地下载目标目录，如果为 None 则使用当前工作目录下的 
                               "context_downloads/{context_id}" 目录
            overwrite: 是否覆盖已存在的文件，默认 False（跳过已存在文件）
            
        Returns:
            int: 成功下载的文件数量
            
        Example:
            ```python
            from pathlib import Path
            manager = ContextBoxManager()
            count = manager.download_all_files(
                "SdkCtx-xxx",
                "/",
                Path("./my_context_files"),
                overwrite=True
            )
            print(f"下载了 {count} 个文件")
            ```
        """
        if local_download_dir is None:
            local_download_dir = Path.cwd() / "context_downloads" / context_id

        logger.info(f"📥 开始下载 Context 文件 (ID: {context_id})")
        logger.info(f"   远程路径: {remote_root_path}")
        logger.info(f"   本地目录: {local_download_dir}")

        # 确保本地目录存在
        local_download_dir.mkdir(parents=True, exist_ok=True)

        downloaded_count = 0
        skipped_count = 0
        failed_count = 0

        try:
            # 递归下载文件
            downloaded_count = self._download_recursive(
                context_id=context_id,
                remote_path=remote_root_path,
                local_base_dir=local_download_dir,
                remote_base_path=remote_root_path,
                overwrite=overwrite,
                skipped_count_ref=[skipped_count],
                failed_count_ref=[failed_count]
            )

            logger.info(
                f"✅ 下载完成: 成功 {downloaded_count} 个, "
                f"跳过 {skipped_count} 个, 失败 {failed_count} 个"
            )
            return downloaded_count

        except Exception as e:
            logger.error(f"❌ 下载过程异常: {e}")
            import traceback
            traceback.print_exc()
            return downloaded_count

    def _download_recursive(
            self,
            context_id: str,
            remote_path: str,
            local_base_dir: Path,
            remote_base_path: str,
            overwrite: bool,
            skipped_count_ref: list,
            failed_count_ref: list
    ) -> int:
        """递归下载目录中的文件。
        
        Args:
            context_id: Context ID
            remote_path: 当前远程路径
            local_base_dir: 本地基础目录
            remote_base_path: 远程基础路径（用于计算相对路径）
            overwrite: 是否覆盖已存在文件
            skipped_count_ref: 跳过计数的引用列表
            failed_count_ref: 失败计数的引用列表
            
        Returns:
            int: 成功下载的文件数量
        """
        downloaded_count = 0

        try:
            # 列出当前目录下的所有文件和子目录
            files = self.list_context_files(context_id, remote_path, page_size=100)

            for file_entry in files:
                # 计算相对路径
                relative_path = Path(file_entry.file_path).relative_to(remote_base_path)
                local_path = local_base_dir / relative_path

                # 判断是文件还是目录
                if file_entry.file_type == "folder":
                    # 创建本地目录
                    local_path.mkdir(parents=True, exist_ok=True)
                    logger.debug(f"   📁 创建目录: {local_path}")

                    # 递归下载子目录
                    downloaded_count += self._download_recursive(
                        context_id=context_id,
                        remote_path=file_entry.file_path,
                        local_base_dir=local_base_dir,
                        remote_base_path=remote_base_path,
                        overwrite=overwrite,
                        skipped_count_ref=skipped_count_ref,
                        failed_count_ref=failed_count_ref
                    )
                else:
                    # 下载文件
                    if local_path.exists() and not overwrite:
                        logger.debug(f"   ⏭️  跳过已存在文件: {local_path}")
                        skipped_count_ref[0] += 1
                        continue

                    success = self._download_single_file(
                        context_id=context_id,
                        remote_file_path=file_entry.file_path,
                        local_file_path=local_path
                    )

                    if success:
                        downloaded_count += 1
                        logger.debug(f"   ✅ 已下载: {file_entry.file_path} -> {local_path}")
                    else:
                        failed_count_ref[0] += 1
                        logger.warning(f"   ❌ 下载失败: {file_entry.file_path}")

        except Exception as e:
            logger.error(f"❌ 递归下载出错 (路径: {remote_path}): {e}")

        return downloaded_count

    def _download_single_file(
            self,
            context_id: str,
            remote_file_path: str,
            local_file_path: Path
    ) -> bool:
        """下载单个文件。
        
        Args:
            context_id: Context ID
            remote_file_path: 远程文件路径
            local_file_path: 本地文件路径
            
        Returns:
            bool: 是否下载成功
        """
        temp_file_path = None

        try:
            # 确保父目录存在
            local_file_path.parent.mkdir(parents=True, exist_ok=True)

            # 获取预签名下载 URL
            url_result = self._context_service.get_file_download_url(
                context_id=context_id,
                file_path=remote_file_path
            )

            if not url_result.success or not url_result.url:
                logger.error(f"   获取下载 URL 失败: {url_result.error_message}")
                return False

            # 使用临时文件下载
            import requests

            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.tmp') as temp_file:
                temp_file_path = temp_file.name

                # 下载文件
                response = requests.get(url_result.url, timeout=60)
                response.raise_for_status()

                temp_file.write(response.content)

            # 移动到目标位置
            import shutil
            shutil.move(temp_file_path, str(local_file_path))

            return True

        except Exception as e:
            logger.error(f"   下载文件异常: {e}")
            return False

        finally:
            # 清理临时文件
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass

    def get_context_info(self, context_id: str) -> Optional[dict]:
        """获取 Context 的详细信息。
        
        Args:
            context_id: Context ID
            
        Returns:
            Optional[dict]: 包含 Context 详细信息的字典，包括：
                - id: Context ID
                - name: Context 名称
                - created_at: 创建时间
                - last_used_at: 最后使用时间
                - file_count: 文件总数（估算）
        """
        context = self.get_context_by_id(context_id)
        if not context:
            return None

        info = {
            "id": context.id,
            "name": context.name,
            "created_at": context.created_at,
            "last_used_at": context.last_used_at,
        }

        # 尝试获取文件数量（通过列出根目录）
        try:
            files = self.list_context_files(context_id, "/", page_size=1)
            # 这里只能获取第一页，实际文件数可能需要遍历所有页面
            info["has_files"] = len(files) > 0
        except Exception:
            info["has_files"] = False

        return info

    def __repr__(self) -> str:
        return f"ContextBoxManager(api_key='{settings.WUYING_AGENTBAY_API_KEY[:8]}...')"


if __name__ == "__main__":
    # 测试代码
    from src.config.config_logging import setup_logging

    setup_logging()

    logger.info("=" * 60)
    logger.info("ContextBoxManager 测试")
    logger.info("=" * 60)

    # 创建管理器
    manager = ContextBoxManager()

    # 1. 列出所有 Context
    logger.info("\n--- 测试 1: 列出所有 Context Box ---\n\n")
    contexts = manager.list_all_contexts(max_results=10)
    logger.info(f"找到 {len(contexts)} 个 Context Box:")
    for i, ctx in enumerate(contexts, 1):
        logger.info(f"  {i}. ID: {ctx.id}")
        logger.info(f"     Name: {ctx.name}")
        logger.info(f"     Created: {ctx.created_at}")
        logger.info(f"     Last Used: {ctx.last_used_at}")
        logger.info("")

    # 2. 如果有 Context，测试获取和浏览
    if contexts:
        test_context = contexts[0]  # 获取第一个 Context
        logger.info(f"\n--- 测试 2: 通过Context ID = {test_context.id})获取Context: ---\n\n")
        context = manager.get_context_by_id(test_context.id)
        if context:
            logger.info(f"  Context Name: {context.name}")
            logger.info(f"  Context ID: {context.id}")

            # 3. 列出文件
            logger.info(f"\n--- 测试 3: 列出 Context 文件 ---\n\n")
            files = manager.list_context_files(context.id, "/", page_size=20)
            logger.info(f"根目录下有 {len(files)} 个文件/目录:")
            for file_entry in files[:10]:  # 只显示前 10 个
                logger.info(f"  - {file_entry.file_path} "
                            f"(type: {file_entry.file_type}, size: {file_entry.size})")

            # 4. 下载文件（可选，取消注释以测试）
            # logger.info(f"\n--- 测试 4: 下载所有文件 ---")
            # from pathlib import Path
            # local_dir = Path("./test_context_download")
            # count = manager.download_all_files(context.id, "/", local_dir, overwrite=True)
            # logger.info(f"下载了 {count} 个文件到 {local_dir}")

    logger.info("=" * 60)
    logger.info("测试完成")
    logger.info("=" * 60)
