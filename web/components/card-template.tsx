"use client";

import { forwardRef, useImperativeHandle } from "react";

export type CardVariant = "dark" | "light";

interface CardTemplateProps {
  userName: string;
  variant: CardVariant;
  onTextureReady: (dataUrl: string) => void;
  city?: string;
  date?: string;
}

export interface CardTemplateRef {
  captureTexture: () => Promise<void>;
  exportCard: () => void;
}

const CANVAS_SIZE = 1376;
const RIGHT_X = CANVAS_SIZE / 2 - 55; // matches the card.glb UV used by the template

// Draw a Coherent "member card" entirely in canvas (no third-party art).
function drawCard(ctx: CanvasRenderingContext2D, userName: string, variant: CardVariant) {
  const dark = variant === "dark";
  const bg = dark ? "#0a0a0b" : "#f4f4f5";
  const fg = dark ? "#ffffff" : "#0a0a0a";
  const dim = dark ? "#8a8a90" : "#6b6b70";
  const line = dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)";

  // Background
  const grad = ctx.createLinearGradient(0, 0, 0, CANVAS_SIZE);
  grad.addColorStop(0, dark ? "#111113" : "#ffffff");
  grad.addColorStop(1, bg);
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

  // Subtle grid pattern
  ctx.strokeStyle = line;
  ctx.lineWidth = 2;
  for (let x = 0; x <= CANVAS_SIZE; x += 64) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, CANVAS_SIZE); ctx.stroke();
  }
  for (let y = 0; y <= CANVAS_SIZE; y += 64) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(CANVAS_SIZE, y); ctx.stroke();
  }

  // Faint large mark (three waves ≋) centered
  ctx.fillStyle = dark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)";
  ctx.font = 'normal 520px "Geist", system-ui, sans-serif';
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("≋", CANVAS_SIZE / 2, CANVAS_SIZE / 2 - 40);

  ctx.textAlign = "right";
  ctx.textBaseline = "middle";

  // Brand (top)
  ctx.fillStyle = fg;
  ctx.font = '600 72px "Geist", system-ui, sans-serif';
  ctx.fillText("Coherent", RIGHT_X, 150);

  ctx.fillStyle = dim;
  ctx.font = 'normal 40px "Geist Mono", monospace';
  ctx.fillText("MEMBER CARD", RIGHT_X, 212);

  // Name (lower area)
  const displayName = (userName || "Your name").toUpperCase();
  ctx.fillStyle = fg;
  ctx.font = 'normal 64px "Geist Mono", monospace';
  ctx.fillText(displayName, RIGHT_X, CANVAS_SIZE - 400);

  ctx.fillStyle = dim;
  ctx.font = 'normal 34px "Geist Mono", monospace';
  ctx.fillText("LPL FINANCIAL", RIGHT_X, CANVAS_SIZE - 340);
}

const CardTemplate = forwardRef<CardTemplateRef, CardTemplateProps>(
  ({ userName, variant, onTextureReady }, ref) => {
    const captureTexture = async () => {
      const canvas = document.createElement("canvas");
      canvas.width = CANVAS_SIZE;
      canvas.height = CANVAS_SIZE;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      drawCard(ctx, userName, variant);
      onTextureReady(canvas.toDataURL("image/png"));
    };

    const exportCard = () => {
      const canvas = document.createElement("canvas");
      canvas.width = CANVAS_SIZE;
      canvas.height = CANVAS_SIZE - 334;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      drawCard(ctx, userName, variant);
      const link = document.createElement("a");
      link.download = `samepage-card-${userName || "member"}.png`;
      link.href = canvas.toDataURL("image/png", 1.0);
      link.click();
    };

    useImperativeHandle(ref, () => ({ captureTexture, exportCard }));
    return null;
  }
);

CardTemplate.displayName = "CardTemplate";
export default CardTemplate;
