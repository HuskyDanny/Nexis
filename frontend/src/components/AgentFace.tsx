import { useEffect, useMemo, useRef, useState } from "react";

interface AgentFaceProps {
  size?: number;
  className?: string;
}

/**
 * Soft gradient blob face — tracks cursor with whole face movement,
 * gradient color shifts based on cursor angle, eyes blink naturally.
 */
export function AgentFace({ size = 120, className = "" }: AgentFaceProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [cursor, setCursor] = useState({ x: 0, y: 0, angle: 0 });
  const [blinkPhase, setBlinkPhase] = useState(0);

  // Cursor tracking — compute offset and angle
  useEffect(() => {
    function handleMouseMove(e: MouseEvent) {
      if (!ref.current) return;
      const rect = ref.current.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = e.clientX - cx;
      const dy = e.clientY - cy;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const maxShift = size * 0.08;
      const scale = Math.min(dist / 300, 1);
      const angle = Math.atan2(dy, dx) * (180 / Math.PI);
      setCursor({
        x: (dx / (dist || 1)) * maxShift * scale,
        y: (dy / (dist || 1)) * maxShift * scale,
        angle,
      });
    }
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, [size]);

  // Natural blinking
  useEffect(() => {
    let timeout: ReturnType<typeof setTimeout>;
    function scheduleBlink() {
      const delay = 2500 + Math.random() * 4500;
      timeout = setTimeout(() => {
        setBlinkPhase(1);
        setTimeout(() => setBlinkPhase(2), 60);
        setTimeout(() => setBlinkPhase(3), 120);
        setTimeout(() => {
          setBlinkPhase(0);
          scheduleBlink();
        }, 200);
      }, delay);
    }
    scheduleBlink();
    return () => clearTimeout(timeout);
  }, []);

  const eyeScaleY = useMemo(() => {
    switch (blinkPhase) {
      case 1:
        return 0.3;
      case 2:
        return 0.05;
      case 3:
        return 0.5;
      default:
        return 1;
    }
  }, [blinkPhase]);

  // Color shifts based on cursor angle
  const hueShift = cursor.angle; // -180 to 180
  const color1 = `hsl(${220 + hueShift * 0.15}, 80%, 82%)`; // blue-ish
  const color2 = `hsl(${260 + hueShift * 0.2}, 70%, 78%)`; // lavender
  const color3 = `hsl(${290 + hueShift * 0.15}, 65%, 85%)`; // pink

  const s = size;
  const r = s / 2;
  const eyeY = -s * 0.04;
  const eyeSpacing = s * 0.13;
  const dotR = s * 0.028;

  // Eye offset is slightly more than face offset for parallax
  const eyeX = cursor.x * 1.3;
  const eyeYOff = cursor.y * 1.3;

  return (
    <div
      ref={ref}
      className={className}
      style={{
        width: s,
        height: s,
        position: "relative",
        borderRadius: "50%",
        overflow: "visible",
      }}
    >
      {/* Primary gradient blob — color shifts with cursor */}
      <div
        style={{
          position: "absolute",
          inset: -s * 0.2,
          borderRadius: "50%",
          background: `radial-gradient(ellipse at ${45 + cursor.x * 0.1}% ${45 + cursor.y * 0.1}%, ${color1} 0%, ${color2} 45%, ${color3} 70%, transparent 100%)`,
          filter: `blur(${s * 0.18}px)`,
          animation: "blobRotate 10s ease-in-out infinite",
          opacity: 0.9,
          transition: "background 0.3s ease",
        }}
      />
      {/* Secondary blob */}
      <div
        style={{
          position: "absolute",
          inset: -s * 0.12,
          borderRadius: "50%",
          background: `radial-gradient(ellipse at ${55 - cursor.x * 0.08}% ${50 - cursor.y * 0.08}%, ${color2} 0%, ${color1} 40%, ${color3} 70%, transparent 90%)`,
          filter: `blur(${s * 0.2}px)`,
          animation: "blobRotate 14s ease-in-out infinite reverse",
          opacity: 0.7,
          transition: "background 0.3s ease",
        }}
      />

      {/* Face SVG — whole face shifts toward cursor */}
      <svg
        viewBox={`${-r} ${-r} ${s} ${s}`}
        width={s}
        height={s}
        style={{
          position: "relative",
          zIndex: 1,
          transform: `translate(${cursor.x}px, ${cursor.y}px)`,
          transition: "transform 0.15s ease-out",
        }}
      >
        {/* Left eyebrow — small arc */}
        <path
          d={`M ${-eyeSpacing - s * 0.045} ${eyeY - s * 0.065} A ${s * 0.05} ${s * 0.05} 0 0 1 ${-eyeSpacing + s * 0.045} ${eyeY - s * 0.065}`}
          fill="none"
          stroke="white"
          strokeWidth={s * 0.02}
          strokeLinecap="round"
          style={{ filter: "drop-shadow(0 0 3px rgba(255,255,255,0.7))" }}
        />
        {/* Right eyebrow — small arc */}
        <path
          d={`M ${eyeSpacing - s * 0.045} ${eyeY - s * 0.065} A ${s * 0.05} ${s * 0.05} 0 0 1 ${eyeSpacing + s * 0.045} ${eyeY - s * 0.065}`}
          fill="none"
          stroke="white"
          strokeWidth={s * 0.02}
          strokeLinecap="round"
          style={{ filter: "drop-shadow(0 0 3px rgba(255,255,255,0.7))" }}
        />

        {/* Left eye — parallax offset */}
        <ellipse
          cx={-eyeSpacing + eyeX * 0.3}
          cy={eyeY + eyeYOff * 0.3}
          rx={dotR}
          ry={dotR * eyeScaleY}
          fill="white"
          style={{
            filter: "drop-shadow(0 0 4px rgba(255,255,255,0.9))",
            transition: "ry 0.06s ease",
          }}
        />
        {/* Right eye — parallax offset */}
        <ellipse
          cx={eyeSpacing + eyeX * 0.3}
          cy={eyeY + eyeYOff * 0.3}
          rx={dotR}
          ry={dotR * eyeScaleY}
          fill="white"
          style={{
            filter: "drop-shadow(0 0 4px rgba(255,255,255,0.9))",
            transition: "ry 0.06s ease",
          }}
        />

        {/* Nose — angular L-shape */}
        <path
          d={`M ${s * 0.01} ${-s * 0.02} L ${s * 0.01} ${s * 0.04} L ${s * 0.045} ${s * 0.04}`}
          fill="none"
          stroke="white"
          strokeWidth={s * 0.018}
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ filter: "drop-shadow(0 0 3px rgba(255,255,255,0.6))" }}
        />
      </svg>
    </div>
  );
}
