type ToastType = "error" | "success";

export interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
}

export type Listener = (toasts: ToastItem[]) => void;

let nextId = 0;
let toasts: ToastItem[] = [];
const listeners = new Set<Listener>();

function notify() {
  for (const listener of listeners) {
    listener([...toasts]);
  }
}

function addToast(message: string, type: ToastType) {
  const id = nextId++;
  toasts = [...toasts, { id, message, type }];
  notify();

  setTimeout(() => {
    toasts = toasts.filter((t) => t.id !== id);
    notify();
  }, 5000);
}

export function dismiss(id: number) {
  toasts = toasts.filter((t) => t.id !== id);
  notify();
}

export function subscribe(listener: Listener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export const toast = {
  error: (message: string) => addToast(message, "error"),
  success: (message: string) => addToast(message, "success"),
};
