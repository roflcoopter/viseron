import React from "react";

import { Toast, toastIds } from "hooks/UseToast";
import { authToken } from "lib/api/auth";
import { clientId } from "lib/api/client";
import { sleep } from "lib/helpers";
import * as messages from "lib/messages";
import { loadTokens, tokenExpired } from "lib/tokens";
import * as types from "lib/types";

const DEBUG = false;

type Error = 1 | 2 | 3;
const ERR_CANNOT_CONNECT = 1;
const ERR_INVALID_AUTH = 2;
const ERR_CONNECTION_LOST = 3;
const MSG_TYPE_AUTH_REQUIRED = "auth_required";
const MSG_TYPE_AUTH_NOT_REQUIRED = "auth_not_required";
const MSG_TYPE_AUTH_INVALID = "auth_failed";
const MSG_TYPE_AUTH_OK = "auth_ok";

type Events = "connected" | "disconnected" | "connection-error";
export type EventListener = (conn: Connection, eventData?: any) => void;

export interface Message {
  command_id?: number;
  type: string;
  [key: string]: any;
}

export type WebSocketProviderProps = {
  children: React.ReactNode;
};

export type SubscriptionUnsubscribe = () => Promise<void>;

interface SubscribeEventCommmandInFlight<T> {
  resolve: (result?: any) => void;
  reject: (err: any) => void;
  callback: (ev: T) => void;
  subscribe: (() => Promise<SubscriptionUnsubscribe>) | undefined;
  unsubscribe: SubscriptionUnsubscribe;
}

export function createSocket(wsURL: string): Promise<WebSocket> {
  if (DEBUG) {
    console.debug("[Socket] Initializing", wsURL);
  }

  function connect(
    promResolve: (socket: WebSocket) => void,
    promReject: (err: Error) => void,
  ) {
    if (DEBUG) {
      console.debug("[Socket] New connection", wsURL);
    }

    const socket = new WebSocket(wsURL);

    let invalidAuth = false;
    let refreshToken = false;
    const closeMessage = () => {
      socket.removeEventListener("close", closeMessage);
      if (refreshToken) {
        return;
      }

      if (invalidAuth) {
        promReject(ERR_INVALID_AUTH);
        return;
      }

      promReject(ERR_CANNOT_CONNECT);
    };

    const handleMessage = async (event: MessageEvent) => {
      let storedTokens = loadTokens();
      const message = JSON.parse(event.data);

      if (DEBUG) {
        console.debug("[Socket] Received", message);
      }
      switch (message.type) {
        case MSG_TYPE_AUTH_REQUIRED:
          if (tokenExpired()) {
            if (DEBUG) {
              console.debug("[Socket] Token expired, refreshing");
            }

            // If we already tried to refresh the token, we should not try again.
            if (refreshToken) {
              promReject(ERR_CANNOT_CONNECT);
              return;
            }

            refreshToken = true;
            await authToken({
              grant_type: "refresh_token",
              client_id: clientId(),
            });
            storedTokens = loadTokens();
            // Since we authenticate by partly using cookies, we need to close the
            // socket and open a new one so the refreshed signature_cookie is sent.
            socket.close();
            let newSocket: WebSocket;
            try {
              newSocket = await createSocket(wsURL);
            } catch (error) {
              promReject(error as Error);
              return;
            }
            promResolve(newSocket);
            return;
          }
          if (DEBUG) {
            console.debug("[Socket] Sending auth message", message);
          }
          if (!storedTokens) {
            promReject(ERR_INVALID_AUTH);
            return;
          }
          socket.send(
            JSON.stringify(
              messages.auth(`${storedTokens.header}.${storedTokens.payload}`),
            ),
          );
          break;

        case MSG_TYPE_AUTH_INVALID:
          if (DEBUG) {
            console.debug("[Socket] Auth failed");
          }
          invalidAuth = true;
          socket.close();
          break;

        case MSG_TYPE_AUTH_OK:
        case MSG_TYPE_AUTH_NOT_REQUIRED:
          socket.removeEventListener("message", handleMessage);
          socket.removeEventListener("close", closeMessage);
          socket.removeEventListener("error", closeMessage);
          promResolve(socket);
          break;

        default:
          if (DEBUG) {
            console.warn("[Socket] Unhandled message", message);
          }
      }
    };

    socket.addEventListener("message", handleMessage);
    socket.addEventListener("close", closeMessage);
    socket.addEventListener("error", closeMessage);
  }

  return new Promise((resolve, reject) =>
    // eslint-disable-next-line no-promise-executor-return
    connect(resolve, reject),
  );
}

