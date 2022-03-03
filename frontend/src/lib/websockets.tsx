import React from "react";
import { toast } from "react-toastify";

import * as messages from "lib/messages";
import * as types from "lib/types";

const connectedToastId = "connectedToastId";
const connectingToastId = "connectingToastId";
const connectionLostToastId = "connectionLostToastId";

type Events = "connected" | "disconnected";
export type EventListener = (conn: Connection, eventData?: any) => void;

export interface Message {
  command_id?: number;
  type: string;
  [key: string]: any;
}

type WebSocketEventResponse = {
  command_id: number;
  type: "event";
  event: types.Event;
};

type WebSocketResultResponse = {
  command_id: number;
  type: "result";
  success: true;
  result: any;
};

type WebSocketResultErrorResponse = {
  command_id: number;
  type: "result";
  success: false;
  error: {
    code: string;
    message: string;
  };
};

type WebSocketResponse =
  | WebSocketEventResponse
  | WebSocketResultResponse
  | WebSocketResultErrorResponse;

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

export class Connection {
  socket: WebSocket | null = null;

  reconnectTimer: NodeJS.Timeout | null = null;

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

  async connect() {
    if (this.socket) {
      return;
    }

    const wsURL = `${
      window.location.protocol === "https:" ? "wss://" : "ws://"
    }${location.host}/websocket`;
    console.log(wsURL);
    this.socket = new WebSocket(wsURL);

    if (!this.reconnectTimer) {
      setTimeout(() => {
        this.connectingToast();
      }, 1000);
    }

    this._handleOpen = this._handleOpen.bind(this);
    this._handleMessage = this._handleMessage.bind(this);
    this._handleClose = this._handleClose.bind(this);
    this.socket.addEventListener("open", this._handleOpen);
    this.socket.addEventListener("message", this._handleMessage);
    this.socket.addEventListener("close", this._handleClose);
  }

  private _generateCommandId(): number {
    return ++this.commandId;
  }

  private _handleOpen(_event: any) {
    console.log("Connection opened");
    this.commandId = 0;
    if (this.reconnectTimer) {
      toast("Connected to server!", {
        toastId: connectedToastId,
        type: toast.TYPE.INFO,
        autoClose: 5000,
        pauseOnFocusLoss: false,
      });
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    setTimeout(() => {
      toast.dismiss(connectingToastId);
      toast.dismiss(connectionLostToastId);
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
        }
      );
    }

    const queuedMessages = this.queuedMessages;
    if (queuedMessages) {
      this.queuedMessages = undefined;
      for (const queuedMsg of queuedMessages) {
        queuedMsg.resolve();
      }
    }

    this.fireEvent("connected");
  }

  private _handleMessage(event: any) {
    const message: WebSocketResponse = JSON.parse(event.data);
    console.debug("Received ", message);

    const command_info = this.commands.get(message.command_id);

    switch (message.type) {
      case "event":
        if (command_info) {
          command_info.callback((message as WebSocketEventResponse).event);
        } else {
          console.warn(
            `Received event for unknown subscription ${message.command_id}. Unsubscribing.`
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
      default:
        console.warn("Unhandled message", message);
    }
  }

  private _handleClose = async () => {
    if (!this.reconnectTimer) {
      console.debug("Connection closed");
      if (this.socket) {
        this.socket.removeEventListener("close", this._handleClose);
        this.socket.removeEventListener("message", this._handleMessage);
      }

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

      this.queuedMessages = [];
      toast.dismiss(connectingToastId);
      toast("Connection lost, reconnecting", {
        toastId: connectionLostToastId,
        type: toast.TYPE.ERROR,
        autoClose: false,
      });
    }

    this.reconnectTimer = setTimeout(async () => {
      this.socket = null;
      console.debug("Reconnecting to server...");
      await this.connect();
    }, 5000);
    this.fireEvent("disconnected");
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
      callback(this, eventData)
    );
  }

  connectingToast(): void {
    if (this.socket && this.socket.readyState === WebSocket.CONNECTING) {
      toast("Connecting to server", {
        toastId: connectingToastId,
        type: toast.TYPE.INFO,
        autoClose: false,
      });
    }
  }

  private _sendMessage(message: Message) {
    console.log("Sending", message);
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

  async subscribeEvent<EventType>(
    event: string,
    callback: (message: EventType) => void,
    resubscribe = true
  ) {
    if (this.queuedMessages) {
      await new Promise((resolve, reject) => {
        this.queuedMessages!.push({ resolve, reject });
      });
    }
    console.log("Subscribing to", event);

    let subscription: SubscribeEventCommmandInFlight<any>;

    await new Promise((resolve, reject) => {
      const commandId = this._generateCommandId();

      subscription = {
        resolve,
        reject,
        callback,
        subscribe:
          resubscribe === true
            ? () => this.subscribeEvent(event, callback, resubscribe)
            : undefined,
        unsubscribe: async () => {
          await this.sendMessagePromise(messages.unsubscribeEvent(commandId));
          this.commands.delete(commandId);
        },
      };

      this.commands.set(commandId, subscription);
      this.sendMessage(messages.subscribeEvent(event), commandId);
    });
    return () => subscription.unsubscribe();
  }

  async getCameras(): Promise<types.Cameras> {
    const response = await this.sendMessagePromise(messages.getCameras());
    const json = await JSON.parse(response);
    return json;
  }

  async subscribeCameras(cameraCallback: (camera: types.Camera) => void) {
    const storedCameraCallback = cameraCallback;
    const _cameraCallback = (message: types.CameraRegisteredEvent) => {
      storedCameraCallback(message.data);
    };
    const subscription = await this.subscribeEvent(
      "camera_registered",
      _cameraCallback,
      true
    );
    return subscription;
  }

  async getConfig(): Promise<string> {
    const response = await this.sendMessagePromise(messages.getConfig());
    return response.config;
  }

  async saveConfig(
    config: string
  ): Promise<
    WebSocketResultResponse["result"] | WebSocketResultErrorResponse["error"]
  > {
    return this.sendMessagePromise(messages.saveConfig(config));
  }
}
