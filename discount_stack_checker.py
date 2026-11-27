#!/usr/bin/env python3
"""
Shopify Discount Stack & Margin Floor Checker.

Exact Decimal CLI calculator to catch negative-margin stacked discounts
(flash sale compare-at markdown + active checkout promo code + payment fees)
before launching a Shopify promotion.

Zero third-party dependencies. Compatible with Python 3.9+.
Free browser version & 11 more no-login Shopify tools:
https://getsaleguard.com/tools?utm_source=github&utm_medium=repo&utm_campaign=sg_kit
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from typing import List, Optional

CENT = Decimal("0.01")
TENTH = Decimal("0.1")
HUNDRED = Decimal("100")


def q2(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def q1(value: Decimal) -> Decimal:
    return value.quantize(TENTH, rounding=ROUND_HALF_UP)


def q1_down(value: Decimal) -> Decimal:
    return value.quantize(TENTH, rounding=ROUND_DOWN)


def parse_decimal(raw: str, label: str) -> Decimal:
    try:
        val = Decimal(raw.strip())
    except InvalidOperation as exc:
        raise ValueError(f"Invalid numeric value for {label}: {raw!r}") from exc
    if not val.is_finite():
        raise ValueError(f"Value for {label} must be finite.")
    return val


@dataclass(frozen=True)
class StackResult:
    retail_price: Decimal
    landed_cost: Decimal
    flash_sale_pct: Decimal
    promo_code_pct: Decimal
    fee_pct: Decimal
    fee_fixed: Decimal
    flash_sale_price: Decimal
    effective_price: Decimal
    combined_discount_pct: Decimal
    payment_fee: Decimal
    net_profit: Decimal
    net_margin_pct: Decimal
    baseline_profit: Decimal
    break_even_price: Decimal
    max_safe_promo_pct: Decimal
    status: str
    alert_label: str


def evaluate_stack(
    retail_price: Decimal,
    landed_cost: Decimal,
    flash_sale_pct: Decimal,
    promo_code_pct: Decimal,
    fee_pct: Decimal = Decimal("2.9"),
    fee_fixed: Decimal = Decimal("0.30"),
    thin_margin_pct: Decimal = Decimal("15.0"),
) -> StackResult:
    if retail_price <= 0:
        raise ValueError("Retail price must be greater than 0.")
    if landed_cost < 0:
        raise ValueError("Landed cost cannot be negative.")
    if not (Decimal("0") <= flash_sale_pct < HUNDRED):
        raise ValueError("Flash sale percent must be in [0, 100).")
    if not (Decimal("0") <= promo_code_pct < HUNDRED):
        raise ValueError("Promo code percent must be in [0, 100).")
    if not (Decimal("0") <= fee_pct < HUNDRED):
        raise ValueError("Payment fee percent must be in [0, 100).")
    if fee_fixed < 0:
        raise ValueError("Fixed fee cannot be negative.")

    sale_factor = Decimal("1") - (flash_sale_pct / HUNDRED)
    promo_factor = Decimal("1") - (promo_code_pct / HUNDRED)
    fee_rate = fee_pct / HUNDRED

    flash_sale_price = q2(retail_price * sale_factor)
    effective_price = q2(retail_price * sale_factor * promo_factor)
    combined_discount_pct = q2((Decimal("1") - (sale_factor * promo_factor)) * HUNDRED)

    payment_fee = q2(effective_price * fee_rate + fee_fixed)
    net_profit = q2(effective_price - landed_cost - payment_fee)
    net_margin_pct = (
        q1((net_profit / effective_price) * HUNDRED)
        if effective_price > 0
        else Decimal("0.0")
    )

    baseline_fee = q2(retail_price * fee_rate + fee_fixed)
    baseline_profit = q2(retail_price - landed_cost - baseline_fee)

    break_even_price = q2((landed_cost + fee_fixed) / (Decimal("1") - fee_rate))

    if flash_sale_price > 0 and flash_sale_price > break_even_price:
        max_promo = (Decimal("1") - (break_even_price / flash_sale_price)) * HUNDRED
        max_safe_promo_pct = max(Decimal("0.0"), q1_down(max_promo))
    else:
        max_safe_promo_pct = Decimal("0.0")

    if net_profit < 0:
        status = "RED"
        alert_label = f"RED ALERT: LOSING ${abs(net_profit):.2f} PER ORDER"
    elif net_margin_pct < thin_margin_pct:
        status = "AMBER"
        alert_label = f"AMBER WARNING: THIN MARGIN ({net_margin_pct:.1f}% < {thin_margin_pct:.1f}%)"
    else:
        status = "GREEN"
        alert_label = f"GREEN SAFE: HEALTHY MARGIN ({net_margin_pct:.1f}%)"

    return StackResult(
        retail_price=q2(retail_price),
        landed_cost=q2(landed_cost),
        flash_sale_pct=q2(flash_sale_pct),
        promo_code_pct=q2(promo_code_pct),
        fee_pct=q2(fee_pct),
        fee_fixed=q2(fee_fixed),
        flash_sale_price=flash_sale_price,
        effective_price=effective_price,
        combined_discount_pct=combined_discount_pct,
        payment_fee=payment_fee,
        net_profit=net_profit,
        net_margin_pct=net_margin_pct,
        baseline_profit=baseline_profit,
        break_even_price=break_even_price,
        max_safe_promo_pct=max_safe_promo_pct,
        status=status,
        alert_label=alert_label,
    )


def format_report(res: StackResult, title: Optional[str] = None) -> str:
    sign = "-" if res.net_profit < 0 else "+"
    lines: List[str] = []
    if title:
        lines.append(f"=== {title} ===")
    else:
        lines.append("=== SHOPIFY DISCOUNT STACK CHECK ===")
    lines.extend(
        [
            f"Status:            {res.alert_label}",
            f"Retail Price:      ${res.retail_price:.2f}  (Baseline Net Profit: ${res.baseline_profit:.2f})",
            f"Landed Cost:       ${res.landed_cost:.2f}",
            f"Flash Sale ({res.flash_sale_pct:.2f}%): ${res.flash_sale_price:.2f}",
            f"Stacked Code ({res.promo_code_pct:.2f}%): ${res.effective_price:.2f}  (Combined Discount: {res.combined_discount_pct:.2f}%)",
            f"Payment Fee:       ${res.payment_fee:.2f}  ({res.fee_pct:.2f}% + ${res.fee_fixed:.2f})",
            f"Net Profit/Order:  {sign}${abs(res.net_profit):.2f}  (Net Margin: {res.net_margin_pct:.1f}%)",
            f"Break-Even Floor:  ${res.break_even_price:.2f}",
            f"Max Safe Promo:    {res.max_safe_promo_pct:.1f}% on top of {res.flash_sale_pct:.2f}% sale",
        ]
    )
    return "\n".join(lines)


def serialize_result(res: StackResult) -> dict:
    raw = asdict(res)
    return {
        k: (str(v) if isinstance(v, Decimal) else v)
        for k, v in raw.items()
    }


def run_demo() -> int:
    scenarios = [
        ("Scenario 1: Classic BFCM Trap ($100 SKU, 25% Sale + 15% Welcome Code)", "100", "62", "25", "15"),
        ("Scenario 2: Heavy Markdown Crash ($80 SKU, 30% Sale + 20% VIP Code)", "80", "48", "30", "20"),
        ("Scenario 3: Thin Margin Warning ($120 SKU, 20% Sale + 10% Email Code)", "120", "76", "20", "10"),
        ("Scenario 4: Protected Healthy Sale ($100 SKU, 20% Sale + 0% Code)", "100", "52", "20", "0"),
    ]
    print("Shopify Flash Sale Safety Kit - Discount Stack Matrix\n")
    for title, price, cost, sale, promo in scenarios:
        res = evaluate_stack(
            retail_price=Decimal(price),
            landed_cost=Decimal(cost),
            flash_sale_pct=Decimal(sale),
            promo_code_pct=Decimal(promo),
        )
        print(format_report(res, title=title))
        print()
    print(
        "Free browser calculators (12 no-login tools): "
        "https://getsaleguard.com/tools?utm_source=github&utm_medium=repo&utm_campaign=sg_kit"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calculate true Shopify net profit when flash sale markdowns stack with promo codes."
    )
    parser.add_argument("--price", help="Original retail price (e.g. 100)")
    parser.add_argument("--cost", help="Total landed cost per unit: COGS + shipping + ad CAC (e.g. 62)")
    parser.add_argument("--sale", default="0", help="Flash sale compare-at discount percent (e.g. 25)")
    parser.add_argument("--promo", default="0", help="Stacked checkout promo code percent (e.g. 15)")
    parser.add_argument("--fee-pct", default="2.9", help="Payment gateway percent fee (default: 2.9)")
    parser.add_argument("--fee-fixed", default="0.30", help="Payment gateway fixed fee per order (default: 0.30)")
    parser.add_argument("--thin-margin", default="15.0", help="Amber warning margin threshold percent (default: 15.0)")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    parser.add_argument("--demo", action="store_true", help="Run 4 built-in Shopify BFCM stacking scenarios")
    parser.add_argument(
        "--fail-on-loss",
        action="store_true",
        help="Return exit code 2 if net profit is negative (useful for CI/pre-launch gates)",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.demo or (args.price is None and args.cost is None):
        return run_demo()

    if args.price is None or args.cost is None:
        parser.error("Both --price and --cost are required (or pass --demo).")

    try:
        result = evaluate_stack(
            retail_price=parse_decimal(args.price, "--price"),
            landed_cost=parse_decimal(args.cost, "--cost"),
            flash_sale_pct=parse_decimal(args.sale, "--sale"),
            promo_code_pct=parse_decimal(args.promo, "--promo"),
            fee_pct=parse_decimal(args.fee_pct, "--fee-pct"),
            fee_fixed=parse_decimal(args.fee_fixed, "--fee-fixed"),
            thin_margin_pct=parse_decimal(args.thin_margin, "--thin-margin"),
        )
    except ValueError as err:
        print(f"Input error: {err}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(serialize_result(result), indent=2))
    else:
        print(format_report(result))

    if args.fail_on_loss and result.status == "RED":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