export class Connection {
  socket: WebSocket | null = null;

  reconnectTimer: NodeJS.Timeout | null = null;

  closeRequested = false;

  commandId = 0;

  // Active commands and subscriptions
  commands = new Map();

  // Store subscriptions during a reconnect
  oldSubscriptions: Map<any, any> | undefined = undefined;

  // Holds messages sent when not connected. Sent as soon as connection is established
  queuedMessages:
    | Array<{
        resolve: (value?: unknown) => unknown;
        reject?: (err: any) => unknown;
      }>
    | undefined = [];

  // Internal event listeners
  eventListeners = new Map();

  pingInterval: NodeJS.Timeout | undefined;

  toast: Toast;

  constructor(_toast: Toast) {
    this.toast = _toast;
  }

  async connect() {
    if (this.socket) {
      return;
    }

    const wsURL = `${
      window.location.protocol === "https:" ? "wss://" : "ws://"
    }${location.host}/websocket`;

    // eslint-disable-next-line no-constant-condition
    while (true) {
      try {
        // eslint-disable-next-line no-await-in-loop
        this.socket = await createSocket(wsURL);
        break;
      } catch (error) {
        if (error === ERR_INVALID_AUTH) {
          // eslint-disable-next-line @typescript-eslint/no-throw-literal
          throw error;
        }
        console.debug("Error connecting, retrying", error);
        // eslint-disable-next-line no-await-in-loop
        await sleep(5000);
      }
    }
    this._initializeSocket();

    if (!this.reconnectTimer) {
      setTimeout(() => {
        this.connectingToast();
      }, 1000);
    }

    this._handleMessage = this._handleMessage.bind(this);
    this._handleClose = this._handleClose.bind(this);
    this.socket.addEventListener("message", this._handleMessage);
    this.socket.addEventListener("close", this._handleClose);
  }

  async disconnect(closeRequested = true) {
    this.closeRequested = closeRequested;
    if (this.socket) {
      this.socket.close();
    }
  }

  private _generateCommandId(): number {
    return ++this.commandId;
  }

  get connected() {
    return this.socket !== null && this.socket.readyState === this.socket.OPEN;
  }

  private _initializeSocket() {
    console.debug("Connection opened");
    this.commandId = 0;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    setTimeout(() => {
      this.toast.dismiss(toastIds.websocketConnecting);
      this.toast.dismiss(toastIds.websocketConnectionLost);
    }, 500);

    const oldSubscriptions = this.oldSubscriptions;
    if (oldSubscriptions) {
      this.oldSubscriptions = undefined;
      oldSubscriptions.forEach(
        (subscription: SubscribeEventCommmandInFlight<any>) => {
          if ("subscribe" in subscription && subscription.subscribe) {
            subscription.subscribe().then((unsub) => {
              subscription.unsubscribe = unsub;
              // We need to resolve this in case it wasn't resolved yet.
              // This allows us to subscribe while we're disconnected
              // and recover properly.
              subscription.resolve();
            });
          }
        },
      );
    }

    const queuedMessages = this.queuedMessages;
    if (queuedMessages) {
      this.queuedMessages = undefined;
      for (const queuedMsg of queuedMessages) {
        queuedMsg.resolve();
      }
    }

    const ping = () => {
      this.pingInterval = setTimeout(async () => {
        try {
          await this.ping();
        } catch (err) {
          console.error("Ping failed:", err);
        }
        ping();
      }, 30000);
    };
    ping();

    this.fireEvent("connected");
  }

