import Dexie from "dexie";
import { ExecutionState, Message, AIMessage, HumanMessage, ToolMessage, SystemMessage } from "../types";

interface ThreadHistory {
  threadId: string;
  messages: ExecutionState["messages"];
  lastUpdated: string;
}

class MessageDB extends Dexie {
  threadHistory!: Dexie.Table<ThreadHistory, string>;

  constructor() {
    super("MASMessageDB");
    this.version(1).stores({
      threadHistory: "threadId, lastUpdated",
    });
  }
}

const db = new MessageDB();

const saveThreadHistory = async (
  threadId: string,
  messages: ExecutionState["messages"],
) => {
  try {
    await db.threadHistory.put({
      threadId,
      messages,
      lastUpdated: new Date().toISOString(),
    });
  } catch (error) {
    console.error("保存历史消息失败", error);
  }
};

const loadThreadHistory = async (
  threadId: string,
): Promise<ExecutionState["messages"] | null> => {
  try {
    const history = await db.threadHistory.get(threadId);
    return history?.messages || null;
  } catch (error) {
    console.error("加载历史消息失败", error);
    return null;
  }
};

const deleteThreadHistory = async (threadId: string) => {
  try {
    await db.threadHistory.delete(threadId);
  } catch (error) {
    console.error("删除历史消息失败", error);
  }
};

const getAllThreadHistory = async (): Promise<ThreadHistory[]> => {
  try {
    return await db.threadHistory.toArray();
  } catch (error) {
    console.error("获取所有历史消息失败", error);
    return [];
  }
};

interface SSEMessage {
  type?: "system_message" | "agent_message";
  agent_name?: string;
  agent?: string;
  message?: any;
  error?: string;
  thread_id?: string;
}

const getAgentKey = (agentName?: string): keyof ExecutionState["messages"] => {
  const normalized = (agentName || "").toLowerCase();
  if (normalized.includes("bob") || normalized.includes("builder"))
    return "bob";
  if (normalized.includes("eva") || normalized.includes("evaluator"))
    return "eva";
  if (
    normalized.includes("alice") ||
    normalized.includes("planner") ||
    normalized.includes("leader")
  )
    return "alice";
  return "alice";
};

const normalizeSSEMessage = (
  sseMsg: SSEMessage,
  taskId: number,
): { agentKey: keyof ExecutionState["messages"]; message: Message } => {
  if (sseMsg.type === "system_message" || sseMsg.error) {
    const content =
      typeof sseMsg.message === "string"
        ? sseMsg.message
        : sseMsg.error || "系统消息";
    const systemMsg: SystemMessage = {
      id: `system-${Date.now()}-${Math.random()}`,
      agent_name: "系统",
      content,
      message_type: "system",
      timestamp: new Date().toISOString(),
    };
    return { agentKey: "alice", message: systemMsg };
  }

  const raw = sseMsg.message || {};
  const agentName = sseMsg.agent_name ?? sseMsg.agent ?? raw.name ?? "Alice";
  const rawType = raw.type || raw.message_type;
  const content =
    typeof raw.content === "string"
      ? raw.content
      : JSON.stringify(raw.content ?? "", null, 2);

  const id = raw.id || `${taskId}-${Date.now()}-${Math.random()}`;
  const timestamp = new Date().toISOString();
  const agentKey = getAgentKey(agentName);

  if (rawType === "human") {
    const humanMsg: HumanMessage = {
      id,
      agent_name: "用户",
      content,
      message_type: "user",
      timestamp,
    };
    return { agentKey, message: humanMsg };
  }

  if (rawType === "tool") {
    const toolMsg: ToolMessage = {
      id,
      agent_name: agentName,
      content,
      message_type: "tool",
      timestamp,
      tool_name: raw.name,
      tool_call_id: raw.tool_call_id,
      status: raw.status,
    };
    return { agentKey, message: toolMsg };
  }

  if (rawType === "system") {
    const systemMsg: SystemMessage = {
      id,
      agent_name: agentName,
      content,
      message_type: "system",
      timestamp,
    };
    return { agentKey, message: systemMsg };
  }

  const aiMsg: AIMessage = {
    id,
    agent_name: agentName,
    content,
    message_type: "ai",
    timestamp,
    tool_calls: raw.tool_calls,
  };
  return { agentKey, message: aiMsg };
};

interface ConnectionInfo {
  controller: AbortController;
  callbacks: Set<(msg: SSEMessage) => void>;
  messages: ExecutionState["messages"];
  isRunning: boolean;
  tabId: string;
  pendingSave: boolean;
  saveTimer: ReturnType<typeof setTimeout> | null;
  taskId: number;
  originalThreadId: string;
}

