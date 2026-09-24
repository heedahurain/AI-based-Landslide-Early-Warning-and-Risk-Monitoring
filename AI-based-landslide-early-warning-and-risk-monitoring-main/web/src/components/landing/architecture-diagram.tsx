"use client";

import { useRef } from "react";
import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";

/**
 * The data flow, drawn on scroll.
 *
 * Source to ingest to feature store to risk engine to alert to channel to
 * acknowledgement. The connectors draw themselves as the section passes
 * through the viewport, using stroke-dashoffset, which animates on the
 * compositor and never triggers layout.
 *
 * The diagram is decorative for sighted readers and redundant for everyone
 * else: the same sequence is available as an ordered list to screen readers.
 */

const STAGES = [
  { id: "source", label: "Sources", detail: "Rainfall, satellite, sensors, citizens" },
  { id: "ingest", label: "Ingest", detail: "Retry, cache, labelled fallback" },
  { id: "features", label: "Feature store", detail: "Hypertables and terrain" },
  { id: "risk", label: "Risk engine", detail: "Physics, empirical, ML, deformation" },
  { id: "alert", label: "Alert", detail: "CAP v1.2, fatigue controls" },
  { id: "channel", label: "Channels", detail: "App, SMS, IVR, push, siren" },
  { id: "ack", label: "Acknowledged", detail: "Escalation and audit" },
] as const;

const BOX_W = 150;
const BOX_H = 62;
const GAP = 42;
const VIEW_W = STAGES.length * BOX_W + (STAGES.length - 1) * GAP;
const VIEW_H = 150;

export function ArchitectureDiagram() {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start 0.85", "center 0.4"],
  });

  // When motion is reduced, the diagram is simply drawn complete.
  const dashOffset = useTransform(scrollYProgress, [0, 1], [1, 0]);
  const progress = reduced ? 0 : dashOffset;

  return (
    <div ref={ref}>
      <ol className="sr-only">
        {STAGES.map((stage) => (
          <li key={stage.id}>
            {stage.label}. {stage.detail}
          </li>
        ))}
      </ol>

      <div className="overflow-x-auto pb-2">
        <svg
          viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
          className="h-auto w-full min-w-[820px]"
          role="presentation"
          focusable="false"
        >
          <defs>
            <linearGradient id="flow" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="var(--sev-cyan-mark)" stopOpacity="0.25" />
              <stop offset="55%" stopColor="var(--sev-cyan-mark)" stopOpacity="0.9" />
              <stop offset="100%" stopColor="var(--sev-red-mark)" stopOpacity="0.9" />
            </linearGradient>
          </defs>

          {STAGES.map((stage, i) => {
            const x = i * (BOX_W + GAP);
            const y = VIEW_H / 2 - BOX_H / 2;
            const isLast = i === STAGES.length - 1;

            return (
              <g key={stage.id}>
                {i > 0 && (
                  <motion.line
                    x1={x - GAP}
                    y1={VIEW_H / 2}
                    x2={x}
                    y2={VIEW_H / 2}
                    stroke="url(#flow)"
                    strokeWidth={2}
                    strokeLinecap="round"
                    pathLength={1}
                    strokeDasharray={1}
                    style={{ strokeDashoffset: progress }}
                  />
                )}

                <rect
                  x={x}
                  y={y}
                  width={BOX_W}
                  height={BOX_H}
                  rx={12}
                  fill="var(--bg-elevated)"
                  stroke={isLast ? "var(--sev-green-outline)" : "var(--border-default)"}
                  strokeWidth={1}
                />
                <text
                  x={x + BOX_W / 2}
                  y={y + 25}
                  textAnchor="middle"
                  fill="var(--fg-primary)"
                  style={{ fontSize: 13, fontWeight: 600 }}
                >
                  {stage.label}
                </text>
                <text
                  x={x + BOX_W / 2}
                  y={y + 44}
                  textAnchor="middle"
                  fill="var(--fg-muted)"
                  style={{ fontSize: 9.5 }}
                >
                  {stage.detail.length > 30 ? `${stage.detail.slice(0, 29)}…` : stage.detail}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
