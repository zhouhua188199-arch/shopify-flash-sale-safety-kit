# Shopify Flash Sale Safety Kit

Open-source profit-floor checklist, discount stacking math calculator (Python), and BFCM rollback playbook for Shopify merchants and ecommerce agencies.

Built to eliminate the three most expensive operational mistakes during weekend sales and Black Friday / Cyber Monday (BFCM): forgotten compare-at rollbacks at 2:00 AM, silent coupon stacking below landed cost, and broken CSV re-imports.

> Prefer instant browser calculators with zero setup? Use our [12 free, no-login Shopify promo and margin tools](https://getsaleguard.com/tools?utm_source=github&utm_medium=repo&utm_campaign=sg_kit) (including the Discount Stack Checker and 30-Second Store Price Audit).

---

## What Is Included

| File | Purpose | How to Use |
| :--- | :--- | :--- |
| `discount_stack_checker.py` | Zero-dependency Python 3 CLI calculator using exact `Decimal` math to detect negative-margin discount stacks and compute break-even floors. | `python3 discount_stack_checker.py --price 100 --cost 62 --sale 25 --promo 15` |
| `bfcm_sale_rollback_checklist.csv` | 15-point pre-launch, launch-verification, and midnight-rollback checklist ready for Notion, Google Sheets, or Excel. | Import directly into Notion Database or Google Sheets |
| `README.md` | Engineering breakdown of Shopify `compare_at_price` failure modes, exact compound stacking formulas, and the 5-point 2:00 AM safety protocol. | Read below or fork for your internal agency SOP |

---

## The 3 Most Common Shopify `compare_at_price` Failure Modes

### 1. Strict Inequality & Variant-Level Inconsistency
Shopify renders a storefront strikethrough price only when `compare_at_price > price` on a specific **variant** (not the parent product).
- If `compare_at_price == price` (for example, `$49.00` and `$49.00`), Shopify suppresses the sale badge silently.
- If a 4-size product has 3 variants updated and 1 variant missed during a Bulk Editor session, collection grids display broken `"From $X"` anchors or drop the sale badge across the card.

### 2. Reverse-Math Drift & Clobbering Pre-Existing Clearance Anchors
A common script mistake is skipping pre-sale snapshots and trying to revert prices via reverse division (`sale_price / (1 - discount)`):
- Suppose a `$50.00` SKU goes 20% off (`$40.00`) and gets rounded to `$39.99`. Reversing it via `$39.99 / 0.80` returns `$49.99`, silently drifting cents across the catalog.
- Worse, SKUs already on permanent clearance (`$90.00 -> $65.00`) lose their original `$90.00` anchor when a naive rollback wipes `compare_at_price` blank across every product.
- **Fix:** Always snapshot the exact pre-sale tuple `(variant_id, price, compare_at_price)` before modifying a single cent.

### 3. Full-Column CSV Overwrites & Unprotected Mid-Sale Edits
Shopify has no native "Undo" button for bulk price edits or CSV imports.
- Re-importing an untouched full-column backup CSV 72 hours after launch with *"Overwrite products with matching handles"* checked can overwrite product descriptions, SEO metadata, or manual price adjustments made mid-campaign.
- If you rely on manual CSV rollbacks, always trim your restore CSV strictly to matching identifiers (`Handle`, `Option1-3 Value`, `Variant SKU`) plus `Variant Price` and `Variant Compare At Price`, and verify every variant after import.

---

## Exact Compound Discount Stacking Math

Stacked discounts on Shopify **compound multiplicatively** rather than adding linearly, while payment gateway fees still take a percentage cut off the remaining gross revenue plus a fixed per-order fee:

```text
Sale_Price      = Retail_Price * (1 - Flash_Sale_Rate)
Effective_Price = Sale_Price   * (1 - Promo_Code_Rate)
Combined_Rate   = 1 - (1 - Flash_Sale_Rate) * (1 - Promo_Code_Rate)

Payment_Fee     = Effective_Price * Fee_Rate + Fixed_Fee
Net_Profit      = Effective_Price - Landed_Cost - Payment_Fee
Net_Margin_Pct  = Net_Profit / Effective_Price
```

### Real-World Margin Trap Example
- **Retail Price:** `$100.00`
- **Landed Cost (COGS + shipping + fulfillment + ad CAC):** `$62.00`
- **Flash Sale Markdown (`compare_at_price` edit):** `25% off` -> `$75.00` (still `$10.52` profit after standard `2.9% + $0.30` fee)
- **Forgotten Email Code (`WELCOME15`) Stacks at Checkout:** extra `15% off` -> **`$63.75`** effective price (`36.25%` combined discount)
- **Payment Fee (`2.9% + $0.30`):** `$2.15`
- **Net Profit per Order:** `$63.75 - $62.00 - $2.15` = **`-$0.40` (RED ALERT: losing money on every order)**

To stay profitable (`Net_Profit >= 0`), the minimum break-even selling price is:

```text
Break_Even_Price = (Landed_Cost + Fixed_Fee) / (1 - Fee_Rate)
```

For `$62.00` landed cost at `2.9% + $0.30`, your hard break-even floor is **`$64.16`**.

---

## Quick Start: Run the Python Stack Checker

Requires Python 3.9+ (standard library only, zero external packages).

### Single SKU Check
```bash
python3 discount_stack_checker.py \
  --price 100 \
  --cost 62 \
  --sale 25 \
  --promo 15 \
  --fee-pct 2.9 \
  --fee-fixed 0.30
```

### Run Built-In BFCM Scenario Matrix
```bash
python3 discount_stack_checker.py --demo
```

### Machine-Readable JSON Output (CI / Pre-Launch Scripts)
```bash
python3 discount_stack_checker.py --price 80 --cost 48 --sale 25 --promo 20 --json
```

---

## The 5-Point 2:00 AM Flash Sale Safety Protocol

1. **Snapshot Original Prices First** — Export and archive every target variant's `(price, compare_at_price)` pair before applying any rule.
2. **Lock a Hard Cost Floor** — Enforce a strict minimum price above `(Landed_Cost + Fixed_Fee) / (1 - Fee_Rate)` so decimal typos never create `$0.99` store disasters.
3. **Audit Active Coupon Stacking** — Disable or scope legacy welcome/VIP codes (`WELCOME10`, `VIP15`, influencer codes) unless stacked math stays green.
4. **Verify Store Timezone (Not Laptop Time)** — Confirm start and revert timestamps against Shopify Admin's store timezone, especially for international agencies.
5. **Verify Post-Sale Rollback Cent-by-Cent** — Spot-check `/products.json` or automated audit receipts after the cutoff minute so zero variants remain stuck on sale during morning traffic.

Use `bfcm_sale_rollback_checklist.csv` in this repository to run all 15 pre-launch, live-check, and post-sale audit steps with your team.

---

## Free No-Login Browser Tools & Automated Rollbacks

- **12 Free Browser Tools (No Signup / No Store Login):** Test stacked margins, inspect live Shopify storefront strikethroughs via `/products.json`, verify CSV backups, and plan BFCM cutoffs at [getsaleguard.com/tools](https://getsaleguard.com/tools?utm_source=github&utm_medium=repo&utm_campaign=sg_kit).
- **Automated Scheduled Sales & Verified Rollback on Shopify:** If you want dry-run previews, hard cost-floor guardrails, mid-sale manual edit protection, and exact-minute automatic restoration without 2:00 AM CSV sessions, you can test [SaleGuard on the Shopify App Store](https://apps.shopify.com/saleguard-flash-sale-editor?utm_source=github&utm_medium=repo&utm_campaign=sg_kit) free on up to 10 products (original price snapshots and auto-restore remain permanently free on every plan, with minimal 2-scope product pricing permissions and zero access to customer or order data).

---

## License

MIT License. Free to fork, adapt, and share with your store team or Shopify agency clients.
