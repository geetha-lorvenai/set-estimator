import Link from "next/link";
import type { Estimate } from "@/lib/types";
import { formatDate, formatMoney, formatPercent, formatQty, humanize, unitLabel } from "@/lib/format";

const CATEGORY_ORDER = ["structural", "finish", "electrical", "scenic"];

export default function EstimateSheet({ estimate, showLink = false }: { estimate: Estimate; showLink?: boolean }) {
  const { summary } = estimate;
  const categories = Object.entries(estimate.material_cost_by_category).sort(
    ([a], [b]) => CATEGORY_ORDER.indexOf(a) - CATEGORY_ORDER.indexOf(b),
  );

  return (
    <article className="sheet" aria-labelledby={`sheet-${estimate.id}`}>
      <header className="slate">
        <div className="slate__sticks" aria-hidden="true" />
        <div className="slate__body">
          <dl className="slate__fields">
            <div>
              <dt>Set</dt>
              <dd id={`sheet-${estimate.id}`}>{estimate.set_name ?? "Untitled set"}</dd>
            </div>
            <div>
              <dt>Complexity</dt>
              <dd>
                {humanize(estimate.complexity)}
                {!estimate.complexity_detected && <span className="slate__note"> (default)</span>}
              </dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{formatDate(estimate.created_at)}</dd>
            </div>
            <div>
              <dt>Reference</dt>
              <dd className="slate__ref">{estimate.id.slice(0, 8)}</dd>
            </div>
          </dl>
          <div className="slate__total">
            <span>Total</span>
            <strong>{formatMoney(summary.total)}</strong>
          </div>
        </div>
      </header>

      <blockquote className="sheet__request">{estimate.raw_input}</blockquote>

      {estimate.warnings.length > 0 && (
        <div className="notice notice--warn">
          <p>Check before you sign off:</p>
          <ul>
            {estimate.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      <section className="sheet__section">
        <h3>Materials</h3>
        {estimate.materials.length === 0 ? (
          <p className="muted">No materials in this request.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Item</th>
                  <th scope="col">Category</th>
                  <th scope="col" className="num">Qty</th>
                  <th scope="col" className="num">Unit price</th>
                  <th scope="col" className="num">Amount</th>
                </tr>
              </thead>
              <tbody>
                {estimate.materials.map((m) => (
                  <tr key={m.material}>
                    <td>{humanize(m.material)}</td>
                    <td>
                      <span className={`cat cat--${m.category}`}>{humanize(m.category)}</span>
                    </td>
                    <td className="num">
                      {formatQty(m.quantity)} {unitLabel(m.unit, m.quantity)}
                    </td>
                    <td className="num">{formatMoney(m.unit_price)}</td>
                    <td className="num">{formatMoney(m.line_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {categories.length > 0 && summary.material_cost > 0 && (
          <div className="split" aria-label="Material cost by category">
            <div className="split__bar">
              {categories.map(([cat, value]) => (
                <span
                  key={cat}
                  className={`split__seg cat-bg--${cat}`}
                  style={{ flexGrow: value }}
                  title={`${humanize(cat)}: ${formatMoney(value)}`}
                />
              ))}
            </div>
            <ul className="split__legend">
              {categories.map(([cat, value]) => (
                <li key={cat}>
                  <span className={`swatch cat-bg--${cat}`} aria-hidden="true" />
                  {humanize(cat)} <span className="num">{formatMoney(value)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section className="sheet__section">
        <h3>Labor</h3>
        {estimate.labor.length === 0 ? (
          <p className="muted">No crew in this request.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Role</th>
                  <th scope="col" className="num">Crew</th>
                  <th scope="col" className="num">Days</th>
                  <th scope="col" className="num">Day rate</th>
                  <th scope="col" className="num">Amount</th>
                </tr>
              </thead>
              <tbody>
                {estimate.labor.map((l) => (
                  <tr key={l.role}>
                    <td>{humanize(l.role)}</td>
                    <td className="num">{l.workers}</td>
                    <td className="num">{formatQty(l.days)}</td>
                    <td className="num">{formatMoney(l.daily_rate)}</td>
                    <td className="num">{formatMoney(l.line_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="sheet__section">
        <h3>Cost summary</h3>
        <dl className="ledger">
          <div>
            <dt>Materials</dt>
            <dd>{formatMoney(summary.material_cost)}</dd>
          </div>
          <div>
            <dt>
              Complexity surcharge ({humanize(summary.complexity)}, {formatPercent(summary.complexity_surcharge_rate)} of
              materials)
            </dt>
            <dd>+ {formatMoney(summary.complexity_surcharge)}</dd>
          </div>
          <div className={summary.bulk_discount_applied ? "" : "ledger__off"}>
            <dt>
              Bulk discount ({formatPercent(summary.bulk_discount_rate)} when materials exceed{" "}
              {formatMoney(summary.bulk_discount_threshold)})
              {!summary.bulk_discount_applied && " — not reached"}
            </dt>
            <dd>− {formatMoney(summary.bulk_discount)}</dd>
          </div>
          <div>
            <dt>Labor</dt>
            <dd>+ {formatMoney(summary.labor_cost)}</dd>
          </div>
          <div className="ledger__total">
            <dt>Total</dt>
            <dd>{formatMoney(summary.total)}</dd>
          </div>
        </dl>
      </section>

      {showLink && (
        <p className="sheet__link">
          <Link href={`/estimates/${estimate.id}`}>Open this estimate on its own page</Link>
        </p>
      )}
    </article>
  );
}
