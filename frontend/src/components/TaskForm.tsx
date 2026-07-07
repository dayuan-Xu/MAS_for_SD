import React, { useEffect, useState } from "react";
import { Modal, Form, Input, message, Button, Popconfirm } from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import { Task, TaskCreate, TaskUpdate, ThreadInfo } from "../types";
import { taskApi } from "../services/api";
import {
  messageStreamService,
  deleteThreadHistory,
} from "../services/messageStreamService";

const { TextArea } = Input;

interface TaskFormProps {
  open: boolean;
  task: Task | null;
  onClose: () => void;
  onSubmit: () => void;
  onThreadDeleted?: () => void;
}

const TaskForm: React.FC<TaskFormProps> = ({
  open,
  task,
  onClose,
  onSubmit,
  onThreadDeleted,
}) => {
  const [form] = Form.useForm();
  const [threads, setThreads] = useState<ThreadInfo[]>([]);
  const [runningThreads, setRunningThreads] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (open) {
      if (task) {
        form.setFieldsValue({
          name: task.name,
          description: task.description,
        });
        fetchThreads(task.id);
      } else {
        form.resetFields();
        setThreads([]);
      }
    }
  }, [open, task, form]);

  const fetchThreads = async (taskId: number) => {
    try {
      const [threadsResult, statusResult] = await Promise.all([
        taskApi.getThreads(taskId),
        taskApi.getTaskExecutionStatus(taskId),
      ]);
      setThreads(threadsResult.data.data.threads || []);
      const runningThreadIds = statusResult.data.data.running_thread_ids || [];
      setRunningThreads(new Set(runningThreadIds));
    } catch (error) {
      console.error("获取线程列表失败", error);
    }
  };

  const handleDeleteThread = async (threadId: number, threadIdStr: string) => {
    try {
      const { data } = await taskApi.deleteThread(threadId);
      setThreads((prev) => prev.filter((t) => t.id !== threadId));
      messageStreamService.disconnect(threadIdStr);
      await deleteThreadHistory(threadIdStr);
      message.success(data.msg);
      if (onThreadDeleted) {
        onThreadDeleted();
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || "删除失败");
    }
  };

  const handleSubmit = async (values: any) => {
    try {
      const taskData: TaskCreate = {
        name: values.name,
        description: values.description,
      };

      if (task) {
        const updateData: TaskUpdate = {
          ...taskData,
        };
        const { data } = await taskApi.update(task.id, updateData);
        message.success(data.msg);
      } else {
        const { data } = await taskApi.create(taskData);
        message.success(data.msg);
      }
      form.resetFields();
      onClose();
      onSubmit();
    } catch (error: any) {
      message.error(error.response?.data?.detail || "操作失败");
    }
  };

  const handleCancel = () => {
    form.resetFields();
    onClose();
  };

  return (
    <Modal
      title={task ? "编辑任务" : "创建任务"}
      open={open}
      onCancel={handleCancel}
      footer={null}
      width={600}
      centered
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        {task && (
          <Form.Item label="任务编号">
            <Input disabled value={task.id} />
          </Form.Item>
        )}

        <Form.Item
          name="name"
          label="任务名称"
          rules={[{ required: true, message: "请输入任务名称" }]}
        >
          <Input placeholder="请输入任务名称" />
        </Form.Item>

        <Form.Item
          name="description"
          label="任务描述"
          rules={[{ required: true, message: "请输入任务描述" }]}
        >
          <TextArea rows={4} placeholder="请输入任务描述" />
        </Form.Item>

        <Form.Item
          style={{
            marginBottom: 0,
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
          }}
        >
          <Button
            type="default"
            onClick={handleCancel}
            style={{ marginLeft: 10, marginRight: 10 }}
          >
            取消
          </Button>
          <Button type="primary" htmlType="submit">
            提交
          </Button>
        </Form.Item>
      </Form>

      {task && threads.length > 0 && (
        <div
          style={{
            marginTop: 24,
            borderTop: "1px solid #e8e8e8",
            paddingTop: 16,
          }}
        >
          <h4 style={{ margin: "0 0 12px 0" }}>关联线程</h4>
          <div style={{ maxHeight: 200, overflowY: "auto" }}>
            {threads.map((thread) => (
              <div
                key={thread.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "8px 0",
                  borderBottom: "1px dashed #f0f0f0",
                }}
              >
                <div>
                  <span style={{ fontWeight: 500 }}>线程 {thread.id}</span>
                  <span style={{ marginLeft: 8, color: "#666" }}>
                    {thread.context_box_name || "未命名"}
                  </span>
                  <span style={{ marginLeft: 8, color: "#999", fontSize: 12 }}>
                    {new Date(thread.created_at).toLocaleString()}
                  </span>
                </div>
                <Popconfirm
                  title="确定要删除该线程吗？同时将删除前端保存的该线程消息历史。"
                  onConfirm={() =>
                    handleDeleteThread(thread.id, thread.thread_id || "")
                  }
                  okText="确定"
                  cancelText="取消"
                >
                  <Button
                    danger
                    size="small"
                    icon={<DeleteOutlined />}
                    style={{ padding: "2px 8px", fontSize: 12 }}
                    disabled={
                      thread.thread_id
                        ? runningThreads.has(thread.thread_id)
                        : false
                    }
                  >
                    {thread.thread_id && runningThreads.has(thread.thread_id)
                      ? "运行中"
                      : "删除"}
                  </Button>
                </Popconfirm>
              </div>
            ))}
          </div>
        </div>
      )}
    </Modal>
  );
};

export default TaskForm;
