import { fireEvent, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { API_BASE_URL } from "tests/mocks/handlers";
import { server } from "tests/mocks/server";
import { renderWithContext } from "tests/utils/renderWithContext";
import { describe, expect, test, vi } from "vitest";

import StorageCleanup from "pages/settings/StorageCleanup";

describe("StorageCleanup", () => {
  test("lists cameras that are no longer configured", async () => {
    renderWithContext(<StorageCleanup />);

    expect(await screen.findByText("camera_3")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("2.5 MiB")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  test("shows a message when nothing is orphaned", async () => {
    server.use(
      http.get(`${API_BASE_URL}/cameras/orphaned`, () =>
        HttpResponse.json({ cameras: [] }, { status: 200 }),
      ),
    );
    renderWithContext(<StorageCleanup />);

    expect(
      await screen.findByText(/No orphaned cameras found/),
    ).toBeInTheDocument();
  });

  test("asks for confirmation before deleting", async () => {
    const onDelete = vi.fn();
    server.use(
      http.delete(
        `${API_BASE_URL}/cameras/orphaned/:camera_identifier`,
        ({ params }) => {
          onDelete(params.camera_identifier);
          return HttpResponse.json(
            {
              camera_identifier: params.camera_identifier,
              file_count: 12,
              size_bytes: 2621440,
              database_rows: 4,
              directories: [],
            },
            { status: 200 },
          );
        },
      ),
    );
    renderWithContext(<StorageCleanup />);

    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(await screen.findByText("Delete camera_3?")).toBeInTheDocument();
    expect(onDelete).not.toHaveBeenCalled();

    const dialog = await screen.findByRole("dialog");
    fireEvent.click(
      screen
        .getAllByRole("button", { name: "Delete" })
        .find((button) => dialog.contains(button))!,
    );

    await waitFor(() => expect(onDelete).toHaveBeenCalledWith("camera_3"));
  });

  test("explains why the server will not guess", async () => {
    server.use(
      http.get(`${API_BASE_URL}/cameras/orphaned`, () =>
        HttpResponse.json(
          { status: 503, error: "Components failed to set up: ffmpeg." },
          { status: 503 },
        ),
      ),
    );
    renderWithContext(<StorageCleanup />);

    expect(
      await screen.findByText("Components failed to set up: ffmpeg."),
    ).toBeInTheDocument();
  });

  test("shows an error when the request fails", async () => {
    server.use(
      http.get(`${API_BASE_URL}/cameras/orphaned`, () =>
        HttpResponse.json({ status: 500, error: "boom" }, { status: 500 }),
      ),
    );
    renderWithContext(<StorageCleanup />);

    expect(
      await screen.findByText("Error loading orphaned cameras"),
    ).toBeInTheDocument();
  });
});
