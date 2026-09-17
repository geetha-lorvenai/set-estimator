"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import EstimateSheet from "@/components/EstimateSheet";
import { ApiError, getEstimate } from "@/lib/api";
import type { Estimate } from "@/lib/types";

export default function EstimatePage() {
  const { id } = useParams<{ id: string }>();
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getEstimate(id)
      .then((e) => !cancelled && setEstimate(e))
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && (err.status === 404 || err.status === 422)) {
          setError("This estimate doesn't exist. It may have been mistyped.");
        } else {
          setError(err instanceof ApiError ? err.message : "Could not load this estimate.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <div className="detail">
      <p>
        <Link href="/" className="backlink">
          Back to all estimates
        </Link>
      </p>
      {error && (
        <div className="notice notice--error" role="alert">
          <p>{error}</p>
        </div>
      )}
      {!error && !estimate && <p className="muted">Loading estimate…</p>}
      {estimate && <EstimateSheet estimate={estimate} />}
    </div>
  );
}