  private _handleMessage(event: any) {
    const message: types.WebSocketResponse = JSON.parse(event.data);
    const command_info = this.commands.get(message.command_id);

    switch (message.type) {
      case "event":
        if (command_info) {
          command_info.callback(
            (message as types.WebSocketEventResponse).event,
          );
        } else {
          console.warn(
            `Received event for unknown subscription ${message.command_id}. Unsubscribing.`,
          );
          // TODO UNSUB HERE
        }
        break;

      case "result":
        if (command_info) {
          if (message.success) {
            command_info.resolve(message.result);

            // Don't remove subscriptions.
            if (!("subscribe" in command_info)) {
              this.commands.delete(message.command_id);
            }
          } else {
            command_info.reject(message.error);
            this.commands.delete(message.command_id);
          }
        }
        break;

      case "pong":
        if (command_info) {
          command_info.resolve();
          this.commands.delete(message.command_id);
        } else {
          console.warn(`Received unknown pong response ${message.command_id}`);
        }
        break;
      default:
        console.warn("Unhandled message", message);
    }
  }

  private _handleClose = async () => {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
    }

    this.commandId = 0;
    this.oldSubscriptions = this.commands;
    this.commands = new Map();

    // Reject unanswered commands
    if (this.oldSubscriptions) {
      this.oldSubscriptions.forEach((subscription) => {
        if (!("subscribe" in subscription)) {
          subscription.reject("Connection lost");
        }
      });
    }

    if (this.socket) {
      this.socket.removeEventListener("close", this._handleClose);
      this.socket.removeEventListener("message", this._handleMessage);
    }

    this.fireEvent("disconnected");

    if (this.closeRequested) {
      this.socket = null;
      return;
    }

    if (!this.reconnectTimer) {
      console.debug("Connection closed");

      this.queuedMessages = [];
      this.toast.dismiss(toastIds.websocketConnecting);
      this.toast.info("Connection lost, reconnecting", {
        toastId: toastIds.websocketConnectionLost,
        autoClose: false,
      });
    }

    const reconnect = () => {
      this.reconnectTimer = setTimeout(async () => {
        this.socket = null;
        if (this.closeRequested) {
          return;
        }

        console.debug("Reconnecting to server...");
        try {
          await this.connect();
        } catch (err) {
          if (this.queuedMessages) {
            const queuedMessages = this.queuedMessages;
            this.queuedMessages = undefined;
            for (const msg of queuedMessages) {
              if (msg.reject) {
                msg.reject(ERR_CONNECTION_LOST);
              }
            }
          }
          if (err === ERR_INVALID_AUTH) {
            this.toast.dismiss(toastIds.websocketConnecting);
            this.toast.dismiss(toastIds.websocketConnectionLost);
            this.fireEvent("connection-error", err);
          } else {
            reconnect();
          }
        }
      }, 5000);
    };

