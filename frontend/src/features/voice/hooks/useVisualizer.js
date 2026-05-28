import { useRef, useCallback } from "react";

export const COLORS = {
  idle:       { bg: "#0d1f4a", glow: "37,99,235"   },
  speaking:   { bg: "#3b0f0f", glow: "220,38,38"   },
  processing: { bg: "#2a1a00", glow: "217,119,6"   },
  replying:   { bg: "#1a0d3b", glow: "168,85,247"  },
};

export function useVisualizer({ canvasRef, liveBgRef, getState }) {
  const micCtxRef        = useRef(null);
  const analyserRef      = useRef(null);
  const replyAnalyserRef = useRef(null);
  const rafIdRef         = useRef(null);
  const smoothedVolRef   = useRef(0);

  const getColor = useCallback(
    () => COLORS[getState()] ?? COLORS.idle,
    [getState]
  );

  const resizeCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    canvas.width  = canvas.offsetWidth  * devicePixelRatio;
    canvas.height = canvas.offsetHeight * devicePixelRatio;
    ctx.scale(devicePixelRatio, devicePixelRatio);
  }, [canvasRef]);

  const drawWave = useCallback(
    (timeData) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      const W = canvas.offsetWidth;
      const H = canvas.offsetHeight;
      const c = getColor();
      const smoothedVol = smoothedVolRef.current;

      ctx.clearRect(0, 0, W, H);

      const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
      bgGrad.addColorStop(0,   "rgba(0,0,0,0)");
      bgGrad.addColorStop(0.5, `rgba(${c.glow},${0.06 + smoothedVol * 0.12})`);
      bgGrad.addColorStop(1,   "rgba(0,0,0,0)");
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, W, H);

      for (const mirror of [1, -1]) {
        const grad = ctx.createLinearGradient(0, 0, W, 0);
        grad.addColorStop(0,    `rgba(${c.glow},0)`);
        grad.addColorStop(0.15, `rgba(${c.glow},${0.6 + smoothedVol * 0.4})`);
        grad.addColorStop(0.85, `rgba(${c.glow},${0.6 + smoothedVol * 0.4})`);
        grad.addColorStop(1,    `rgba(${c.glow},0)`);

        ctx.beginPath();
        ctx.strokeStyle = grad;
        ctx.lineWidth   = 1.5 + smoothedVol * 1.5;
        ctx.shadowColor = `rgba(${c.glow},${0.4 + smoothedVol * 0.5})`;
        ctx.shadowBlur  = 8 + smoothedVol * 16;

        const sliceW = W / timeData.length;
        let x = 0;
        for (let i = 0; i < timeData.length; i++) {
          const v = timeData[i] / 128.0 - 1;
          const y = H / 2 + mirror * v * (H * 0.38);
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
          x += sliceW;
        }
        ctx.stroke();
        ctx.shadowBlur = 0;
      }
    },
    [canvasRef, getColor]
  );

  const drawIdle = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.offsetWidth;
    const H = canvas.offsetHeight;
    const c = COLORS.idle;

    ctx.clearRect(0, 0, W, H);
    const grad = ctx.createLinearGradient(0, 0, W, 0);
    grad.addColorStop(0,    `rgba(${c.glow},0)`);
    grad.addColorStop(0.15, `rgba(${c.glow},0.25)`);
    grad.addColorStop(0.85, `rgba(${c.glow},0.25)`);
    grad.addColorStop(1,    `rgba(${c.glow},0)`);

    ctx.beginPath();
    ctx.strokeStyle = grad;
    ctx.lineWidth   = 1;
    ctx.shadowColor = `rgba(${c.glow},0.2)`;
    ctx.shadowBlur  = 6;
    ctx.moveTo(0, H / 2);
    ctx.lineTo(W, H / 2);
    ctx.stroke();
    ctx.shadowBlur = 0;
  }, [canvasRef]);

  const updateBg = useCallback(() => {
    const liveBg = liveBgRef.current;
    if (!liveBg) return;
    const c = getColor();
    const smoothedVol = smoothedVolRef.current;
    liveBg.style.background = `radial-gradient(ellipse at 50% 80%, ${c.bg}cc ${smoothedVol * 30}%, #0a0a0a 70%)`;
  }, [liveBgRef, getColor]);

  const start = useCallback(
    (stream) => {
      const micCtx = new AudioContext();
      micCtxRef.current = micCtx;
      const src = micCtx.createMediaStreamSource(stream);
      const analyser = micCtx.createAnalyser();
      analyser.fftSize = 1024;
      src.connect(analyser);
      analyserRef.current = analyser;

      const timeData = new Uint8Array(analyser.fftSize);
      const freqData = new Uint8Array(analyser.frequencyBinCount);

      function tick() {
        const active = replyAnalyserRef.current || analyserRef.current;
        active.getByteTimeDomainData(timeData);
        active.getByteFrequencyData(freqData);

        const avg = freqData.slice(2, 14).reduce((a, b) => a + b, 0) / 12;
        smoothedVolRef.current +=
          (Math.min(avg / 150, 1) - smoothedVolRef.current) * 0.15;

        drawWave(timeData);
        updateBg();
        rafIdRef.current = requestAnimationFrame(tick);
      }
      tick();
    },
    [drawWave, updateBg]
  );

  const stop = useCallback(() => {
    if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
    drawIdle();
    const liveBg = liveBgRef.current;
    if (liveBg)
      liveBg.style.background = `radial-gradient(ellipse at 50% 70%, ${COLORS.idle.bg} 0%, #0a0a0a 70%)`;
    if (micCtxRef.current) {
      micCtxRef.current.close();
      micCtxRef.current = null;
    }
  }, [drawIdle, liveBgRef]);

  const attachReplySource = useCallback((audioContext, bufferSource) => {
    const replyAnalyser = audioContext.createAnalyser();
    replyAnalyser.fftSize = 1024;
    bufferSource.connect(replyAnalyser);
    replyAnalyserRef.current = replyAnalyser;
    return replyAnalyser;
  }, []);

  const detachReplySource = useCallback(() => {
    replyAnalyserRef.current = null;
  }, []);

  const getMicContext = useCallback(() => micCtxRef.current, []);

  return {
    start,
    stop,
    resizeCanvas,
    drawIdle,
    attachReplySource,
    detachReplySource,
    getMicContext,
  };
}
