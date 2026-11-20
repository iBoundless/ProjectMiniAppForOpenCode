import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./Button";
import { ConfirmDialog } from "./ConfirmDialog";
import { formatCost, formatTime, statusLabel } from "./format";
import { Skeleton } from "./Skeleton";
import { ToastProvider } from "./Toasts";
import { useToast } from "./toast-context";

test("confirm dialog calls confirm and cancel", async () => {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  const { rerender } = render(
    <ConfirmDialog open={false} title="Удалить?" onConfirm={onConfirm} onCancel={onCancel} />,
  );
  expect(screen.queryByRole("dialog")).toBeNull();
  rerender(
    <ConfirmDialog open title="Удалить?" confirmLabel="Да" onConfirm={onConfirm} onCancel={onCancel}>
      Нельзя отменить
    </ConfirmDialog>,
  );
  expect(screen.getByRole("dialog", { name: "Удалить?" })).toBeInTheDocument();
  await userEvent.click(screen.getByText("Да"));
  expect(onConfirm).toHaveBeenCalledOnce();
  await userEvent.click(screen.getByText("Отмена"));
  expect(onCancel).toHaveBeenCalledOnce();
});

test("button loading disables it", () => {
  render(<Button loading>Go</Button>);
  expect(screen.getByRole("button")).toBeDisabled();
});

test("skeleton renders lines", () => {
  render(<Skeleton lines={2} />);
  expect(screen.getByTestId("skeleton").children).toHaveLength(2);
});

function ToastButton() {
  const toast = useToast();
  return <button onClick={() => toast.error("Сбой")}>show</button>;
}

test("toast appears and disappears", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  render(
    <ToastProvider timeout={1000}>
      <ToastButton />
    </ToastProvider>,
  );
  await userEvent.click(screen.getByText("show"));
  expect(screen.getByRole("status")).toHaveTextContent("Сбой");
  act(() => {
    vi.advanceTimersByTime(1500);
  });
  expect(screen.queryByRole("status")).toBeNull();
  vi.useRealTimers();
});

test("format helpers", () => {
  const now = 10_000_000_000_000;
  expect(formatTime(now - 5_000, now)).toBe("только что");
  expect(formatTime(now - 5 * 60_000, now)).toBe("5 мин назад");
  expect(formatTime(now - 3 * 3_600_000, now)).toBe("3 ч назад");
  expect(formatTime(null)).toBe("");
  expect(formatCost(0)).toBe("");
  expect(formatCost(0.1234)).toBe("$0.123");
  expect(statusLabel("busy")).toBe("работает");
  expect(statusLabel("weird")).toBe("weird");
});
