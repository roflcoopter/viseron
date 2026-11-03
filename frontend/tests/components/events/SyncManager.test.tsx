import { act, render } from "@testing-library/react";
import Hls from "hls.js";
import { afterEach, describe, expect, it, vi } from "vitest";

import SyncManager from "components/events/SyncManager";
import { useHlsStore } from "components/events/utils";

describe("SyncManager", () => {
  const players: Hls[] = [];

  const createPlayer = () => {
    const hls = new Hls();
    // Stands in for the error recovery that the player components register
    hls.on(Hls.Events.ERROR, vi.fn());
    players.push(hls);
    return { current: hls };
  };

  afterEach(() => {
    useHlsStore.setState({ hlsRefs: [] });
    players.splice(0).forEach((hls) => hls.destroy());
  });

  it("keeps the other error listeners of a player when another player is added", () => {
    const player = createPlayer();
    const otherListeners = player.current.listeners(Hls.Events.ERROR);
    useHlsStore.setState({ hlsRefs: [player] });
    render(<SyncManager>{null}</SyncManager>);

    act(() => {
      useHlsStore.setState({ hlsRefs: [player, createPlayer()] });
    });

    const listeners = player.current.listeners(Hls.Events.ERROR);
    expect(listeners).toEqual(expect.arrayContaining(otherListeners));
    expect(listeners).toHaveLength(otherListeners.length + 1);
  });

  it("removes only its own error listeners when unmounted", () => {
    const player = createPlayer();
    const otherListeners = player.current.listeners(Hls.Events.ERROR);
    useHlsStore.setState({ hlsRefs: [player] });
    const { unmount } = render(<SyncManager>{null}</SyncManager>);

    unmount();

    expect(player.current.listeners(Hls.Events.ERROR)).toEqual(otherListeners);
  });
});
