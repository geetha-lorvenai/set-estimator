import Link from "next/link";
import type { Estimate } from "@/lib/types";
import { formatDate, formatMoney, humanize } from "@/lib/format";

interface Props {
  items: Estimate[];
  total: number;
  loading: boolean;
  error: string | null;
  activeId?: string;
  onRetry: () => void;
}

export default function EstimateLog({ items, total, loading, error, activeId, onRetry }: Props) {
  return (
    <section className="log" aria-labelledby="log-title">
      <div className="log__head">
        <h2 id="log-title" className="section-title">
          Estimate log
        </h2>
        {!loading && !error && <span className="muted">{total} saved</span>}
      </div>

      {loading && <p className="muted">Loading saved estimates…</p>}
      {error && (
        <div className="notice notice--error" role="alert">
          <p>{error}</p>
          <button type="button" className="chip" onClick={onRetry}>
            Try again
          </button>
        </div>
      )}
      {!loading && !error && items.length === 0 && (
        <p className="muted">No estimates yet. Submit a work order above and it will be saved here.</p>
      )}

      {items.length > 0 && (
        <div className="table-wrap">
          <table className="log__table">
            <thead>
              <tr>
                <th scope="col">Set</th>
                <th scope="col">Request</th>
                <th scope="col">Complexity</th>
                <th scope="col">Created</th>
                <th scope="col" className="num">Total</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id} className={e.id === activeId ? "is-active" : undefined}>
                  <td>
                    <Link href={`/estimates/${e.id}`}>{e.set_name ?? "Untitled set"}</Link>
                  </td>
                  <td className="log__request" title={e.raw_input}>
                    {e.raw_input}
                  </td>
                  <td>{humanize(e.complexity)}</td>
                  <td className="nowrap">{formatDate(e.created_at)}</td>
                  <td className="num">{formatMoney(e.summary.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
