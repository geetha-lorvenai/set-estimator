"use client";

import { useState } from "react";
import { ApiError, createEstimate } from "@/lib/api";
import type { Estimate } from "@/lib/types";

const EXAMPLES: { label: string; text: string }[] = [
  {
    label: "Living room",
    text: "Build a moderate complexity living room set with 10 sheets of drywall, 20 litres of paint, 30sqm of flooring, 2 scenic backdrops, and 2 days of carpenter and painter labor",
  },
  {
    label: "Kitchen",
    text: "We need a complex kitchen set: drywall x 12, paint 15L, 25 square metres of flooring, three prop furniture pieces and 4 electrical points. 2 carpenters for 3 days and an electrician for 1 day.",
  },
  {
    label: "Western saloon",
    text: "Moderately complex western saloon set with 101 sheets of timber, six rolls of wallpaper, 2 backdrops, a scenic artist for 2 days and 3 carpenter days.",
  },
];

interface Props {
  onCreated: (estimate: Estimate) => void;
}

export default function EstimateForm({ onCreated }: Props) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const trimmed = text.trim();
  const canSubmit = trimmed.length >= 3 && !busy;

  async function submit() {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      onCreated(await createEstimate(trimmed));
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError("Something went wrong. Try again.", 0));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="order"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <h2 className="section-title">Work order</h2>
      <label htmlFor="request" className="order__label">
        Describe the set, the materials and the crew
      </label>
      <textarea
        id="request"
        className="order__input"
        rows={8}
        maxLength={2000}
        value={text}
        placeholder="e.g. A simple bedroom set with 8 sheets of plywood, 6 rolls of wallpaper and a carpenter for 2 days"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
            e.preventDefault();
            void submit();
          }
        }}
      />
      <div className="order__meta">
        <span>Ctrl + Enter to submit</span>
        <span>{text.length} / 2000</span>
      </div>

      <div className="order__examples">
        <span className="order__examples-label">Fill with an example:</span>
        {EXAMPLES.map((ex) => (
          <button key={ex.label} type="button" className="chip" onClick={() => setText(ex.text)}>
            {ex.label}
          </button>
        ))}
      </div>

      <button type="submit" className="button" disabled={!canSubmit}>
        {busy ? "Estimating…" : "Estimate cost"}
      </button>

      {error && (
        <div className="notice notice--error" role="alert">
          <p>{error.message}</p>
          {error.hints.length > 0 && (
            <ul>
              {error.hints.map((h) => (
                <li key={h}>{h}</li>
              ))}
            </ul>
          )}
          {error.status === 422 && (
            <p className="notice__help">
              Include quantities with catalogue items (timber, drywall, paint, wallpaper, flooring, electrical points,
              scenic backdrops, prop furniture) or crew with days (carpenter, painter, electrician, scenic artist).
            </p>
          )}
        </div>
      )}
    </form>
  );
}