    reconnect();
  };

  addEventListener(eventType: Events, callback: EventListener) {
    let listeners = this.eventListeners.get(eventType);

    if (!listeners) {
      listeners = [];
      this.eventListeners.set(eventType, listeners);
    }

    listeners.push(callback);
  }

  removeEventListener(eventType: Events, callback: EventListener) {
    const listeners = this.eventListeners.get(eventType);

    if (!listeners) {
      return;
    }

    const index = listeners.indexOf(callback);

    if (index !== -1) {
      listeners.splice(index, 1);
    }
  }

  fireEvent(eventType: Events, eventData?: any) {
    (this.eventListeners.get(eventType) || []).forEach((callback: any) =>
      callback(this, eventData),
    );
  }

  connectingToast(): void {
    if (this.socket && this.socket.readyState === WebSocket.CONNECTING) {
      this.toast.info("Connecting to server", {
        toastId: toastIds.websocketConnecting,
        autoClose: false,
      });
    }
  }

  ping() {
    return this.sendMessagePromise(messages.ping());
  }

  private _sendMessage(message: Message) {
    if (!this.connected) {
      // eslint-disable-next-line @typescript-eslint/no-throw-literal
      throw ERR_CONNECTION_LOST;
    }
    console.debug("Sending", message);
    this.socket!.send(JSON.stringify(message));
  }

  sendMessage(message: Message, commandId: number | null = null) {
    message.command_id = commandId || this._generateCommandId();
    if (this.queuedMessages) {
      this.queuedMessages.push({
        resolve: () => this.sendMessage(message, message.command_id),
      });
      return;
    }

    this._sendMessage(message);
  }

  sendMessagePromise(message: Message, commandId: number | null = null) {
    return new Promise<any>((resolve, reject) => {
      if (this.queuedMessages) {
        this.queuedMessages!.push({
          reject,
          resolve: async () => {
            try {
              resolve(await this.sendMessagePromise(message));
            } catch (err) {
              reject(err);
            }
          },
        });
        return;
      }

      message.command_id = commandId || this._generateCommandId();
      this.commands.set(message.command_id, { resolve, reject });
      this._sendMessage(message);
    });
  }

  private async subscribe<EventType>(
    callback: (message: EventType) => void,
    subMessage:
      | messages.SubscribeEventMessage
      | messages.SubscribeStatesMessage,
    unsubMessage: (subscription: number) => Message,
    resubscribe = true,
  ): Promise<SubscriptionUnsubscribe> {
    if (this.queuedMessages) {
      await new Promise((resolve, reject) => {
        this.queuedMessages!.push({ resolve, reject });
      });
    }
    let subscription: SubscribeEventCommmandInFlight<any>;

    await new Promise((resolve, reject) => {
      const commandId = this._generateCommandId();

      subscription = {
        resolve,
        reject,
        callback,
        subscribe:
          resubscribe === true
            ? () =>
                this.subscribe(callback, subMessage, unsubMessage, resubscribe)
            : undefined,
        unsubscribe: async () => {
          if (this.connected) {
            await this.sendMessagePromise(unsubMessage(commandId));
          }
          this.commands.delete(commandId);
          if (this.oldSubscriptions) {
            // Delete from old subscriptions when disconnected so we don't resubscribe
            this.oldSubscriptions.delete(commandId);
          }
        },
      };

      this.commands.set(commandId, subscription);
      try {
        this.sendMessage(subMessage, commandId);
      } catch (err) {
        // Socket is closing
      }
    });
    return () => subscription.unsubscribe();
  }

  async subscribeEvent<EventType>(
    event: string,
    callback: (message: EventType) => void,
    resubscribe = true,
  ): Promise<SubscriptionUnsubscribe> {
    if (this.queuedMessages) {
      await new Promise((resolve, reject) => {
        this.queuedMessages!.push({ resolve, reject });
      });
    }
    if (DEBUG) {
      console.debug("Subscribing to event", event);
    }
    const unsub = await this.subscribe(
      callback,
      messages.subscribeEvent(event),
      (subscription) => messages.unsubscribeEvent(subscription),
      resubscribe,
    );
    return unsub;
  }

  async subscribeStates(
    callback: (message: types.StateChangedEvent) => void,
    entity_id?: string,
    entity_ids?: string[],
    resubscribe = true,
  ): Promise<SubscriptionUnsubscribe> {
    if (this.queuedMessages) {
      await new Promise((resolve, reject) => {
        this.queuedMessages!.push({ resolve, reject });
      });
    }
    if (DEBUG) {
      console.debug("Subscribing to states for ", entity_id || entity_ids);
    }
    const unsub = await this.subscribe(
      callback,
      messages.subscribeStates(entity_id, entity_ids),
      (subscription) => messages.unsubscribeStates(subscription),
      resubscribe,
    );
    return unsub;
  }
}
