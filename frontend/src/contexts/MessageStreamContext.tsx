import React, {
  createContext,
  useContext,
  useCallback,
  useEffect,
} from "react";
import { ExecutionState } from "../types";
import {
  messageStreamService,
  SSEMessage,
  loadThreadHistory,
} from "../services/messageStreamService";

interface MessageStreamContextType {
  connect: (
    threadId: string,
    taskId: number,
    userInput: string,
  ) => Promise<string>;
  disconnect: (threadId: string) => void;
  subscribe: (threadId: string, callback: (msg: SSEMessage) => void) => void;
  unsubscribe: (threadId: string, callback: (msg: SSEMessage) => void) => void;
  getMessages: (threadId: string) => ExecutionState["messages"] | null;
  isConnected: (threadId: string) => boolean;
  loadHistory: (threadId: string) => Promise<ExecutionState["messages"] | null>;
  addMessageCallback: (
    threadId: string,
    callback: (messages: ExecutionState["messages"]) => void,
  ) => void;
  removeMessageCallback: (
    threadId: string,
    callback: (messages: ExecutionState["messages"]) => void,
  ) => void;
}

const MessageStreamContext = createContext<
  MessageStreamContextType | undefined
>(undefined);

interface MessageStreamProviderProps {
  children: React.ReactNode;
}

const MessageStreamProvider: React.FC<MessageStreamProviderProps> = ({
  children,
}) => {
  const messageCallbacks = React.useRef<
    Map<string, Set<(messages: ExecutionState["messages"]) => void>>
  >(new Map());
  const connectionHandlers = React.useRef<
    Map<string, (msg: SSEMessage) => void>
  >(new Map());

  const connect = useCallback(
    async (
      threadId: string,
      taskId: number,
      userInput: string,
    ): Promise<string> => {
      return messageStreamService.connect(threadId, taskId, userInput);
    },
    [],
  );

  const disconnect = useCallback((threadId: string) => {
    messageStreamService.disconnect(threadId);
  }, []);

  const subscribe = useCallback(
    (threadId: string, callback: (msg: SSEMessage) => void) => {
      messageStreamService.subscribe(threadId, callback);
    },
    [],
  );

  const unsubscribe = useCallback(
    (threadId: string, callback: (msg: SSEMessage) => void) => {
      messageStreamService.unsubscribe(threadId, callback);
    },
    [],
  );

  const getMessages = useCallback(
    (threadId: string): ExecutionState["messages"] | null => {
      return messageStreamService.getMessages(threadId);
    },
    [],
  );

  const isConnected = useCallback((threadId: string): boolean => {
    return messageStreamService.isConnected(threadId);
  }, []);

  const loadHistory = useCallback(
    async (threadId: string): Promise<ExecutionState["messages"] | null> => {
      return loadThreadHistory(threadId);
    },
    [],
  );

  const addMessageCallback = useCallback(
    (
      threadId: string,
      callback: (messages: ExecutionState["messages"]) => void,
    ) => {
      let callbacks = messageCallbacks.current.get(threadId);
      if (!callbacks) {
        callbacks = new Set();
        messageCallbacks.current.set(threadId, callbacks);
      }
      callbacks.add(callback);
    },
    [],
  );

  const removeMessageCallback = useCallback(
    (
      threadId: string,
      callback: (messages: ExecutionState["messages"]) => void,
    ) => {
      const callbacks = messageCallbacks.current.get(threadId);
      if (callbacks) {
        callbacks.delete(callback);
      }
    },
    [],
  );

  const handleSSEMessage = useCallback((threadId: string) => {
    return (msg: SSEMessage) => {
      const effectiveThreadId = msg.thread_id || threadId;
      const callbacksToNotify = new Set<(messages: ExecutionState["messages"]) => void>();

      messageCallbacks.current.forEach((callbacks, storedThreadId) => {
        if (storedThreadId === effectiveThreadId || 
            storedThreadId === threadId ||
            (storedThreadId === threadId && !msg.thread_id)) {
          callbacks.forEach((cb) => callbacksToNotify.add(cb));
        }
      });

      const messages =
        messageStreamService.getMessages(effectiveThreadId) ||
        messageStreamService.getMessages(threadId);

      if (messages) {
        callbacksToNotify.forEach((cb) => cb(messages));
      }
    };
  }, []);

  useEffect(() => {
    const currentHandlers = new Map<string, (msg: SSEMessage) => void>();
    const connectionHandlersRef = connectionHandlers.current;

    const handleConnectionCreated = (threadId: string) => {
      const handleMessage = handleSSEMessage(threadId);
      currentHandlers.set(threadId, handleMessage);
      connectionHandlersRef.set(threadId, handleMessage);
      messageStreamService.subscribe(threadId, handleMessage);
    };

    const handleConnectionDestroyed = (threadId: string) => {
      const handleMessage = currentHandlers.get(threadId);
      if (handleMessage) {
        messageStreamService.unsubscribe(threadId, handleMessage);
        currentHandlers.delete(threadId);
        connectionHandlersRef.delete(threadId);
      }
    };

    const handleThreadIdChanged = (
      oldThreadId: string,
      newThreadId: string,
    ) => {
      const handleMessage = currentHandlers.get(oldThreadId);
      if (handleMessage) {
        messageStreamService.unsubscribe(oldThreadId, handleMessage);
        currentHandlers.delete(oldThreadId);
        connectionHandlersRef.delete(oldThreadId);

        const newHandleMessage = handleSSEMessage(newThreadId);
        currentHandlers.set(newThreadId, newHandleMessage);
        connectionHandlersRef.set(newThreadId, newHandleMessage);
        messageStreamService.subscribe(newThreadId, newHandleMessage);
      }

      const oldCallbacks = messageCallbacks.current.get(oldThreadId);
      if (oldCallbacks) {
        messageCallbacks.current.set(newThreadId, oldCallbacks);
        messageCallbacks.current.delete(oldThreadId);
      }
    };

    messageStreamService.onConnectionCreated(handleConnectionCreated);
    messageStreamService.onConnectionDestroyed(handleConnectionDestroyed);
    messageStreamService.onThreadIdChanged(handleThreadIdChanged);

    const threadIds = messageStreamService.getAllThreadIds();
    threadIds.forEach(handleConnectionCreated);

    return () => {
      messageStreamService.offConnectionCreated(handleConnectionCreated);
      messageStreamService.offConnectionDestroyed(handleConnectionDestroyed);
      messageStreamService.offThreadIdChanged(handleThreadIdChanged);
      currentHandlers.forEach((handleMessage, threadId) => {
        messageStreamService.unsubscribe(threadId, handleMessage);
      });
      currentHandlers.clear();
      connectionHandlersRef.clear();
    };
  }, [handleSSEMessage]);

  const value: MessageStreamContextType = {
    connect,
    disconnect,
    subscribe,
    unsubscribe,
    getMessages,
    isConnected,
    loadHistory,
    addMessageCallback,
    removeMessageCallback,
  };

  return (
    <MessageStreamContext.Provider value={value}>
      {children}
    </MessageStreamContext.Provider>
  );
};

export const useMessageStream = (): MessageStreamContextType => {
  const context = useContext(MessageStreamContext);
  if (!context) {
    throw new Error(
      "useMessageStream must be used within a MessageStreamProvider",
    );
  }
  return context;
};

export { MessageStreamProvider, MessageStreamContext };
