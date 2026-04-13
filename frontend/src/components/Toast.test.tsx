import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastContainer } from "./Toast";
import { toast } from "../lib/toast";

describe("ToastContainer", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    // Advance timers to clear any pending auto-dismiss timeouts
    act(() => vi.advanceTimersByTime(10_000));
    vi.useRealTimers();
  });

  it("renders nothing when there are no toasts", () => {
    const { container } = render(<ToastContainer />);
    expect(container.innerHTML).toBe("");
  });

  it("shows an error toast", () => {
    render(<ToastContainer />);
    act(() => toast.error("Something failed"));

    expect(screen.getByText("Something failed")).toBeInTheDocument();
  });

  it("shows a success toast", () => {
    render(<ToastContainer />);
    act(() => toast.success("Operation completed"));

    expect(screen.getByText("Operation completed")).toBeInTheDocument();
  });

  it("auto-dismisses after 5 seconds", () => {
    render(<ToastContainer />);
    act(() => toast.success("Temporary message"));

    expect(screen.getByText("Temporary message")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(5_000));

    expect(screen.queryByText("Temporary message")).not.toBeInTheDocument();
  });

  it("dismisses on click", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ToastContainer />);
    act(() => toast.error("Click me away"));

    const toastEl = screen.getByText("Click me away");
    expect(toastEl).toBeInTheDocument();

    await user.click(toastEl);

    expect(screen.queryByText("Click me away")).not.toBeInTheDocument();
  });
});
