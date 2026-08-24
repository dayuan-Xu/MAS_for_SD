import React from "react";
import { Layout, Menu } from "antd";
import {
  AppstoreOutlined,
  RocketOutlined,
  DatabaseOutlined,
} from "@ant-design/icons";
import TaskList from "./components/TaskList";
import TaskExecution from "./components/TaskExecution";
import MessageStorageManager from "./components/MessageStorageManager";
import { Task } from "./types";
import { MessageStreamProvider } from "./contexts/MessageStreamContext";

const { Header, Content, Sider } = Layout;

interface AppProps {
  initialTask?: Task | null;
}

const App: React.FC<AppProps> = ({ initialTask }) => {
  const [selectedKey, setSelectedKey] = React.useState("tasks");
  const [currentTask, setCurrentTask] = React.useState<Task | null>(
    initialTask || null,
  );
  const [isTaskStarting, setIsTaskStarting] = React.useState(false);
  const [currentThreadId, setCurrentThreadId] = React.useState<string>();

  React.useEffect(() => {
    if (initialTask) {
      setCurrentTask(initialTask);
      setSelectedKey("execution");
    }
  }, [initialTask]);

  const handleNavigateToExecution = (
    task: Task,
    isStarting?: boolean,
    threadId?: string,
  ) => {
    setCurrentTask(task);
    setIsTaskStarting(isStarting || false);
    setCurrentThreadId(threadId);
    setSelectedKey("execution");
  };

  return (
    <MessageStreamProvider>
      <Layout style={{ minHeight: "100vh" }}>
        <Header
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 24px",
          }}
        >
          <div style={{ color: "#fff", fontSize: 20, fontWeight: "bold" }}>
            基于多智能体协同的自主软件开发平台
          </div>
          <div style={{ color: "#fff", fontSize: 14 }}>
            Multi-Agent Software Development Platform
          </div>
        </Header>
        <Layout>
          <Sider width={200} theme="dark">
            <Menu
              mode="inline"
              selectedKeys={[selectedKey]}
              style={{ height: "100%", borderRight: 0 }}
              items={[
                {
                  key: "tasks",
                  icon: <AppstoreOutlined />,
                  label: "任务管理",
                },
                {
                  key: "execution",
                  icon: <RocketOutlined />,
                  label: "任务执行",
                },
                {
                  key: "storage",
                  icon: <DatabaseOutlined />,
                  label: "消息存储管理",
                },
              ]}
              onClick={({ key }) => setSelectedKey(key)}
            />
          </Sider>
          <Layout style={{ padding: "10px", flex: 1, height: "100%" }}>
            <Content
              style={{
                background: "#fff",
                padding: 10,
                margin: 0,
                minHeight: 280,
                borderRadius: 8,
                height: "100%",
              }}
            >
              {selectedKey === "tasks" && (
                <TaskList onNavigateToExecution={handleNavigateToExecution} />
              )}
              {selectedKey === "execution" && currentTask && (
                <TaskExecution
                  task={currentTask}
                  onBack={() => setSelectedKey("tasks")}
                  isStarting={isTaskStarting}
                  threadId={currentThreadId}
                />
              )}
              {selectedKey === "execution" && !currentTask && (
                <div>
                  <h2>任务执行</h2>
                  <p>请在任务管理页面选择一个任务并点击"启动"按钮开始执行。</p>
                </div>
              )}
              {selectedKey === "storage" && <MessageStorageManager />}
            </Content>
          </Layout>
        </Layout>
      </Layout>
    </MessageStreamProvider>
  );
};

export default App;
