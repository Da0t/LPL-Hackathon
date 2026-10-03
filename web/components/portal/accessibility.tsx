"use client";
import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
} from "react";
import Link from "next/link";
import {
  Volume2,
  Square,
  Type,
  Contrast,
  Phone,
  ShieldCheck,
} from "lucide-react";

type Preferences = { large: boolean; contrast: boolean; autoRead: boolean };
type SpeechState = "idle" | "loading" | "playing";
const Context = createContext<{
  prefs: Preferences;
  toggle: (key: keyof Preferences) => void;
  speak: (text: string) => Promise<void>;
  stop: () => void;
  state: SpeechState;
  error: string;
} | null>(null);
export const useAccessibility = () => useContext(Context)!;
export function AccessibilityProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [prefs, setPrefs] = useState<Preferences>({
    large: false,
    contrast: false,
    autoRead: false,
  });
  const [state, setState] = useState<SpeechState>("idle"),
    [error, setError] = useState("");
  const audio = useRef<HTMLAudioElement | null>(null),
    url = useRef<string | null>(null),
    request = useRef<AbortController | null>(null),
    generation = useRef(0);
  useEffect(() => {
    try {
      const saved = JSON.parse(
        localStorage.getItem("coherent-accessibility") || "{}",
      );
      setPrefs({
        large: saved.large === true,
        contrast: saved.contrast === true,
        autoRead: saved.autoRead === true,
      });
    } catch {}
    return () => {
      request.current?.abort();
      audio.current?.pause();
      if (url.current) URL.revokeObjectURL(url.current);
    };
  }, []);
  const stop = useCallback(() => {
    generation.current++;
    request.current?.abort();
    audio.current?.pause();
    audio.current = null;
    if (url.current) URL.revokeObjectURL(url.current);
    url.current = null;
    setState("idle");
  }, []);
  async function speak(text: string) {
    stop();
    setError(text.length > 2500 ? "This is a long message. Reading its first part; the full text stays on screen." : "");
    if (!text.trim()) return;
    const seq = generation.current,
      controller = new AbortController();
    request.current = controller;
    setState("loading");
    try {
      const response = await fetch("/api/portal/speech", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.slice(0, 2500) }),
        signal: controller.signal,
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(
          error.message || "Read-aloud is unavailable. You can keep typing.",
        );
      }
      const blob = await response.blob();
      if (seq !== generation.current) return;
      url.current = URL.createObjectURL(blob);
      const player = new Audio(url.current);
      audio.current = player;
      player.onended = () => {
        if (seq === generation.current) stop();
      };
      player.onerror = () => {
        if (seq === generation.current) {
          stop();
          setError("Audio could not play. Your text is still available.");
        }
      };
      await player.play();
      if (seq === generation.current) setState("playing");
    } catch (e: any) {
      if (seq !== generation.current || e.name === "AbortError") return;
      stop();
      setError(
        e.name === "NotAllowedError"
          ? "Choose Read aloud to start audio in this browser."
          : e.message,
      );
    }
  }
  function toggle(key: keyof Preferences) {
    setPrefs((p) => {
      const next = { ...p, [key]: !p[key] };
      try {
        localStorage.setItem("coherent-accessibility", JSON.stringify(next));
      } catch {}
      return next;
    });
    if (key === "autoRead") stop();
  }
  return (
    <Context.Provider value={{ prefs, toggle, speak, stop, state, error }}>
      <div
        className={`accessibility-scope ${prefs.large ? "large-text" : ""} ${prefs.contrast ? "strong-contrast" : ""}`}
      >
        {children}
      </div>
    </Context.Provider>
  );
}
export function AccessibilityToolbar() {
  const { prefs, toggle, state, stop, error } = useAccessibility();
  return (
    <div
      className="accessibility-toolbar"
      role="region"
      aria-label="Reading and accessibility preferences"
    >
      <div className="accessibility-controls">
        <button aria-pressed={prefs.large} onClick={() => toggle("large")}>
          <Type size={19} />
          Larger text
        </button>
        <button
          aria-pressed={prefs.contrast}
          onClick={() => toggle("contrast")}
        >
          <Contrast size={19} />
          Stronger contrast
        </button>
        <button
          aria-pressed={prefs.autoRead}
          onClick={() => toggle("autoRead")}
        >
          <Volume2 size={19} />
          Read questions aloud
        </button>
        {state !== "idle" && (
          <button onClick={stop}>
            <Square size={17} />
            {state === "loading" ? "Cancel audio" : "Stop reading"}
          </button>
        )}
      </div>
      {error && <p role="status">{error}</p>}
    </div>
  );
}
export function ReadAloudButton({
  text,
  label = "Read aloud",
}: {
  text: string;
  label?: string;
}) {
  const { speak, state, stop } = useAccessibility();
  return (
    <button
      type="button"
      className="portal-secondary read-aloud-button"
      onClick={() => (state !== "idle" ? stop() : speak(text))}
      disabled={!text.trim()}
    >
      <Volume2 size={18} />
      {state !== "idle" ? "Stop reading" : label}
    </button>
  );
}
export function ReassuranceBar() {
  return (
    <div className="reassurance-bar">
      <span>
        <ShieldCheck size={18} />
        No money has moved.
      </span>
      <Link href="/workspace/requests/new?help=person">
        <Phone size={18} />
        Talk to a person
      </Link>
    </div>
  );
}
