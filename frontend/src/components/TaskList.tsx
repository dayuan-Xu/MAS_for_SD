import React, { useState, useEffect, useCallback } from "react";
import {
  Table,
  Button,
  Input,
  Select,
  Tag,
  Space,
  Popconfirm,
  message,
  Pagination,
  Modal,
  Tooltip,
} from "antd";
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  PlayCircleOutlined,
  PlusCircleOutlined,
} from "@ant-design/icons";
import {
  Task,
  ThreadInfo,
  ThreadStatusInfo,
  TaskExecutionStatusResponse,
  TaskExecutionStatus,
} from "../types";
import { taskApi } from "../services/api";
import TaskForm from "./TaskForm";
import TaskDetail from "./TaskDetail";

const { Search } = Input;
const { Option } = Select;

const executionStatusConfig: Record<
  TaskExecutionStatus,
  { color: string; label: string; description: string }
> = {
  idle: { color: "default", label: "空闲", description: "无智能体团队会话" },
  pending: {
    color: "blue",
    label: "待处理",
    description: "存在智能体团队会话但无任何智能体团队在运行",
  },
  running: {
    color: "processing",
    label: "运行中",
    description: "存在智能体团队在运行",
  },
};

interface TaskListProps {
  onNavigateToExecution?: (
    task: Task,
    isStarting?: boolean,
    threadId?: string,
  ) => void;
}

