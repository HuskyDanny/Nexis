import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ErrorBoundary from "./ErrorBoundary";

function ProblemChild({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error("boom");
  return <div>child content</div>;
}

describe("ErrorBoundary", () => {
  it("renders children when no error occurs", () => {
    render(
      <ErrorBoundary>
        <div>hello world</div>
      </ErrorBoundary>,
    );

    expect(screen.getByText("hello world")).toBeInTheDocument();
  });

  it("shows fallback UI when a child throws", () => {
    // Suppress React error boundary console.error noise
    vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <ProblemChild shouldThrow />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.queryByText("child content")).not.toBeInTheDocument();

    vi.restoreAllMocks();
  });

  it("displays the error message in fallback", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <ProblemChild shouldThrow />
      </ErrorBoundary>,
    );

    expect(screen.getByText("boom")).toBeInTheDocument();

    vi.restoreAllMocks();
  });

  it("resets error state when 'Try again' is clicked", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const user = userEvent.setup();

    // Use a mutable ref to control throwing
    let shouldThrow = true;

    function ConditionalChild() {
      if (shouldThrow) throw new Error("boom");
      return <div>recovered</div>;
    }

    const { rerender } = render(
      <ErrorBoundary>
        <ConditionalChild />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();

    // Stop throwing before clicking retry
    shouldThrow = false;

    await user.click(screen.getByText("Try again"));

    // Force re-render so the non-throwing child appears
    rerender(
      <ErrorBoundary>
        <ConditionalChild />
      </ErrorBoundary>,
    );

    expect(screen.getByText("recovered")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();

    vi.restoreAllMocks();
  });
});
