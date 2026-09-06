import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { AttractScreen } from "./screens/AttractScreen";
import { SelectScreen } from "./screens/SelectScreen";
import { ReplayScreen } from "./screens/ReplayScreen";
import { loadDrawing, loadManifest } from "./lib/data";
import type { ShowcaseDrawing, ShowcaseManifest } from "./lib/types";

type Phase = "attract" | "select" | "replay";

// Idle timeout: after this much inactivity on any non-attract screen,
// the kiosk returns to ATTRACT so the booth loops unattended.
// `?noidle` in the URL disables it (handy for QA / a staffed booth).
const IDLE_MS = 45_000;
const IDLE_DISABLED =
  typeof window !== "undefined" && window.location.search.includes("noidle");

export function App() {
  const [phase, setPhase] = useState<Phase>("attract");
  const [manifest, setManifest] = useState<ShowcaseManifest | null>(null);
  const [active, setActive] = useState<ShowcaseDrawing | null>(null);
  const [loading, setLoading] = useState(false);
  const idleTimer = useRef<number | null>(null);

  // Load the manifest once.
  useEffect(() => {
    loadManifest().then(setManifest).catch((e) => console.error("manifest", e));
  }, []);

  const goAttract = useCallback(() => {
    setPhase("attract");
    setActive(null);
  }, []);

  // Idle watchdog — only armed off the attract screen.
  const bumpIdle = useCallback(() => {
    if (IDLE_DISABLED) return;
    if (idleTimer.current) window.clearTimeout(idleTimer.current);
    if (phase === "attract") return;
    idleTimer.current = window.setTimeout(goAttract, IDLE_MS);
  }, [phase, goAttract]);

  useEffect(() => {
    bumpIdle();
    return () => {
      if (idleTimer.current) window.clearTimeout(idleTimer.current);
    };
  }, [phase, bumpIdle]);

  const handleSelect = useCallback(async (key: string) => {
    setLoading(true);
    try {
      const d = await loadDrawing(key);
      setActive(d);
      setPhase("replay");
    } catch (e) {
      console.error("loadDrawing", e);
      goAttract();
    } finally {
      setLoading(false);
    }
  }, [goAttract]);

  return (
    <div
      className="relative h-full w-full overflow-hidden bg-canvas text-fg-primary"
      onPointerDown={bumpIdle}
      onPointerMove={bumpIdle}
    >
      <AnimatePresence mode="wait">
        {phase === "attract" && (
          <AttractScreen key="attract" onStart={() => setPhase("select")} />
        )}
        {phase === "select" && (
          <SelectScreen
            key="select"
            manifest={manifest}
            loading={loading}
            onPick={handleSelect}
            onBack={goAttract}
          />
        )}
        {phase === "replay" && active && (
          <ReplayScreen
            key={`replay-${active.drawing_id}`}
            drawing={active}
            onRestart={goAttract}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