const TaskList: React.FC<TaskListProps> = ({ onNavigateToExecution }) => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(() => {
    const saved = localStorage.getItem("taskList_page");
    return saved ? parseInt(saved, 10) : 1;
  });
  const [pageSize, setPageSize] = useState(() => {
    const saved = localStorage.getItem("taskList_pageSize");
    return saved ? parseInt(saved, 10) : 5;
  });
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [showDetail, setShowDetail] = useState(false);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [statusInfoByTaskId, setStatusInfoByTaskId] = useState<
    Record<number, TaskExecutionStatusResponse | undefined>
  >({});

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    try {
      let allTaskItems: Task[] = [];
      let backendTotal = 0;

      if (statusFilter) {
        let hasMore = true;
        let currentPage = 1;
        while (hasMore) {
          const response = await taskApi.list({
            page: currentPage,
            page_size: 100,
            search,
            status: "",
            sort_by: "created_at",
          });
          allTaskItems = allTaskItems.concat(response.data.data.items);
          backendTotal = response.data.data.total;
          if (response.data.data.items.length < 100) {
            hasMore = false;
          }
          currentPage++;
        }
      } else {
        const response = await taskApi.list({
          page,
          page_size: pageSize,
          search,
          status: "",
          sort_by: "created_at",
        });
        allTaskItems = response.data.data.items;
        backendTotal = response.data.data.total;
      }

      const statusResults = await Promise.allSettled(
        allTaskItems.map(async (task) => {
          const { data } = await taskApi.getTaskExecutionStatus(task.id);
          return [task.id, data.data] as const;
        }),
      );
      const nextStatusInfoByTaskId: Record<
        number,
        TaskExecutionStatusResponse | undefined
      > = {};
      statusResults.forEach((result) => {
        if (result.status === "fulfilled") {
          const [taskId, info] = result.value;
          nextStatusInfoByTaskId[taskId] = info;
        }
      });
      setStatusInfoByTaskId(nextStatusInfoByTaskId);

      let filteredTasks = allTaskItems;
      if (statusFilter) {
        filteredTasks = allTaskItems.filter((task) => {
          const info = nextStatusInfoByTaskId[task.id];
          return info?.status === statusFilter;
        });
      }

      let displayTasks = filteredTasks;
      if (statusFilter) {
        const start = (page - 1) * pageSize;
        const end = start + pageSize;
        displayTasks = filteredTasks.slice(start, end);
      }

      setTasks(displayTasks);
      setTotal(statusFilter ? filteredTasks.length : backendTotal);

      if (statusResults.some((result) => result.status === "rejected")) {
        message.warning("部分任务状态获取失败，请稍后刷新");
      }
    } catch (error) {
      message.error("获取任务列表失败");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search, statusFilter]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  useEffect(() => {
    localStorage.setItem("taskList_pageSize", String(pageSize));
  }, [pageSize]);

  useEffect(() => {
    localStorage.setItem("taskList_page", String(page));
  }, [page]);

  const handleDelete = async (id: number) => {
    try {
      const { data } = await taskApi.delete(id);
      message.success(data.msg);
      fetchTasks();
    } catch (error: any) {
      message.error(error.response?.data?.detail || "删除失败");
    }
  };

  const handleEdit = (task: Task) => {
    setEditingTask(task);
    setShowForm(true);
  };

  const handleView = (task: Task) => {
    setSelectedTask(task);
    setShowDetail(true);
  };

  const [showThreadModal, setShowThreadModal] = useState(false);
  const [selectedTaskForThread, setSelectedTaskForThread] =
    useState<Task | null>(null);
  const [taskThreads, setTaskThreads] = useState<ThreadStatusInfo[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<number | null>(null);

  const handleStartExecution = (task: Task) => {
    onNavigateToExecution?.(task, true);
  };

  const handleContinueExecution = async (task: Task) => {
    try {
      const { data } = await taskApi.getTaskExecutionStatus(task.id);
      const statusData = data.data;
      setStatusInfoByTaskId((prev) => ({ ...prev, [task.id]: statusData }));

      if (statusData.threads.length === 0) {
        onNavigateToExecution?.(task, true);
      } else {
        setTaskThreads(statusData.threads);
        setSelectedTaskForThread(task);
        setSelectedThreadId(statusData.threads[0].id);
        setShowThreadModal(true);
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || "操作失败");
    }
  };

  const handleThreadSelect = async () => {
    if (!selectedTaskForThread || !selectedThreadId) return;

    const thread = taskThreads.find((t) => t.id === selectedThreadId);
    setShowThreadModal(false);
    onNavigateToExecution?.(
      selectedTaskForThread,
      false,
      thread?.thread_id ?? undefined,
    );
  };

  const handleFormSubmit = () => {
    setShowForm(false);
    setEditingTask(null);
    fetchTasks();
  };

  const columns = [
    {
      title: "编号",
      key: "id",
      render: (_: unknown, task: Task) => task.id,
    },
    {
      title: "任务名称",
      dataIndex: "name",
      key: "name",
      width: 200,
      ellipsis: true,
    },
    {
      title: "任务描述",
      dataIndex: "description",
      key: "description",
      ellipsis: true,
    },
    {
      title: "状态",
      key: "execution_status",
      width: 180,
      render: (_: unknown, record: Task) => {
        const info = statusInfoByTaskId[record.id];
        if (!info) {
          return <Tag color="default">判断中</Tag>;
        }
        const cfg = executionStatusConfig[info.status];
        return (
          <Tooltip title={cfg.description}>
            <Tag color={cfg.color}>{cfg.label}</Tag>
          </Tooltip>
        );
      },
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 160,
      render: (time: string) => new Date(time).toLocaleString(),
    },
    {
      title: "操作",
      key: "action",
      width: 320,
      render: (_: unknown, record: Task) => {
        const info = statusInfoByTaskId[record.id];
        const compactButtonStyle: React.CSSProperties = {
          padding: "1px 4px",
          minWidth: "auto",
          fontSize: "12px",
          marginRight: "2px",
        };

        return (
          <Space size={0}>
            <Button
              icon={<EyeOutlined />}
              size="small"
              onClick={() => handleView(record)}
              style={compactButtonStyle}
            >
              查看
            </Button>
            <Button
              icon={<EditOutlined />}
              size="small"
              onClick={() => handleEdit(record)}
              style={compactButtonStyle}
            >
              编辑
            </Button>
            {info === undefined ? (
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                size="small"
                disabled
                style={compactButtonStyle}
              >
                判断中
              </Button>
            ) : info.threads.length === 0 ? (
              <Tooltip title="启动新任务">
                <Button
                  icon={<PlayCircleOutlined />}
                  size="small"
                  onClick={() => handleStartExecution(record)}
                  style={{
                    ...compactButtonStyle,
                    backgroundColor: "#52c41a",
                    borderColor: "#52c41a",
                    color: "#fff",
                  }}
                >
                  启动
                </Button>
              </Tooltip>
            ) : info.status === "running" ? (
              <>
                <Tooltip title="存在运行中的线程">
                  <Button
                    icon={<PlayCircleOutlined />}
                    size="small"
                    onClick={() => handleContinueExecution(record)}
                    style={{
                      ...compactButtonStyle,
                      backgroundColor: "#8B4513",
                      borderColor: "#8B4513",
                      color: "#fff",
                    }}
                  >
                    参与
                  </Button>
                </Tooltip>
                <Tooltip title="新开一个线程">
                  <Button
                    icon={<PlusCircleOutlined />}
                    size="small"
                    onClick={() => handleStartExecution(record)}
                    style={{
                      ...compactButtonStyle,
                      backgroundColor: "#52c41a",
                      borderColor: "#52c41a",
                      color: "#fff",
                    }}
                  >
                    新开
                  </Button>
                </Tooltip>
              </>
            ) : (
              <>
                <Tooltip title="继续进行某个线程">
                  <Button
                    icon={<PlayCircleOutlined />}
                    size="small"
                    onClick={() => handleContinueExecution(record)}
                    style={{
                      ...compactButtonStyle,
                      backgroundColor: "#8B4513",
                      borderColor: "#8B4513",
                      color: "#fff",
                    }}
                  >
                    继续
                  </Button>
                </Tooltip>
                <Tooltip title="新开一个线程">
                  <Button
                    icon={<PlusCircleOutlined />}
                    size="small"
                    onClick={() => handleStartExecution(record)}
                    style={{
                      ...compactButtonStyle,
                      backgroundColor: "#52c41a",
                      borderColor: "#52c41a",
                      color: "#fff",
                    }}
                  >
                    新开
                  </Button>
                </Tooltip>
              </>
            )}
            <Popconfirm
              title="确定要删除该任务吗？"
              onConfirm={() => handleDelete(record.id)}
              okText="确定"
              cancelText="取消"
            >
              <Button
                danger
                icon={<DeleteOutlined />}
                size="small"
                style={compactButtonStyle}
              >
                删除
              </Button>
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <h2 style={{ margin: 0 }}>任务管理</h2>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setShowForm(true)}
        >
          创建任务
        </Button>
      </div>

      <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
        <Search
          placeholder="搜索任务"
          allowClear
          enterButton="搜索"
          size="middle"
          style={{ width: 300 }}
          onSearch={(value) => {
            setSearch(value);
            setPage(1);
          }}
        />
        <Select
          placeholder="状态筛选"
          allowClear
          style={{ width: 150 }}
          onChange={(value) => {
            setStatusFilter(value || "");
            setPage(1);
          }}
          value={statusFilter || undefined}
          optionLabelProp="label"
        >
          <Option value="idle" label="空闲">
            <Tooltip title="无智能体团队会话">
              <span>空闲</span>
            </Tooltip>
          </Option>
          <Option value="pending" label="待处理">
            <Tooltip title="存在智能体团队会话但无任何智能体团队在运行">
              <span>待处理</span>
            </Tooltip>
          </Option>
          <Option value="running" label="运行中">
            <Tooltip title="存在智能体团队在运行">
              <span>运行中</span>
            </Tooltip>
          </Option>
        </Select>
      </div>

      <div style={{ flex: 1, overflow: "auto" }}>
        <Table
          columns={columns}
          dataSource={tasks}
          rowKey="id"
          loading={loading}
          pagination={false}
          scroll={{ x: 1000 }}
        />
      </div>

      <div
        style={{ display: "flex", justifyContent: "flex-end", marginTop: 16 }}
      >
        <Pagination
          current={page}
          pageSize={pageSize}
          total={total}
          onChange={(p, s) => {
            setPage(p);
            setPageSize(s);
          }}
          showSizeChanger
          pageSizeOptions={["5", "10", "20", "50"]}
          showTotal={(total) => `共 ${total} 条记录`}
        />
      </div>

      <TaskForm
        open={showForm}
        task={editingTask}
        onClose={() => {
          setShowForm(false);
          setEditingTask(null);
        }}
        onSubmit={handleFormSubmit}
        onThreadDeleted={fetchTasks}
      />

      <TaskDetail
        open={showDetail}
        task={selectedTask!}
        onClose={() => setShowDetail(false)}
      />

      <Modal
        title="选择棕地"
        open={showThreadModal}
        onCancel={() => setShowThreadModal(false)}
        footer={[
          <Button key="back" onClick={() => setShowThreadModal(false)}>
            取消
          </Button>,
          <Button
            key="submit"
            type="primary"
            onClick={handleThreadSelect}
            disabled={!selectedThreadId}
          >
            确定继续
          </Button>,
        ]}
      >
        <p>
          任务 "{selectedTaskForThread?.name}"
          存在可继续的棕地线程，请选择要继续的线程：
        </p>
        <Select
          style={{ width: "100%", marginTop: 16 }}
          placeholder="请选择线程"
          value={selectedThreadId}
          onChange={(value) => setSelectedThreadId(value)}
        >
          {taskThreads.map((thread) => {
            const isRunning = thread.is_running || false;
            const isAlive = thread.is_alive || false;
            return (
              <Option key={thread.id} value={thread.id}>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  {isRunning && (
                    <span
                      style={{
                        display: "inline-block",
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        backgroundColor: "#52c41a",
                      }}
                    />
                  )}
                  <span>
                    棕地 {thread.id}
                    {thread.context_box_name && (
                      <span style={{ marginLeft: 4, color: "#999" }}>
                        - {thread.context_box_name}
                      </span>
                    )}
                  </span>
                  {isRunning && (
                    <span style={{ color: "#52c41a", fontSize: 12 }}>
                      (运行中)
                    </span>
                  )}
                  {isAlive && thread.last_access_time && (
                    <span style={{ fontSize: 11, color: "#999" }}>
                      最近访问:{" "}
                      {new Date(thread.last_access_time).toLocaleString()}
                    </span>
                  )}
                  {!isAlive && (
                    <span style={{ color: "#ff4d4f", fontSize: 11 }}>
                      (已销毁)
                    </span>
                  )}
                </span>
              </Option>
            );
          })}
        </Select>
      </Modal>
    </div>
  );
};

export default TaskList;