class MessageStreamService {
  private connections = new Map<string, ConnectionInfo>();
  private BROADCAST_CHANNEL_NAME = "mas-sse-messages";
  private broadcastChannel = new BroadcastChannel(this.BROADCAST_CHANNEL_NAME);
  private DEFAULT_SAVE_DELAY = 2000;
  private onConnectionCreatedCallbacks = new Set<(threadId: string) => void>();
  private onConnectionDestroyedCallbacks = new Set<(threadId: string) => void>();
  private onThreadIdChangedCallbacks = new Set<(oldThreadId: string, newThreadId: string) => void>();

  constructor() {
    this.initBroadcastChannel();
  }

  private initBroadcastChannel() {
    this.broadcastChannel.onmessage = (event) => {
      if (event.data.type === "message") {
        this.handleMessage(event.data.threadId, event.data.sseMsg, true);
      } else if (event.data.type === "sync") {
        this.syncFromOtherTab(event.data.threadId);
      }
    };
  }

  async connect(threadId: string, taskId: number, userInput: string): Promise<string> {
    let initialThreadId = threadId || `task-${taskId}-${Date.now()}`;

    let existingConn = this.connections.get(initialThreadId);
    if (!existingConn && threadId) {
      const entries = Array.from(this.connections.entries());
      for (let i = 0; i < entries.length; i++) {
        const [key, value] = entries[i];
        if (value.originalThreadId === threadId || key === threadId) {
          existingConn = value;
          initialThreadId = key;
          break;
        }
      }
    }

    const controller = new AbortController();
    let messages: ExecutionState["messages"];

    if (existingConn) {
      if (existingConn.tabId === this.getCurrentTabId() && existingConn.isRunning) {
        existingConn.controller.abort();
      }
      messages = existingConn.messages;
    } else {
      messages = (await loadThreadHistory(initialThreadId)) || (await loadThreadHistory(threadId)) || { alice: [], bob: [], eva: [] };
    }

    const userMessage = {
      id: `user-${Date.now()}-${Math.random()}`,
      agent_name: "用户",
      content: userInput,
      message_type: "user" as const,
      timestamp: new Date().toISOString(),
    };
    messages.alice = [...messages.alice, userMessage];

    if (existingConn) {
      // 复用已有连接对象，只更新必要字段，保留 callbacks 等状态
      existingConn.controller = controller;
      existingConn.messages = messages;
      existingConn.isRunning = true;
      existingConn.tabId = this.getCurrentTabId();
      existingConn.taskId = taskId;
      existingConn.originalThreadId = threadId;

      // 乐观更新：立即触发回调通知 UI 显示用户消息
      const fakeSSEMsg: SSEMessage = {
        type: "agent_message",
        thread_id: initialThreadId,
        agent_name: "alice",
        message: userMessage as any,
      };
      existingConn.callbacks.forEach((cb) => cb(fakeSSEMsg));
    } else {
      this.connections.set(initialThreadId, {
        controller,
        callbacks: new Set<(msg: SSEMessage) => void>(),
        messages,
        isRunning: true,
        tabId: this.getCurrentTabId(),
        pendingSave: false,
        saveTimer: null,
        taskId,
        originalThreadId: threadId,
      });
      this.notifyConnectionCreated(initialThreadId);
    }

    const conn = this.connections.get(initialThreadId)!;

    return new Promise<string>((resolve) => {
      const resolveThreadId = () => {
        const finalThreadId = this._findEffectiveThreadId(initialThreadId, threadId);
        resolve(finalThreadId);
      };

      const callback = (msg: SSEMessage) => {
        if (msg.thread_id && msg.thread_id !== initialThreadId) {
          conn.callbacks.delete(callback);
          resolve(msg.thread_id);
        }
      };
      conn.callbacks.add(callback);

      setTimeout(() => {
        conn.callbacks.delete(callback);
        resolveThreadId();
      }, 10000);

      this._consumeSSE(initialThreadId, taskId, userInput, threadId, controller);
    });
  }

  private _findEffectiveThreadId(initialThreadId: string, originalThreadId: string): string {
    if (this.connections.has(initialThreadId)) {
      return initialThreadId;
    }
    const entries = Array.from(this.connections.entries());
    for (let i = 0; i < entries.length; i++) {
      const [key, value] = entries[i];
      if (value.originalThreadId === originalThreadId || key === originalThreadId) {
        return key;
      }
    }
    return initialThreadId;
  }

