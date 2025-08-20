import { act } from "@testing-library/react";
import { renderHookWithContext } from "tests/utils/renderWithContext";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useDebouncedTemplateRender } from "hooks/useDebouncedTemplateRender";
import { renderTemplate } from "lib/commands";

vi.mock("lib/commands", () => ({ renderTemplate: vi.fn() }));

const mockConnection = {} as any;

const DEBOUNCE = 500;

const flushMicrotasks = async () => {
  await Promise.resolve();
  await Promise.resolve();
};

describe("useDebouncedTemplateRender", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    (renderTemplate as any).mockReset();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not call renderTemplate when template is empty", () => {
    renderHookWithContext(() => useDebouncedTemplateRender("", DEBOUNCE), {
      connection: mockConnection,
    });
    expect(renderTemplate).not.toHaveBeenCalled();
  });

  it("debounces rapid changes and only calls once", async () => {
    (renderTemplate as any).mockResolvedValue("OK");
    const { rerender, result } = renderHookWithContext(
      ({ template }) => useDebouncedTemplateRender(template, DEBOUNCE),
      { initialProps: { template: "a" }, connection: mockConnection },
    );

    act(() => {
      rerender({ template: "ab" });
      rerender({ template: "abc" });
    });

    expect(renderTemplate).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(DEBOUNCE);
      await flushMicrotasks();
    });

    expect(renderTemplate).toHaveBeenCalledTimes(1);
    expect(result.current.result).toBe("OK");
    expect(result.current.error).toBeNull();
  });

  it("manual renderNow triggers immediately", async () => {
    (renderTemplate as any).mockResolvedValue("MANUAL");
    const { result } = renderHookWithContext(
      () => useDebouncedTemplateRender("hello", DEBOUNCE),
      { connection: mockConnection },
    );

    await act(async () => {
      await result.current.renderNow();
    });

    expect(renderTemplate).toHaveBeenCalledTimes(1);
    expect(result.current.result).toBe("MANUAL");
  });

  it("sets loading correctly during async call", async () => {
    let resolveFn: (v: string) => void = () => {};
    (renderTemplate as any).mockImplementation(
      () =>
        new Promise((res) => {
          resolveFn = res as any;
        }),
    );

    const { result } = renderHookWithContext(
      () => useDebouncedTemplateRender("abc", DEBOUNCE),
      { connection: mockConnection },
    );

    await act(async () => {
      vi.advanceTimersByTime(DEBOUNCE);
      // Don't flush yet; still pending promise
    });
    expect(result.current.loading).toBe(true);

    await act(async () => {
      resolveFn("DONE");
      await flushMicrotasks();
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.result).toBe("DONE");
  });

  it("handles error path", async () => {
    (renderTemplate as any).mockRejectedValue(new Error("Testing"));
    const { result } = renderHookWithContext(
      () => useDebouncedTemplateRender("err", DEBOUNCE),
      { connection: mockConnection },
    );

    await act(async () => {
      vi.advanceTimersByTime(DEBOUNCE);
      await flushMicrotasks();
    });

    expect(result.current.error).toBe("Testing");
    expect(result.current.result).toBe("");
  });

  it("clear resets result and error", async () => {
    (renderTemplate as any).mockResolvedValue("VALUE");
    const { result } = renderHookWithContext(
      () => useDebouncedTemplateRender("x", DEBOUNCE),
      { connection: mockConnection },
    );

    await act(async () => {
      vi.advanceTimersByTime(DEBOUNCE);
      await flushMicrotasks();
    });
    expect(result.current.result).toBe("VALUE");

    act(() => {
      result.current.clear();
    });

    expect(result.current.result).toBe("");
    expect(result.current.error).toBeNull();
  });

  it("does not call renderTemplate when no connection present", async () => {
    (renderTemplate as any).mockResolvedValue("SHOULD_NOT");
    renderHookWithContext(() => useDebouncedTemplateRender("text", DEBOUNCE));
    await act(async () => {
      vi.advanceTimersByTime(DEBOUNCE);
      await flushMicrotasks();
    });
    expect(renderTemplate).not.toHaveBeenCalled();
  });
});
