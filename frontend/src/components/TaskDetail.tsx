import React, { useEffect, useState } from "react";
import { Modal, Tag, Descriptions, Tooltip } from "antd";
import {
  Task,
  TaskExecutionStatusResponse,
  TaskExecutionStatus,
} from "../types";
import { taskApi } from "../services/api";

interface TaskDetailProps {
  open: boolean;
  task: Task;
  onClose: () => void;
}

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

const TaskDetail: React.FC<TaskDetailProps> = ({ open, task, onClose }) => {
  const [statusInfo, setStatusInfo] =
    useState<TaskExecutionStatusResponse | null>(null);

  useEffect(() => {
    if (open && task) {
      taskApi
        .getTaskExecutionStatus(task.id)
        .then(({ data }) => setStatusInfo(data.data))
        .catch(() => setStatusInfo(null));
    }
  }, [open, task]);

  if (!task) return null;

  const cfg = statusInfo
    ? executionStatusConfig[statusInfo.status]
    : { color: "default", label: "判断中", description: "" };

  return (
    <Modal
      title="任务详情"
      open={open}
      onCancel={onClose}
      footer={null}
      width={600}
    >
      <Descriptions bordered column={1} size="small">
        <Descriptions.Item label="任务编号" style={{ padding: 4 }}>
          {task.id}
        </Descriptions.Item>
        <Descriptions.Item label="任务名称">{task.name}</Descriptions.Item>
        <Descriptions.Item label="任务描述">
          {task.description}
        </Descriptions.Item>
        <Descriptions.Item label="状态">
          <Tooltip title={cfg.description}>
            <Tag color={cfg.color}>{cfg.label}</Tag>
          </Tooltip>
        </Descriptions.Item>
        <Descriptions.Item
          label="创建时间"
          style={{ padding: 4, fontSize: 12 }}
        >
          {new Date(task.created_at).toLocaleString()}
        </Descriptions.Item>
        <Descriptions.Item
          label="更新时间"
          style={{ padding: 4, fontSize: 12 }}
        >
          {new Date(task.updated_at).toLocaleString()}
        </Descriptions.Item>
      </Descriptions>
    </Modal>
  );
};

export default TaskDetail;