  private async _consumeSSE(
    effectiveThreadId: string,
    taskId: number,
    userInput: string,
    threadId: string,
    controller: AbortController,
  ) {
    try {
      const response = await fetch(`http://localhost:8000/agent_team_sessions/start_sse/${taskId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_input: userInput, thread_id: threadId }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`SSE请求失败: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let currentThreadId = effectiveThreadId;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() || "";

        for (let i = 0; i < chunks.length; i++) {
          const chunk = chunks[i];
          const dataLines = chunk
            .split("\n")
            .filter((line) => line.startsWith("data:"))
            .map((line) => line.replace(/^data:\s?/, ""));

          if (dataLines.length === 0) continue;

          try {
            const sseMsg = JSON.parse(dataLines.join("\n"));
            this.handleMessage(currentThreadId, sseMsg, false);

            if (sseMsg.thread_id && sseMsg.thread_id !== currentThreadId) {
              currentThreadId = sseMsg.thread_id;
            }
          } catch (error) {
            console.error("解析SSE消息失败", error);
          }
        }
      }

      if (buffer.trim().startsWith("data:")) {
        try {
          const sseMsg = JSON.parse(buffer.replace(/^data:\s?/, ""));
          this.handleMessage(currentThreadId, sseMsg, false);
        } catch (error) {
          console.error("解析SSE尾部消息失败", error);
        }
      }
    } catch (error: any) {
      if (error.name !== "AbortError") {
        console.error("SSE连接失败", error);
      }
    } finally {
      const conn = this.connections.get(effectiveThreadId);
      if (!conn) {
        const entries = Array.from(this.connections.entries());
        for (let i = 0; i < entries.length; i++) {
          const [key, value] = entries[i];
          if (value.controller === controller) {
            value.isRunning = false;
            this.flushSave(key);
            break;
          }
        }
      } else {
        conn.isRunning = false;
        this.flushSave(effectiveThreadId);
      }
    }
  }

  private handleMessage(threadId: string, sseMsg: SSEMessage, fromBroadcast: boolean) {
    let conn = this.connections.get(threadId);
    const originalThreadId = threadId;

    if (!conn && sseMsg.thread_id) {
      conn = this.connections.get(sseMsg.thread_id);
      if (conn) threadId = sseMsg.thread_id;
    }

    if (!conn) {
      const entries = Array.from(this.connections.entries());
      for (let i = 0; i < entries.length; i++) {
        const [key, value] = entries[i];
        if (value.originalThreadId === sseMsg.thread_id || 
            value.originalThreadId === threadId ||
            key === sseMsg.thread_id ||
            (value.originalThreadId === "" && !sseMsg.thread_id)) {
          conn = value;
          threadId = key;
          break;
        }
      }
    }

    if (!conn) return;

    if (sseMsg.thread_id && threadId !== sseMsg.thread_id) {
      const oldThreadId = threadId;
      this.connections.set(sseMsg.thread_id, conn);
      this.connections.delete(threadId);
      threadId = sseMsg.thread_id;
      this.notifyThreadIdChanged(oldThreadId, threadId);
    }

    const idsToNotify = new Set<string>();
    idsToNotify.add(threadId);
    if (originalThreadId !== threadId) {
      idsToNotify.add(originalThreadId);
    }

    if (sseMsg.type === "system_message" || sseMsg.error) {
      conn.callbacks.forEach((cb) => cb(sseMsg));
      if (!fromBroadcast) {
        idsToNotify.forEach((id) => {
          this.broadcastChannel.postMessage({ type: "message", threadId: id, sseMsg });
        });
      }
      return;
    }

    const { agentKey, message: nextMessage } = normalizeSSEMessage(sseMsg, conn.taskId);
    
    let existingMessages = conn.messages[agentKey] || [];

    if (nextMessage.message_type === "user") {
      const hasOptimisticDuplicate = existingMessages.some(
        (msg) => msg.id.startsWith("user-") && msg.content === nextMessage.content,
      );
      if (hasOptimisticDuplicate) {
        existingMessages = existingMessages.map((msg) =>
          msg.id.startsWith("user-") && msg.content === nextMessage.content
            ? { ...msg, id: nextMessage.id }
            : msg,
        );
        conn.messages[agentKey] = existingMessages;
        this.scheduleSave(threadId);
      } else if (!existingMessages.some((msg) => msg.id === nextMessage.id)) {
        conn.messages[agentKey] = [...existingMessages, nextMessage];
        this.scheduleSave(threadId);
      }
    } else {
      if (!existingMessages.some((msg) => msg.id === nextMessage.id)) {
        conn.messages[agentKey] = [...existingMessages, nextMessage];
        this.scheduleSave(threadId);
      }
    }

    conn.callbacks.forEach((cb) => cb(sseMsg));

    if (!fromBroadcast) {
      idsToNotify.forEach((id) => {
        this.broadcastChannel.postMessage({ type: "message", threadId: id, sseMsg });
      });
    }
  }

