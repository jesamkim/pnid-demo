import { motion } from "framer-motion";
import { Hand, Sparkles } from "lucide-react";

interface Props {
  onStart: () => void;
}

// Deterministic floating particles (no Math.random — stable across renders).
const PARTICLES = Array.from({ length: 18 }, (_, i) => ({
  left: (i * 53) % 100,
  top: (i * 37) % 100,
  size: 2 + (i % 4),
  dur: 7 + (i % 6),
  delay: (i % 9) * 0.6,
}));

/**
 * ATTRACT — the unattended idle screen. A refined ambient backdrop
 * (engineering grid + gradient-mesh glow + drifting particles) sets a
 * high-tech tone without literal drawings. Any tap advances to SELECT.
 */
export function AttractScreen({ onStart }: Props) {
  return (
    <motion.div
      className="absolute inset-0 flex flex-col items-center justify-center"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.6 }}
      onClick={onStart}
    >
      {/* Refined ambient backdrop */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {/* Engineering grid */}
        <div
          className="absolute inset-0 opacity-[0.06]"
          style={{
            backgroundImage:
              "linear-gradient(var(--accent) 1px, transparent 1px), linear-gradient(90deg, var(--accent) 1px, transparent 1px)",
            backgroundSize: "64px 64px",
            maskImage:
              "radial-gradient(ellipse 90% 80% at 50% 45%, black 30%, transparent 80%)",
            WebkitMaskImage:
              "radial-gradient(ellipse 90% 80% at 50% 45%, black 30%, transparent 80%)",
          }}
        />
        {/* Gradient-mesh glows */}
        <div
          className="absolute -left-[10%] top-[8%] h-[60vh] w-[60vh] rounded-full blur-[120px]"
          style={{ background: "color-mix(in srgb, var(--accent) 22%, transparent)" }}
        />
        <div
          className="absolute -right-[8%] bottom-[6%] h-[55vh] w-[55vh] rounded-full blur-[120px]"
          style={{ background: "color-mix(in srgb, #a78bfa 16%, transparent)" }}
        />
        <div
          className="absolute left-1/2 top-1/2 h-[70vh] w-[70vh] -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{
            background:
              "radial-gradient(circle, color-mix(in srgb, var(--accent) 14%, transparent) 0%, transparent 62%)",
          }}
        />
        {/* Drifting particles */}
        {PARTICLES.map((p, i) => (
          <span
            key={i}
            className="absolute rounded-full bg-accent"
            style={{
              left: `${p.left}%`,
              top: `${p.top}%`,
              width: p.size,
              height: p.size,
              opacity: 0.25,
              boxShadow: "0 0 8px var(--accent)",
              animation: `sc-float ${p.dur}s ease-in-out ${p.delay}s infinite`,
            }}
          />
        ))}
      </div>

      <div className="relative z-10 flex flex-col items-center text-center">
        <motion.div
          className="mb-4 flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-semibold backdrop-blur"
          style={{
            border: "1px solid color-mix(in srgb, var(--aws-orange) 45%, transparent)",
            background: "color-mix(in srgb, var(--aws-orange) 14%, transparent)",
            color: "var(--aws-orange)",
          }}
          initial={{ y: -12, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          <Sparkles size={16} />
          AWS Bedrock AgentCore · Multi-Agent
        </motion.div>

        <motion.h1
          className="max-w-[18ch] text-balance text-6xl font-bold leading-[1.08] tracking-tight"
          initial={{ y: 16, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.35, duration: 0.7 }}
        >
          P&ID 도면을
          <br />
          <span className="text-accent">AI로 이해합니다</span>
        </motion.h1>

        <motion.p
          className="mt-5 max-w-[30ch] text-balance text-lg text-fg-secondary"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
        >
          장비 · 밸브 · 계장 · 라인 · 연결 관계를
          <br />
          AWS Bedrock AgentCore 기반의 에이전트로 추출합니다
        </motion.p>

        {/* Pulsing touch affordance */}
        <motion.button
          className="relative mt-14 flex items-center gap-3 rounded-full bg-accent px-9 py-5 text-xl font-semibold text-accent-fg shadow-glow"
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.8, type: "spring", stiffness: 220 }}
          whileTap={{ scale: 0.95 }}
        >
          <span
            className="absolute inset-0 -z-10 rounded-full border-2 border-accent"
            style={{ animation: "sc-pulse-ring 2.4s ease-out infinite" }}
          />
          <Hand size={24} />
          터치하여 시작
        </motion.button>
      </div>
    </motion.div>
  );
}
