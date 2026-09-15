import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithContext } from "tests/utils/renderWithContext";
import { afterEach, describe, expect, test, vi } from "vitest";

import { CameraCard } from "components/camera/CameraCard";

// IntersectionObserver only reports visibility after the first render
const { onScreenStore } = vi.hoisted(() => {
  const listeners = new Set<() => void>();
  return {
    onScreenStore: {
      value: false,
      subscribe(listener: () => void) {
        listeners.add(listener);
        return () => listeners.delete(listener);
      },
      set(value: boolean) {
        this.value = value;
        listeners.forEach((listener) => listener());
      },
    },
  };
});

vi.mock("hooks/UseOnScreen", async () => {
  const { useSyncExternalStore } = await import("react");
  return {
    default: () =>
      useSyncExternalStore(
        (listener: () => void) => onScreenStore.subscribe(listener),
        () => onScreenStore.value,
      ),
  };
});

afterEach(() => {
  onScreenStore.value = false;
});

const renderCameraCard = () =>
  renderWithContext(<CameraCard camera_identifier="camera1" buttons={false} />);

const snapshotSrc = "/api/v1/camera/camera1/snapshot";

describe("CameraCard", () => {
  test("shows a loading indicator before the first snapshot is requested", async () => {
    renderCameraCard();

    expect(
      await screen.findByTestId("camera-snapshot-loading"),
    ).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  test("keeps the loading indicator up until the first snapshot has loaded", async () => {
    const { container } = renderCameraCard();
    await screen.findByText("Camera 1");

    // A load fired while off screen is not the first snapshot
    container.querySelectorAll("img").forEach((img) => fireEvent.load(img));

    act(() => onScreenStore.set(true));

    const snapshot = await screen.findByRole("img");
    await waitFor(() =>
      expect(snapshot).toHaveAttribute(
        "src",
        expect.stringContaining(snapshotSrc),
      ),
    );
    // The snapshot is still in flight, so the spinner has to stay visible.
    expect(screen.getByRole("progressbar")).toBeInTheDocument();

    fireEvent.load(snapshot);

    await waitFor(() =>
      expect(screen.queryByRole("progressbar")).not.toBeInTheDocument(),
    );
  });
});
