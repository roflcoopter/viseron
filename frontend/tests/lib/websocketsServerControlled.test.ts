import { beforeEach, describe, expect, test, vi } from "vitest";

import { Toast } from "hooks/UseToast";
import { Connection } from "lib/websockets";

const PARAMS = { camera_identifier: "camera1", start: 0, end: 3600 };

class FakeSocket {
  OPEN = 1;

  readyState = 1;

  send = vi.fn();

  close = vi.fn();

  addEventListener = vi.fn();

  removeEventListener = vi.fn();

  sent(): any[] {
    return this.send.mock.calls.map(([data]) => JSON.parse(data));
  }

  lastSent(): any {
    const sent = this.sent();
    return sent[sent.length - 1];
  }
}

const toast = {
  info: vi.fn(),
  success: vi.fn(),
  warning: vi.fn(),
  error: vi.fn(),
  dismiss: vi.fn(),
  update: vi.fn(),
};

const setup = () => {
  const connection = new Connection(toast as unknown as Toast);
  const socket = new FakeSocket();
  connection.socket = socket as unknown as WebSocket;
  connection.queuedMessages = undefined;
  // Never reconnect, _handleClose would otherwise schedule a new socket
  connection.closeRequested = true;
  const receive = (message: object) =>
    (connection as any)._handleMessage({ data: JSON.stringify(message) });
  return { connection, socket, receive };
};

// Starts a render and acknowledges it, returning its cancel function
const startRender = async (
  connection: Connection,
  socket: FakeSocket,
  receive: (message: object) => void,
) => {
  const callback = vi.fn();
  const errorCallback = vi.fn();
  const promise = connection.renderTimelapse(PARAMS, callback, errorCallback);
  await vi.waitFor(() => expect(socket.send).toHaveBeenCalled());
  const commandId = socket.lastSent().command_id;
  receive({ command_id: commandId, type: "result", success: true });
  const cancel = await promise;
  return { callback, errorCallback, commandId, cancel };
};

const status = (commandId: number, result: object) => ({
  command_id: commandId,
  type: "subscription_result",
  success: true,
  result,
});

describe("server controlled subscriptions", () => {
  beforeEach(() => {
    Object.values(toast).forEach((fn) => fn.mockClear());
  });

  test("sends the render command", async () => {
    const { connection, socket, receive } = setup();

    await startRender(connection, socket, receive);

    expect(socket.sent()).toEqual([
      { type: "render_timelapse", ...PARAMS, command_id: 1 },
    ]);
  });

  test("forwards every result until the server cancels", async () => {
    const { connection, socket, receive } = setup();
    const { callback, commandId } = await startRender(
      connection,
      socket,
      receive,
    );

    receive(status(commandId, { status: "encoding" }));
    receive(status(commandId, { status: "done", filename: "f", token: "t" }));
    receive({ command_id: commandId, type: "cancel_subscription" });
    receive(status(commandId, { status: "encoding" }));

    expect(callback.mock.calls).toEqual([
      [{ status: "encoding" }],
      [{ status: "done", filename: "f", token: "t" }],
    ]);
    expect(connection.commands.has(commandId)).toBe(false);
  });

  test.each([
    { name: "acknowledged", response: { success: true } },
    {
      name: "already finished",
      response: {
        success: false,
        error: { code: "not_found", message: "Not found" },
      },
    },
  ])(
    "cancel sends unsubscribe_event and drops later results when $name",
    async ({ response }) => {
      const { connection, socket, receive } = setup();
      const { callback, commandId, cancel } = await startRender(
        connection,
        socket,
        receive,
      );

      const cancelled = cancel();
      // Results already on their way when the cancel was sent are ignored
      receive(status(commandId, { status: "encoding" }));
      const unsubscribe = socket.lastSent();
      receive({
        command_id: unsubscribe.command_id,
        type: "result",
        ...response,
      });
      await cancelled;

      expect(unsubscribe).toMatchObject({
        type: "unsubscribe_event",
        subscription: commandId,
      });
      expect(callback).not.toHaveBeenCalled();
      expect(connection.commands.has(commandId)).toBe(false);
    },
  );

  test("cancel does nothing once the server has finished", async () => {
    const { connection, socket, receive } = setup();
    const { commandId, cancel } = await startRender(
      connection,
      socket,
      receive,
    );
    receive({ command_id: commandId, type: "cancel_subscription" });
    socket.send.mockClear();

    await cancel();

    expect(socket.send).not.toHaveBeenCalled();
  });

  test("disconnect calls the error callback", async () => {
    const { connection, socket, receive } = setup();
    const { errorCallback, commandId } = await startRender(
      connection,
      socket,
      receive,
    );

    await (connection as any)._handleClose();

    expect(errorCallback).toHaveBeenCalledWith({
      command_id: commandId,
      type: "subscription_result",
      success: false,
      error: { code: "connection_lost", message: "Connection lost" },
    });
    expect(connection.oldSubscriptions?.has(commandId)).toBe(false);
  });

  test("disconnect before the command is acknowledged rejects it", async () => {
    const { connection, socket } = setup();
    const errorCallback = vi.fn();
    const promise = connection.renderTimelapse(PARAMS, vi.fn(), errorCallback);
    await vi.waitFor(() => expect(socket.send).toHaveBeenCalled());

    await (connection as any)._handleClose();

    await expect(promise).rejects.toEqual({
      code: "connection_lost",
      message: "Connection lost",
    });
    expect(errorCallback).toHaveBeenCalledOnce();
  });

  test("disconnect keeps regular subscriptions for resubscribing", async () => {
    const { connection, socket, receive } = setup();
    const promise = connection.subscribeEvent("event", vi.fn());
    await vi.waitFor(() => expect(socket.send).toHaveBeenCalled());
    const commandId = socket.lastSent().command_id;
    receive({ command_id: commandId, type: "result", success: true });
    await promise;

    await (connection as any)._handleClose();

    expect(connection.oldSubscriptions?.has(commandId)).toBe(true);
  });
});
