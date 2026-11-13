import { useCallback, useEffect, useRef, useState } from "react";
import { defaultSettings, londonToday, type DailyBonus, type NetTimeSettings } from "./policy";
import { addBonus, loadBonus, loadSettings, saveBonus, saveSettings, SETTINGS_KEY } from "./storage";

const REFRESH_MS = 30_000;

/** Settings live only in this browser's localStorage in this version. */
export function useNetTime() {
  const [settings, setSettings] = useState<NetTimeSettings>(defaultSettings);
  const [bonus, setBonusState] = useState<DailyBonus | null>(null);
  const [hasSaved, setHasSaved] = useState(false);
  const [ready, setReady] = useState(false);
  const [today, setToday] = useState<string>("");
  const todayRef = useRef("");

  /** Re-read the UK date and drop any bonus not belonging to it. Returns the current date. */
  const refreshToday = useCallback(() => {
    const t = londonToday();
    if (t !== todayRef.current) { todayRef.current = t; setToday(t); }
    const b = loadBonus(localStorage);
    if (b && b.date !== t) { saveBonus(localStorage, null); setBonusState(null); }
    else setBonusState((prev) => (prev?.date === b?.date && prev?.minutes === b?.minutes ? prev : b));
    return t;
  }, []);

  useEffect(() => {
    setSettings(loadSettings(localStorage));
    setHasSaved(localStorage.getItem(SETTINGS_KEY) !== null);
    refreshToday();
    setReady(true);
    const onVis = () => { if (document.visibilityState === "visible") refreshToday(); };
    window.addEventListener("focus", refreshToday);
    document.addEventListener("visibilitychange", onVis);
    const id = window.setInterval(refreshToday, REFRESH_MS);
    return () => {
      window.removeEventListener("focus", refreshToday);
      document.removeEventListener("visibilitychange", onVis);
      window.clearInterval(id);
    };
  }, [refreshToday]);

  const save = useCallback((s: NetTimeSettings) => {
    saveSettings(localStorage, s); setSettings(s); setHasSaved(true);
  }, []);

  /** Adds time for the UK date at the moment of the click (not a cached date). */
  const addTimeToday = useCallback((minutes: number) => {
    const t = refreshToday();
    const next = addBonus(loadBonus(localStorage), t, minutes);
    saveBonus(localStorage, next); setBonusState(next);
  }, [refreshToday]);

  const clearBonus = useCallback(() => { saveBonus(localStorage, null); setBonusState(null); }, []);

  return { settings, save, bonus, addTimeToday, clearBonus, hasSaved, ready, today, refreshToday };
}
