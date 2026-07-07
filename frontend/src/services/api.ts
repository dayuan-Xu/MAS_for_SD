import axios from "axios";
import {
  Task,
  TaskCreate,
  TaskUpdate,
  TaskListResponse,
  TaskExecutionStatusResponse,
  TaskStatusBatchResponse,
  ThreadInfo,
  DeleteThreadResult,
  ApiResponse,
} from "../types";

const API_BASE_URL = "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export const taskApi = {
  create: (data: TaskCreate) => api.post<ApiResponse<Task>>("/tasks", data),
  list: (params: {
    page?: number;
    page_size?: number;
    search?: string;
    status?: string;
    sort_by?: string;
    sort_order?: string;
  }) => api.get<ApiResponse<TaskListResponse>>("/tasks", { params }),
  get: (id: number) => api.get<ApiResponse<Task>>(`/tasks/${id}`),
  update: (id: number, data: TaskUpdate) => api.put<ApiResponse<Task>>(`/tasks/${id}`, data),
  delete: (id: number) => api.delete<ApiResponse<{}>>(`/tasks/${id}`),
  getThreads: (taskId: number) => api.get<ApiResponse<{ threads: ThreadInfo[] }>>(`/tasks/threads/${taskId}`),
  deleteThread: (threadId: number) => api.delete<ApiResponse<DeleteThreadResult>>(`/tasks/threads/${threadId}`),
  getTaskExecutionStatus: (taskId: number) =>
    api.get<ApiResponse<TaskExecutionStatusResponse>>(`/tasks/${taskId}/status`),
  getTasksStatusBatch: (taskIds: number[]) =>
    api.get<ApiResponse<TaskStatusBatchResponse>>(
      `/tasks/status/batch?task_ids=${taskIds.join(",")}`
    ),
};

export const executionApi = {
  start: (taskId: number, userInput: string, threadId?: string) =>
    api.post(`/agent_team_sessions/start/${taskId}`, {
      user_input: userInput,
      thread_id: threadId,
    }),
  startSSE: (taskId: number, userInput: string, threadId?: string) =>
    api.post(`/agent_team_sessions/start_sse/${taskId}`, {
      user_input: userInput,
      thread_id: threadId,
    }),
  destroySession: (threadId: string) =>
    api.delete("/agent_team_sessions", {
      data: {
        thread_id: threadId,
      },
    }),
  cancelSession: (threadId: string) =>
    api.post("/agent_team_sessions/cancel", {
      thread_id: threadId,
    }),
};

export default api;
