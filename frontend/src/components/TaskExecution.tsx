import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
} from "react";
import { Button, Input, message, Alert, Badge, Tooltip } from "antd";
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
} from "@ant-design/icons";
import { Task, ExecutionState, Message, ToolCall } from "../types";
import { executionApi } from "../services/api";
import { useMessageStream } from "../contexts/MessageStreamContext";
import aliceAvatar from "../assets/images/planner alice.png";
import bobAvatar from "../assets/images/builder bob.png";
import evaAvatar from "../assets/images/evaluator eva.png";

const agentAvatarMap: Record<string, string> = {
  alice: aliceAvatar,
  bob: bobAvatar,
  eva: evaAvatar,
  system:
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E%3Ccircle cx='24' cy='24' r='22' fill='%238c8c8c'/%3E%3Ctext x='24' y='28' text-anchor='middle' font-family='Arial' font-size='16' fill='white'%3E%E7%B3%BB%E7%BB%9F%3C/text%3E%3C/svg%3E",
};

const { TextArea } = Input;

interface TaskExecutionProps {
  task: Task;
  onBack: () => void;
  isStarting?: boolean;
  threadId?: string;
}

const createInitialUserInput = (task: Task) => `针对一个软件需求完成开发。
软件需求描述如下：
task_name: ${task.name}
task_description: ${task.description}
项目工作空间为：/tmp/persistent/agent_workspace/warehouse/${task.name}`;

