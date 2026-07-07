import React, { useState, useEffect, useCallback } from "react";
import { Table, Button, message, Popconfirm, Modal, Space } from "antd";
import {
  DeleteOutlined,
  DatabaseOutlined,
  MessageOutlined,
  EyeOutlined,
} from "@ant-design/icons";
import {
  getAllThreadHistory,
  deleteThreadHistory,
} from "../services/messageStreamService";

interface ThreadHistoryItem {
  threadId: string;
  messages: {
    alice: any[];
    bob: any[];
    eva: any[];
  };
  lastUpdated: string;
}

const MessageStorageManager: React.FC = () => {
  const [threadHistory, setThreadHistory] = useState<ThreadHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [visible, setVisible] = useState(false);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [selectedMessages, setSelectedMessages] = useState<any[]>([]);

  const fetchAllData = useCallback(async () => {
    setLoading(true);
    try {
      const history = await getAllThreadHistory();
      setThreadHistory(history);
    } catch (error) {
      console.error("获取数据失败", error);
      message.error("获取数据失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  const getAllMessages = (messages: ThreadHistoryItem["messages"]) => {
    const allMessages: any[] = [];
    const agentKeyMap: Record<string, string> = {
      alice: "Alice",
      bob: "Bob",
      eva: "Eva",
    };
    (Object.keys(agentKeyMap) as Array<keyof typeof messages>).forEach(
      (key) => {
        messages[key].forEach((msg) => {
          if (msg.message_type !== "system") {
            const agentKey =
              msg.message_type === "user"
                ? msg.agent_name || "用户"
                : agentKeyMap[key];
            allMessages.push({ ...msg, agentKey });
          }
        });
      },
    );
    allMessages.sort(
      (a, b) =>
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
    );
    return allMessages;
  };

  const getMessageCount = (messages: ThreadHistoryItem["messages"]) => {
    return getAllMessages(messages).length;
  };

  const handleViewMessages = (record: ThreadHistoryItem) => {
    setSelectedThreadId(record.threadId);
    setSelectedMessages(getAllMessages(record.messages));
    setVisible(true);
  };

  const handleDelete = async (threadId: string) => {
    try {
      await deleteThreadHistory(threadId);
      setThreadHistory((prev) =>
        prev.filter((item) => item.threadId !== threadId),
      );
      message.success("删除成功");
    } catch (error) {
      console.error("删除失败", error);
      message.error("删除失败");
    }
  };

  const columns = [
    {
      title: "Thread ID",
      dataIndex: "threadId",
      key: "threadId",
      ellipsis: true,
      width: 250,
    },
    {
      title: "消息总数",
      dataIndex: "messages",
      key: "messages",
      render: (
        messages: ThreadHistoryItem["messages"],
        record: ThreadHistoryItem,
      ) => {
        const count = getMessageCount(messages);
        return (
          <Space>
            <span style={{ fontSize: 12, color: "#666" }}>{count} 条消息</span>
            <Button
              size="small"
              icon={<EyeOutlined />}
              onClick={() => handleViewMessages(record)}
              disabled={count === 0}
            >
              查看
            </Button>
          </Space>
        );
      },
    },
    {
      title: "操作",
      key: "action",
      render: (_: any, record: ThreadHistoryItem) => (
        <Popconfirm
          title="确定要删除该线程的所有消息吗？此操作不可恢复。"
          onConfirm={() => handleDelete(record.threadId)}
          okText="确定"
          cancelText="取消"
        >
          <Button danger size="small" icon={<DeleteOutlined />}>
            删除
          </Button>
        </Popconfirm>
      ),
      width: 120,
    },
  ];

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          marginBottom: 16,
        }}
      >
        <DatabaseOutlined style={{ fontSize: 24, color: "#1890ff" }} />
        <h2>消息存储管理</h2>
      </div>
      <Button
        type="primary"
        onClick={fetchAllData}
        loading={loading}
        style={{ marginBottom: 16 }}
      >
        刷新列表
      </Button>
      <Table
        dataSource={threadHistory}
        columns={columns}
        rowKey="threadId"
        loading={loading}
        pagination={{ pageSize: 10 }}
        style={{ marginTop: 16 }}
        title={() => `共 ${threadHistory.length} 条记录`}
      />

      <Modal
        title={`Thread: ${selectedThreadId}`}
        open={visible}
        onCancel={() => setVisible(false)}
        footer={null}
        width={800}
        bodyStyle={{ maxHeight: "60vh", overflowY: "auto" }}
      >
        <div style={{ padding: "16px 0" }}>
          {selectedMessages.length === 0 ? (
            <p style={{ textAlign: "center", color: "#999" }}>无消息</p>
          ) : (
            <div>
              {selectedMessages.map((msg, index) => {
                const content =
                  typeof msg.content === "string"
                    ? msg.content
                    : JSON.stringify(msg.content, null, 2);
                return (
                  <div
                    key={index}
                    style={{
                      marginBottom: 16,
                      padding: 12,
                      backgroundColor: "#fafafa",
                      borderRadius: 8,
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        marginBottom: 8,
                      }}
                    >
                      <MessageOutlined
                        style={{ fontSize: 14, color: "#1890ff" }}
                      />
                      <span style={{ fontWeight: 500 }}>
                        {msg.agentKey || msg.agent_name}
                      </span>
                      <span style={{ fontSize: 12, color: "#999" }}>
                        {new Date(msg.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <pre
                      style={{
                        fontSize: 13,
                        color: "#333",
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-all",
                        margin: 0,
                      }}
                    >
                      {content}
                    </pre>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};

export default MessageStorageManager;
