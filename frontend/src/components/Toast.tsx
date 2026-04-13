import { useEffect, useState } from "react";
import { type ToastItem, dismiss, subscribe } from "../lib/toast";

export function ToastContainer() {
  const [items, setItems] = useState<ToastItem[]>([]);

  useEffect(() => {
    return subscribe(setItems);
  }, []);

  if (items.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {items.map((item) => (
        <div
          key={item.id}
          className="px-4 py-3 rounded-lg text-sm shadow-lg backdrop-blur-md cursor-pointer animate-slide-in"
          style={{
            background: "rgba(15, 20, 35, 0.9)",
            borderLeft: `3px solid ${item.type === "error" ? "#ef4444" : "#22c55e"}`,
            color: "#d4d4d8",
          }}
          onClick={() => dismiss(item.id)}
        >
          {item.message}
        </div>
      ))}
    </div>
  );
}
