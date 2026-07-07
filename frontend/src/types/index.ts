export interface Task {
  id: number;
  name: string;
  description: string;
  status: TaskStatus;
  created_at: string;
  updated_at: string;
}

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface TaskCreate {
  name: string;
  description: string;
}

export interface TaskUpdate {
  name?: string;
  description?: string;
}

export interface TaskListResponse {
  total: number;
  items: Task[];
}

export interface ApiResponse<T = any> {
  success: boolean;
  msg: string;
  data: T;
}

// ===== 任务执行状态（基于后端 AgentTeamSession 内存状态） =====

/**
 * 任务执行状态（基于后端 AgentTeamSession 的内存状态判断）
 * - idle: 空闲 - 后端不存在任何相关的 AgentTeamSession
 * - pending: 待处理 - 存在未销毁的 AgentTeamSession 但无任何在运行
 * - running: 运行中 - 存在运行中的 AgentTeamSession
 */
export type TaskExecutionStatus = 'idle' | 'pending' | 'running';

/**
 * 线程信息（对应后端 ThreadInfo）
 */
export interface ThreadInfo {
  id: number;
  thread_id: string | null;
  context_box_name: string | null;
  context_box_id: string | null;
  created_at: string;
}

/**
 * 线程状态信息（对应后端 ThreadStatusInfo）
 */
export interface ThreadStatusInfo {
  id: number;
  thread_id: string | null;
  context_box_name: string | null;
  context_box_id: string | null;
  created_at: string;
  is_alive: boolean;
  is_running: boolean;
  last_access_time: string | null;
}

/**
 * 任务执行状态信息（对应后端 TaskExecutionStatusResponse）
 */
export interface TaskExecutionStatusResponse {
  status: TaskExecutionStatus;
  threads: ThreadStatusInfo[];
  running_thread_ids: string[];
}

/**
 * 任务状态批量响应（对应后端 TaskStatusBatchResponse）
 */
export interface TaskStatusBatchResponse {
  statuses: Record<number, TaskExecutionStatusResponse>;
}

/**
 * 删除线程结果（对应后端 DeleteThreadResult）
 */
export interface DeleteThreadResult {
  success: boolean;
  message: string;
  is_running: boolean;
}

export interface ExecutionState {
  messages: {
    alice: Message[];
    bob: Message[];
    eva: Message[];
  };
  error: string | null;
}

// ===== Tool 相关类型 =====

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, any>;
}

// ===== 消息类型（对应后端 LangChain 消息类型） =====

/**
 * 消息公共字段（对应 LangChain BaseMessage 的核心字段）
 */
interface BaseMessage {
  id: string;
  agent_name: string;
  content: string;
  timestamp: string;
}

/**
 * AI 消息（对应 LangChain AIMessage，type: "ai"）
 * 模型的输出，可能携带工具调用
 */
export interface AIMessage extends BaseMessage {
  message_type: 'ai';
  tool_calls?: ToolCall[];
}

/**
 * 人类消息（对应 LangChain HumanMessage，type: "human"）
 * 用户输入的消息
 */
export interface HumanMessage extends BaseMessage {
  message_type: 'user';
}

/**
 * 工具消息（对应 LangChain ToolMessage，type: "tool"）
 * 工具调用的执行结果，通过 tool_call_id 关联对应的工具调用
 */
export interface ToolMessage extends BaseMessage {
  message_type: 'tool';
  tool_name?: string;
  tool_call_id?: string;
  status?: 'success' | 'error';
}

/**
 * 系统消息（前端自定义，用于 SSE 系统通知）
 */
export interface SystemMessage extends BaseMessage {
  message_type: 'system';
}

/**
 * 消息判别联合类型
 * 通过 message_type 字段进行类型收窄
 */
export type Message = AIMessage | HumanMessage | ToolMessage | SystemMessage;