  private scheduleSave(threadId: string) {
    const conn = this.connections.get(threadId);
    if (!conn || conn.pendingSave) return;

    conn.pendingSave = true;
    conn.saveTimer = setTimeout(() => {
      this.flushSave(threadId);
    }, this.DEFAULT_SAVE_DELAY);
  }

  private flushSave(threadId: string) {
    const conn = this.connections.get(threadId);
    if (!conn) return;

    if (conn.saveTimer) {
      clearTimeout(conn.saveTimer);
      conn.saveTimer = null;
    }

    saveThreadHistory(threadId, conn.messages);
    conn.pendingSave = false;
  }

  private syncFromOtherTab(threadId: string) {
    const conn = this.connections.get(threadId);
    if (conn) {
      saveThreadHistory(threadId, conn.messages);
    }
  }

  subscribe(threadId: string, callback: (msg: SSEMessage) => void) {
    let conn = this.connections.get(threadId);
    if (!conn) {
      const entries = Array.from(this.connections.entries());
      for (let i = 0; i < entries.length; i++) {
        const [key, value] = entries[i];
        if (value.originalThreadId === threadId || key === threadId) {
          conn = value;
          break;
        }
      }
    }
    if (conn) {
      conn.callbacks.add(callback);
    }
  }

  unsubscribe(threadId: string, callback: (msg: SSEMessage) => void) {
    let conn = this.connections.get(threadId);
    if (!conn) {
      const entries = Array.from(this.connections.entries());
      for (let i = 0; i < entries.length; i++) {
        const [key, value] = entries[i];
        if (value.originalThreadId === threadId || key === threadId) {
          conn = value;
          break;
        }
      }
    }
    if (conn) {
      conn.callbacks.delete(callback);
    }
  }

  disconnect(threadId: string) {
    const conn = this.connections.get(threadId);
    if (conn) {
      conn.controller.abort();
      conn.isRunning = false;
      this.flushSave(threadId);
    }

    const keysToDelete = [];
    const entries = Array.from(this.connections.entries());
    for (let i = 0; i < entries.length; i++) {
      const [key, c] = entries[i];
      if (c.controller.signal.aborted) {
        keysToDelete.push(key);
      }
    }
    keysToDelete.forEach((key) => {
      this.connections.delete(key);
      this.notifyConnectionDestroyed(key);
    });
  }

  getMessages(threadId: string): ExecutionState["messages"] | null {
    return this.connections.get(threadId)?.messages || null;
  }

  isConnected(threadId: string): boolean {
    const conn = this.connections.get(threadId);
    return conn?.isRunning || false;
  }

  getAllThreadIds(): string[] {
    return Array.from(this.connections.keys());
  }

  onConnectionCreated(callback: (threadId: string) => void) {
    this.onConnectionCreatedCallbacks.add(callback);
  }

  offConnectionCreated(callback: (threadId: string) => void) {
    this.onConnectionCreatedCallbacks.delete(callback);
  }

  private notifyConnectionCreated(threadId: string) {
    this.onConnectionCreatedCallbacks.forEach((cb) => cb(threadId));
  }

  onConnectionDestroyed(callback: (threadId: string) => void) {
    this.onConnectionDestroyedCallbacks.add(callback);
  }

  offConnectionDestroyed(callback: (threadId: string) => void) {
    this.onConnectionDestroyedCallbacks.delete(callback);
  }

  private notifyConnectionDestroyed(threadId: string) {
    this.onConnectionDestroyedCallbacks.forEach((cb) => cb(threadId));
  }

  onThreadIdChanged(callback: (oldThreadId: string, newThreadId: string) => void) {
    this.onThreadIdChangedCallbacks.add(callback);
  }

  offThreadIdChanged(callback: (oldThreadId: string, newThreadId: string) => void) {
    this.onThreadIdChangedCallbacks.delete(callback);
  }

  private notifyThreadIdChanged(oldThreadId: string, newThreadId: string) {
    this.onThreadIdChangedCallbacks.forEach((cb) => cb(oldThreadId, newThreadId));
  }

  private getCurrentTabId(): string {
    let tabId = sessionStorage.getItem("tabId");
    if (!tabId) {
      tabId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      sessionStorage.setItem("tabId", tabId);
    }
    return tabId;
  }
}

export const messageStreamService = new MessageStreamService();
export type { SSEMessage };
export { loadThreadHistory, saveThreadHistory, deleteThreadHistory, getAllThreadHistory };