const TaskExecution: React.FC<TaskExecutionProps> = ({
  task,
  onBack,
  isStarting,
  threadId,
}) => {
  const [executionState, setExecutionState] = useState<ExecutionState | null>(
    null,
  );
  const [isRunning, setIsRunning] = useState(false);
  const [messageInput, setMessageInput] = useState("");
  const [currentThreadId, setCurrentThreadId] = useState<string>(
    threadId || "",
  );
  const currentThreadIdRef = useRef<string>(threadId || "");

  const [activeTab, setActiveTab] = useState("alice");
  const [systemNotice, setSystemNotice] = useState<string | null>(null);
  const [isScrolledUp, setIsScrolledUp] = useState(false);
  const [expandedToolMessages, setExpandedToolMessages] = useState<Set<string>>(
    new Set(),
  );
  const [collapsedToolMessages, setCollapsedToolMessages] = useState<
    Set<string>
  >(new Set());
  const [isDestroying, setIsDestroying] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const systemNoticeTimeoutRef = useRef<number | null>(null);

  const {
    connect,
    subscribe,
    unsubscribe,
    getMessages,
    isConnected,
    loadHistory,
    addMessageCallback,
    removeMessageCallback,
  } = useMessageStream();

  const currentMessages = useMemo(() => {
    if (!executionState?.messages) return [];
    const allMessages =
      executionState.messages[
        activeTab as keyof typeof executionState.messages
      ] || [];
    return allMessages.filter((msg) => msg.message_type !== "system");
  }, [executionState, activeTab]);

  const handleMessageUpdate = useCallback(
    (messages: ExecutionState["messages"]) => {
      setExecutionState((prev) => ({
        messages,
        error: prev?.error || null,
      }));
    },
    [],
  );

  useEffect(() => {
    if (!currentThreadId) return;

    const threadIdToUse = currentThreadId;

    const initMessages = async () => {
      const serviceMessages = getMessages(threadIdToUse);
      if (serviceMessages) {
        setExecutionState((prev) => ({
          messages: serviceMessages,
          error: prev?.error || null,
        }));
      } else {
        const historyMessages = await loadHistory(threadIdToUse);
        if (historyMessages) {
          setExecutionState((prev) => ({
            messages: historyMessages,
            error: prev?.error || null,
          }));
        }
      }
    };

    initMessages();
    addMessageCallback(threadIdToUse, handleMessageUpdate);

    return () => {
      removeMessageCallback(threadIdToUse, handleMessageUpdate);
    };
  }, [
    currentThreadId,
    getMessages,
    loadHistory,
    addMessageCallback,
    removeMessageCallback,
    handleMessageUpdate,
  ]);

  useEffect(() => {
    if (isStarting) {
      setMessageInput((currentInput) =>
        currentInput.trim() ? currentInput : createInitialUserInput(task),
      );
    }
  }, [isStarting, task]);

  useEffect(() => {
    const container =
      containerRef.current || messagesEndRef.current?.parentElement;
    if (container && !isScrolledUp) {
      container.scrollTop = container.scrollHeight;
    }
  }, [currentMessages, isScrolledUp]);

  useEffect(() => {
    const container =
      containerRef.current || messagesEndRef.current?.parentElement;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 100;
      setIsScrolledUp(!isAtBottom);
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      container.removeEventListener("scroll", handleScroll);
    };
  }, []);

  useEffect(() => {
    setIsScrolledUp(false);
    const container = containerRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [activeTab]);

  useEffect(() => {
    return () => {
      if (systemNoticeTimeoutRef.current) {
        clearTimeout(systemNoticeTimeoutRef.current);
      }
    };
  }, []);

  const handleStop = useCallback(async () => {
    if (!currentThreadIdRef.current) return;
    try {
      const res = await executionApi.cancelSession(currentThreadIdRef.current);
      if (res.data.success) {
        message.success(res.data.msg);
      } else {
        message.warning(res.data.msg);
      }
    } catch (err: any) {
      message.error(
        err?.response?.data?.detail?.msg ||
          err?.message ||
          "发送中止信号失败",
      );
    }
  }, []);

  const handleSendMessage = useCallback(async () => {
    if (!messageInput.trim()) return;

    const userInput = messageInput;
    setMessageInput("");
    setIsRunning(true);

    const threadIdToUse = currentThreadIdRef.current || "";
    const effectiveThreadId = await connect(threadIdToUse, task.id, userInput);
    currentThreadIdRef.current = effectiveThreadId;
    setCurrentThreadId(effectiveThreadId);
  }, [connect, messageInput, task.id]);

  const handleDestroySandbox = useCallback(async () => {
    if (!currentThreadId) return;

    const confirmResult = window.confirm(
      "确定要销毁沙盒吗？这将清理所有会话资源，且无法恢复。",
    );
    if (!confirmResult) return;

    setIsDestroying(true);

    try {
      const result = await executionApi.destroySession(currentThreadId);
      if (result.data.success) {
        setSystemNotice(result.data.msg);
        if (systemNoticeTimeoutRef.current) {
          clearTimeout(systemNoticeTimeoutRef.current);
        }
        systemNoticeTimeoutRef.current = window.setTimeout(() => {
          setSystemNotice(null);
          setIsDestroying(false);
        }, 3000);
      } else {
        message.error(result.data.msg);
        setIsDestroying(false);
      }
    } catch (error: any) {
      message.error(error.response?.data?.msg || "销毁沙盒失败");
      setIsDestroying(false);
    }
  }, [currentThreadId, task.id]);

  const handleInputKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        handleSendMessage();
      }
    },
    [handleSendMessage],
  );

  const handleSSEMessage = useCallback((sseMsg: any) => {
    if (sseMsg.type === "system_message" || sseMsg.error) {
      const notice =
        typeof sseMsg.message === "string"
          ? sseMsg.message
          : sseMsg.error || "系统消息";
      setSystemNotice(notice);
      if (systemNoticeTimeoutRef.current) {
        clearTimeout(systemNoticeTimeoutRef.current);
      }
      systemNoticeTimeoutRef.current = window.setTimeout(() => {
        setSystemNotice(null);
      }, 5000);

      if (
        notice === "智能体团队本轮运行结束" ||
        notice === "智能体团队本轮运行已中止"
      ) {
        setIsRunning(false);
      }
    }
  }, []);

  useEffect(() => {
    if (!currentThreadId) return;

    const handleMessage = (msg: any) => {
      handleSSEMessage(msg);
    };

    subscribe(currentThreadId, handleMessage);

    return () => {
      unsubscribe(currentThreadId, handleMessage);
    };
  }, [currentThreadId, subscribe, unsubscribe, handleSSEMessage]);

  useEffect(() => {
    if (!threadId) return;

    const loadHistoryMessages = async () => {
      const historyMessages = await loadHistory(threadId);
      if (historyMessages) {
        setExecutionState({
          messages: historyMessages,
          error: null,
        });
      }

      if (!isConnected(threadId)) {
        currentThreadIdRef.current = threadId;
        setCurrentThreadId(threadId);
      }
    };

    loadHistoryMessages();
  }, [threadId, loadHistory, isConnected]);

  const canResume = !isRunning && executionState;
  const canStart = Boolean(isStarting || !executionState);

  const renderToolCall = useCallback(
    (toolCall: any, messageId: string, index: number) => {
      const toolKey = `${messageId}-toolcall-${index}`;
      const isExpanded = expandedToolMessages.has(toolKey);
      const isCollapsed = collapsedToolMessages.has(toolKey);
      const shouldAutoExpand = toolCall.name?.toLowerCase() === "send_message";
      const showExpanded = !isCollapsed && (isExpanded || shouldAutoExpand);

      if (!showExpanded) {
        return (
          <div
            key={toolKey}
            style={{
              backgroundColor: "#f6ffed",
              border: "1px solid #b7eb8f",
              borderRadius: 6,
              padding: "8px 12px",
              margin: "8px 0",
              fontSize: 13,
              display: "flex",
              alignItems: "center",
              gap: 8,
              cursor: "pointer",
            }}
            onClick={() => {
              setExpandedToolMessages((prev) => {
                const next = new Set(prev);
                next.add(toolKey);
                return next;
              });
              setCollapsedToolMessages((prev) => {
                const next = new Set(prev);
                next.delete(toolKey);
                return next;
              });
            }}
          >
            <span>📦</span>
            <span style={{ fontWeight: "bold", color: "#52c41a" }}>
              工具调用: {toolCall.name}
            </span>
            <span style={{ color: "#999", fontSize: 12 }}>点击展开</span>
          </div>
        );
      }

      return (
        <div key={toolKey}>
          <div
            style={{
              backgroundColor: "#f6ffed",
              border: "1px solid #b7eb8f",
              borderRadius: 6,
              padding: 8,
              margin: "8px 0",
              fontSize: 13,
              display: "flex",
              gap: 12,
            }}
          >
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: "50%",
                backgroundColor: "#52c41a",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#fff",
                flexShrink: 0,
              }}
            >
              🛠️
            </div>
            <div style={{ flex: 1 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 4,
                }}
              >
                <span style={{ fontWeight: "bold", color: "#52c41a" }}>
                  工具调用: {toolCall.name}
                </span>
                <button
                  style={{
                    background: "none",
                    border: "none",
                    color: "#999",
                    fontSize: 12,
                    cursor: "pointer",
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setCollapsedToolMessages((prev) => {
                      const next = new Set(prev);
                      next.add(toolKey);
                      return next;
                    });
                  }}
                >
                  折叠
                </button>
              </div>
              <div style={{ color: "#666" }}>
                <span style={{ fontWeight: "bold" }}>参数:</span>
                <pre
                  style={{
                    margin: "4px 0",
                    whiteSpace: "pre-wrap",
                    fontSize: 12,
                  }}
                >
                  {JSON.stringify(toolCall.args, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      );
    },
    [expandedToolMessages, collapsedToolMessages],
  );

  const getAvatarColor = useCallback((agentName: string) => {
    const colors: Record<string, string> = {
      用户: "#1890ff",
      Alice: "#52c41a",
      Bob: "#fa8c16",
      Eva: "#722ed1",
      系统: "#8c8c8c",
    };
    return colors[agentName] || "#8c8c8c";
  }, []);

  const getAvatarInitials = useCallback((agentName: string) => {
    if (agentName === "用户") return "用";
    if (agentName === "系统") return "系";
    return agentName.charAt(0).toUpperCase();
  }, []);

  const renderMessageContent = useCallback(
    (content: string, isUser: boolean) => {
      const parts = content.split(/```/);

      return parts.map((part, index) => {
        const isCodeBlock = index % 2 === 1;
        if (isCodeBlock) {
          const firstLineBreak = part.indexOf("\n");
          const code =
            firstLineBreak >= 0 ? part.slice(firstLineBreak + 1) : part;
          return (
            <pre
              key={index}
              style={{
                margin: "8px 0",
                padding: 12,
                backgroundColor: isUser ? "rgba(255,255,255,0.16)" : "#f6f8fa",
                border: isUser
                  ? "1px solid rgba(255,255,255,0.28)"
                  : "1px solid #e5e7eb",
                borderRadius: 6,
                overflowX: "auto",
                whiteSpace: "pre-wrap",
                fontSize: 13,
                lineHeight: 1.6,
              }}
            >
              {code.trim()}
            </pre>
          );
        }

        return part
          .split(/\n{2,}/)
          .filter((paragraph) => paragraph.trim())
          .map((paragraph, paragraphIndex) => (
            <div
              key={`${index}-${paragraphIndex}`}
              style={{
                marginTop: index === 0 && paragraphIndex === 0 ? 0 : 8,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {paragraph.trim()}
            </div>
          ));
      });
    },
    [],
  );

  const renderMessage = useCallback(
    (msg: Message) => {
      if (msg.message_type === "system") {
        return (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: 12,
              padding: "8px 16px",
              backgroundColor: "#f0f5ff",
              borderRadius: 8,
              border: "1px dashed #91caff",
            }}
          >
            <span
              style={{
                fontSize: 14,
                color: "#1890ff",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <span>🟦</span>
              {msg.content}
            </span>
          </div>
        );
      }

      if (msg.message_type === "tool") {
        const toolKey = `toolmsg-${msg.id}`;
        const isExpanded = expandedToolMessages.has(toolKey);
        let toolName = msg.tool_name;
        if (!toolName && msg.tool_call_id) {
          const tabMessages =
            executionState?.messages?.[
              activeTab as keyof typeof executionState.messages
            ] || [];
          for (const m of tabMessages) {
            if (m.message_type === "ai" && m.tool_calls) {
              const matched = m.tool_calls.find(
                (tc: ToolCall) => tc.id === msg.tool_call_id,
              );
              if (matched) {
                toolName = matched.name;
                break;
              }
            }
          }
        }
        if (!toolName) {
          const match = msg.content.match(/Tool ['"](.+?)['"]/);
          if (match) toolName = match[1];
        }
        const finalToolName = toolName || "未知工具";
        const avatarImg = agentAvatarMap["system"];

        return (
          <div
            style={{
              display: "flex",
              marginBottom: 16,
              justifyContent: "flex-start",
            }}
          >
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                marginRight: 8,
                width: 48,
                flexShrink: 0,
              }}
            >
              <img
                src={avatarImg}
                alt="系统"
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: "50%",
                  objectFit: "cover",
                  boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
                }}
              />
              <span
                style={{
                  fontSize: 11,
                  color: "#666",
                  marginTop: 4,
                  textAlign: "center",
                  whiteSpace: "nowrap",
                }}
              >
                系统
              </span>
            </div>

            <div
              style={{
                display: "flex",
                flexDirection: "column",
                maxWidth: "75%",
              }}
            >
              <span style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>
                {new Date(msg.timestamp).toLocaleTimeString("zh-CN", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>

              {isExpanded ? (
                <div
                  style={{
                    backgroundColor: "#fff7e6",
                    border: "1px solid #ffd591",
                    borderRadius: "16px 16px 16px 0",
                    boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "8px 16px",
                      borderBottom: "1px solid #ffe7ba",
                    }}
                  >
                    <span
                      style={{
                        fontWeight: "bold",
                        color: "#fa8c16",
                        fontSize: 13,
                      }}
                    >
                      工具调用结果: {finalToolName}
                    </span>
                    <button
                      style={{
                        background: "none",
                        border: "none",
                        color: "#999",
                        fontSize: 12,
                        cursor: "pointer",
                      }}
                      onClick={() => {
                        setExpandedToolMessages((prev) => {
                          const next = new Set(prev);
                          next.delete(toolKey);
                          return next;
                        });
                      }}
                    >
                      折叠
                    </button>
                  </div>
                  <div style={{ padding: "12px 16px" }}>
                    <div
                      style={{ color: "#333", fontSize: 14, lineHeight: 1.6 }}
                    >
                      {renderMessageContent(msg.content, false)}
                    </div>
                  </div>
                </div>
              ) : (
                <div
                  style={{
                    backgroundColor: "#fff7e6",
                    border: "1px solid #ffd591",
                    borderRadius: "16px 16px 16px 0",
                    padding: "8px 16px",
                    fontSize: 13,
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    cursor: "pointer",
                    boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
                  }}
                  onClick={() => {
                    setExpandedToolMessages((prev) => {
                      const next = new Set(prev);
                      next.add(toolKey);
                      return next;
                    });
                  }}
                >
                  <span>📦</span>
                  <span style={{ fontWeight: "bold", color: "#fa8c16" }}>
                    工具调用结果: {finalToolName}
                  </span>
                  <span style={{ color: "#999", fontSize: 12 }}>点击展开</span>
                </div>
              )}
            </div>
          </div>
        );
      }

      const isUser = msg.message_type === "user";
      let displayAgentName = msg.agent_name || "用户";
      if (isUser) {
        if (activeTab === "bob") {
          displayAgentName = "Alice";
        } else if (activeTab === "eva") {
          displayAgentName = "Bob";
        }
      }

      const avatarColor = getAvatarColor(displayAgentName);
      const agentAvatarImg = isUser ? null : agentAvatarMap[activeTab];

      return (
        <div
          style={{
            display: "flex",
            marginBottom: 16,
            justifyContent: isUser ? "flex-end" : "flex-start",
          }}
        >
          {!isUser && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                marginRight: 8,
                width: 48,
                flexShrink: 0,
              }}
            >
              <img
                src={agentAvatarImg!}
                alt={displayAgentName}
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: "50%",
                  objectFit: "cover",
                  boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
                }}
              />
              <span style={{ fontSize: 11, color: "#666", marginTop: 4 }}>
                {displayAgentName}
              </span>
            </div>
          )}

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              maxWidth: "75%",
            }}
          >
            {isUser && (
              <span
                style={{
                  fontSize: 11,
                  color: "#666",
                  marginBottom: 4,
                  textAlign: "right",
                }}
              >
                {new Date(msg.timestamp).toLocaleTimeString("zh-CN", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            )}

            {!isUser && (
              <span style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>
                {new Date(msg.timestamp).toLocaleTimeString("zh-CN", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            )}

            <div
              style={{
                padding: "12px 16px",
                borderRadius: isUser ? "16px 16px 0 16px" : "16px 16px 16px 0",
                backgroundColor: isUser ? "#1890ff" : "#ffffff",
                boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
                border: isUser ? "none" : "1px solid #e8e8e8",
              }}
            >
              <div
                style={{
                  color: isUser ? "#fff" : "#333",
                  fontSize: 14,
                  lineHeight: 1.6,
                }}
              >
                {renderMessageContent(msg.content, isUser)}
              </div>
              {msg.message_type === "ai" &&
                msg.tool_calls &&
                msg.tool_calls.length > 0 && (
                  <div style={{ marginTop: 10 }}>
                    {msg.tool_calls.map((toolCall, index) => (
                      <div key={index}>
                        {renderToolCall(toolCall, msg.id, index)}
                      </div>
                    ))}
                  </div>
                )}
            </div>
          </div>

          {isUser && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                marginLeft: 8,
              }}
            >
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: "50%",
                  backgroundColor: avatarColor,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#fff",
                  fontSize: 14,
                  fontWeight: "bold",
                  boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
                }}
              >
                {getAvatarInitials(displayAgentName)}
              </div>
              <span style={{ fontSize: 11, color: "#666", marginTop: 4 }}>
                {displayAgentName}
              </span>
            </div>
          )}
        </div>
      );
    },
    [
      activeTab,
      expandedToolMessages,
      executionState,
      getAvatarColor,
      getAvatarInitials,
      renderMessageContent,
      renderToolCall,
    ],
  );

  const aliceCount =
    executionState?.messages?.alice?.filter(
      (msg) => msg.message_type !== "system",
    ).length || 0;
  const bobCount =
    executionState?.messages?.bob?.filter(
      (msg) => msg.message_type !== "system",
    ).length || 0;
  const evaCount =
    executionState?.messages?.eva?.filter(
      (msg) => msg.message_type !== "system",
    ).length || 0;
  const agentTabs = [
    { key: "alice", label: "Alice", desc: "团队入口", count: aliceCount },
    { key: "bob", label: "Bob", desc: "Builder", count: bobCount },
    { key: "eva", label: "Eva", desc: "Evaluator", count: evaCount },
  ];
  const emptyTextByTab: Record<string, string> = {
    alice: "请在下方输入消息启动或继续任务",
    bob: "Bob 尚未参与此任务",
    eva: "Eva 尚未参与此任务",
  };

  return (
    <>
      <style>{`
        @keyframes cancel-spin {
          from { box-shadow: 0 0 0 2px rgba(255, 77, 79, 0.4); }
          50% { box-shadow: 0 0 0 5px rgba(255, 77, 79, 0.15); }
          to { box-shadow: 0 0 0 2px rgba(255, 77, 79, 0.4); }
        }
      `}</style>
    <div
      style={{
        height: "calc(100vh - 112px)",
        display: "flex",
        flexDirection: "column",
        position: "relative",
      }}
    >
      {systemNotice && (
        <Alert
          message={systemNotice}
          type="info"
          showIcon
          style={{
            position: "absolute",
            top: 52,
            right: 0,
            zIndex: 10,
            maxWidth: 420,
            boxShadow: "0 8px 24px rgba(15, 23, 42, 0.12)",
          }}
        />
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr auto 1fr",
          alignItems: "center",
          gap: 16,
          marginBottom: 8,
          minHeight: 36,
        }}
      >
        <h2
          style={{
            margin: 0,
            fontSize: 20,
            fontWeight: 600,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
          title={task.name}
        >
          {task.name}
        </h2>
        <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
          {agentTabs.map((tab) => (
            <Badge
              key={tab.key}
              count={tab.count}
              size="small"
              style={{ backgroundColor: "#1677ff" }}
              overflowCount={99999}
            >
              <Button
                type={activeTab === tab.key ? "primary" : "default"}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label} ({tab.desc})
              </Button>
            </Badge>
          ))}
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <Button
            type="primary"
            danger
            disabled={isRunning || !currentThreadId || isDestroying}
            loading={isDestroying}
            onClick={handleDestroySandbox}
            style={{ marginRight: 8 }}
          >
            {isDestroying ? "沙盒销毁中" : "销毁沙盒"}
          </Button>
          <Button onClick={onBack}>返回列表</Button>
        </div>
      </div>

      {executionState?.error && (
        <Alert
          message={executionState.error}
          type="error"
          showIcon
          style={{ marginBottom: 12 }}
        />
      )}

      <div
        ref={containerRef}
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
          padding: 16,
          backgroundColor: "#fafafa",
          border: "1px solid #f0f0f0",
          borderRadius: 8,
        }}
      >
        {currentMessages.length === 0 ? (
          <div
            style={{
              height: "100%",
              minHeight: 280,
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              alignItems: "center",
              color: "#8c8c8c",
            }}
          >
            <p style={{ margin: 0 }}>暂无消息</p>
            <p style={{ fontSize: 12, marginTop: 8 }}>
              {emptyTextByTab[activeTab]}
            </p>
          </div>
        ) : (
          currentMessages.map((msg) => renderMessage(msg))
        )}
        <div ref={messagesEndRef} />
      </div>

      {isScrolledUp && currentMessages.length > 0 && (
        <Button
          type="primary"
          shape="circle"
          icon={<ArrowDownOutlined />}
          onClick={() => {
            const container = containerRef.current;
            if (container) {
              container.scrollTo({
                top: container.scrollHeight,
                behavior: "smooth",
              });
            }
          }}
          style={{
            position: "fixed",
            right: 24,
            bottom: 120,
            zIndex: 100,
            boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
          }}
        />
      )}

      {activeTab === "alice" && (
        <div
          style={{
            marginTop: 8,
            display: "flex",
            justifyContent: "center",
            alignItems: "flex-end",
            gap: 8,
          }}
        >
          <div
            style={{
              position: "relative",
              width: "min(760px, 100%)",
            }}
          >
            <TextArea
              placeholder={
                isRunning
                  ? "向Alice发送消息"
                  : canResume
                    ? "输入消息以继续任务（棕地恢复）"
                    : "输入消息以启动任务"
              }
              value={messageInput}
              onChange={(e) => setMessageInput(e.target.value)}
              onKeyDown={handleInputKeyDown}
              autoSize={{ minRows: 3, maxRows: 10 }}
              disabled={isRunning || (!canStart && !canResume)}
              spellCheck={false}
              style={{
                width: "100%",
                padding: "14px 52px 14px 18px",
                borderRadius: 18,
                lineHeight: 1.6,
                resize: "none",
                boxShadow: "0 8px 24px rgba(15, 23, 42, 0.08)",
              }}
            />
            <Tooltip
              title={isRunning ? "中止" : "发送消息"}
              placement="top"
            >
              <Button
                type="primary"
                shape="circle"
                danger={isRunning}
                icon={<ArrowUpOutlined />}
                onClick={isRunning ? handleStop : handleSendMessage}
                disabled={
                  !isRunning &&
                  (!messageInput.trim() || (!canStart && !canResume))
                }
                style={{
                  position: "absolute",
                  right: 10,
                  bottom: 10,
                  width: 34,
                  height: 34,
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  ...(isRunning
                    ? {
                        animation: "cancel-spin 1.5s linear infinite",
                        boxShadow: "0 0 0 2px rgba(255, 77, 79, 0.2)",
                      }
                    : {}),
                }}
              />
            </Tooltip>
          </div>
        </div>
      )}
    </div>
    </>
  );
};

export default TaskExecution;
