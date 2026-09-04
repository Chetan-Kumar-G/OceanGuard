/** A short two-tone alert chime, synthesized with the Web Audio API - no
 * external audio asset needed. Used when the timeline player reaches the
 * first confirmed detection for an event. */
let ctx: AudioContext | null = null;

function getContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const Ctor = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  if (!ctx) ctx = new Ctor();
  return ctx;
}

function beep(audioCtx: AudioContext, startAt: number, freq: number, duration: number) {
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type = "sine";
  osc.frequency.setValueAtTime(freq, startAt);
  gain.gain.setValueAtTime(0, startAt);
  gain.gain.linearRampToValueAtTime(0.18, startAt + 0.02);
  gain.gain.linearRampToValueAtTime(0, startAt + duration);
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.start(startAt);
  osc.stop(startAt + duration + 0.02);
}

export function playAlertSound() {
  const audioCtx = getContext();
  if (!audioCtx) return;
  if (audioCtx.state === "suspended") void audioCtx.resume();
  const now = audioCtx.currentTime;
  // two rising beeps, like a radar/sonar alert
  beep(audioCtx, now, 880, 0.16);
  beep(audioCtx, now + 0.22, 1175, 0.22);
}
