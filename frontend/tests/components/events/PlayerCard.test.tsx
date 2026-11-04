import { fireEvent, screen } from "@testing-library/react";
import { renderWithContext } from "tests/utils/renderWithContext";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PlayerCard } from "components/events/PlayerCard";
import {
  LIVE_EDGE_DELAY,
  useHlsStore,
  useReferencePlayerStore,
} from "components/events/utils";

vi.mock("components/events/SyncManager", () => ({
  default: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("components/player/grid/PlayerGrid", () => ({
  PlayerGrid: () => null,
}));

vi.mock("components/player/CustomControls", () => ({
  CustomControls: ({
    onJumpBackward,
    onJumpForward,
    onLiveClick,
    onPlaybackSpeedChange,
    onVolumeChange,
    onMuteToggle,
  }: Record<string, (...args: unknown[]) => void>) => (
    <>
      <button type="button" onClick={onJumpBackward}>
        jump backward
      </button>
      <button type="button" onClick={onJumpForward}>
        jump forward
      </button>
      <button type="button" onClick={onLiveClick}>
        live
      </button>
      <button type="button" onClick={() => onPlaybackSpeedChange(2)}>
        speed
      </button>
      <button
        type="button"
        onClick={() => onVolumeChange(new Event("change"), 50)}
      >
        volume
      </button>
      <button type="button" onClick={onMuteToggle}>
        mute
      </button>
    </>
  ),
}));

describe("PlayerCard", () => {
  afterEach(() => {
    useHlsStore.setState({ hlsRefs: [] });
    useReferencePlayerStore.setState({ isMuted: true });
  });

  it.each([
    { control: "jump backward", property: "currentTime", expected: 90 },
    { control: "jump forward", property: "currentTime", expected: 110 },
    {
      control: "live",
      property: "currentTime",
      expected: 200 - LIVE_EDGE_DELAY,
    },
    { control: "speed", property: "playbackRate", expected: 2 },
    { control: "volume", property: "volume", expected: 0.5 },
    { control: "mute", property: "muted", expected: false },
  ])(
    "$control reaches the players after one without a media element",
    ({ control, property, expected }) => {
      const media = {
        currentTime: 100,
        duration: 200,
        playbackRate: 1,
        volume: 1,
        muted: true,
        paused: true,
      };
      useReferencePlayerStore.setState({ isMuted: true });
      useHlsStore.setState({
        hlsRefs: [
          // Refs are registered before and after their Hls instance is alive
          { current: null },
          { current: { media: null } },
          { current: { media } },
        ] as never,
      });
      renderWithContext(<PlayerCard />);

      fireEvent.click(screen.getByRole("button", { name: control }));

      expect(media[property as keyof typeof media]).toBe(expected);
    },
  );
});
