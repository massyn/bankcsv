# bankcsv

Load a folder of a bank's CSV statement exports into a single, normalised
`pandas.DataFrame`. Overlapping downloads (the bank only lets you export a
rolling window, so you end up with many overlapping files) are reconciled with
a date-range replacement strategy: the most recent export wins for every date
it covers.

Supported banks: **Bankwest**, **ANZ**, **Macquarie**, **CBA**.

## Installation

```bash
pip install -e ".[dev]"
```

## Usage

```python
from bankcsv import Banking

b = Banking()
df = b.bankwest("~/iCloudDrive/Bankwest")   # folder known to be Bankwest
df = b.anz("~/Downloads")                    # folder known to be ANZ
df = b.macquarie("~/Downloads/macquarie")
df = b.cba("~/Downloads/cba")
```

### Auto-detection

`ingest` walks every CSV under the given path(s) — a folder, a single `.csv`, or
an iterable of either — and offers each file to every bank loader in turn. The
first loader that parses the **whole file** cleanly claims it; files nothing
recognises are logged and skipped. Claimed files are merged per bank and
concatenated, date-sorted:

```python
df = b.ingest(["~/iCloudDrive/Bankwest", "~/Downloads"])
df.groupby("bank").size()
```

Detection is by content, not filename. Loaders are tried most-specific first:

| Bank | Recognised by |
|------|---------------|
| Bankwest | exact 9-column header set |
| Macquarie | core Debit/Credit header **plus** ≥2 of `Category`, `Subcategory`, `Original Description` |
| CBA | headerless lines matching `DD/MM/YYYY,"±amount","desc","±balance"` |
| ANZ | headerless, ≥7 fields, `DD/MM/YYYY` in field 0 and a signed decimal in field 1 |

All frames use the same columns (see below), so `pd.concat([...])` across banks
just works. The `load_bankwest` / `load_anz` / `load_macquarie` / `load_cba` /
`ingest` functions are also exported for direct use.

## Transaction schema

Every loader (`load_bankwest`, `load_anz`, …) returns a `pandas.DataFrame` with
the **same nine columns, in this order**. The columns are always present
(mandatory). *Required* fields are additionally guaranteed to be non-null on
every row; *optional* fields are `None` when the source does not provide them.

Money is normalised to a single signed `amount` (`decimal.Decimal`): credits are
positive, debits negative. `date` is a `datetime.date`.

The frame is object-dtype throughout and gaps are Python `None`, never `NaN`, so
`Decimal` columns stay exact and `x is None` works. An optional column that is
`None` on every row means that bank does not expose it; call
`df.dropna(axis=1, how="all")` for a per-bank trimmed view.

| Column        | Obligation |
|---------------|------------|
| `bank`        | required   |
| `date`        | required   |
| `amount`      | required   |
| `description` | required   |
| `account`     | optional   |
| `balance`     | optional   |
| `type`        | optional   |
| `payee`       | optional   |
| `note`        | optional   |

### Source mapping

Headerless banks are shown by column index; `—` means the export does not carry
that field (so the column is `None` for every row of that bank).

| Column        | Bankwest (`CSV header`)         | ANZ (`col[i]`) | Macquarie (`CSV header`) | CBA (`col[i]`) |
|---------------|--------------------------------|----------------|--------------------------|----------------|
| `bank`        | `"Bankwest"`                   | `"ANZ"`        | `"Macquarie"`            | `"CBA"`        |
| `date`        | `Transaction Date` (DD/MM/YYYY) | `col[0]` (DD/MM/YYYY) | `Transaction Date` (DD Mon YYYY) | `col[0]` (DD/MM/YYYY) |
| `amount`      | `Credit` − `Debit`             | `col[1]`       | `Credit` − `Debit`       | `col[1]`       |
| `description` | `Narration`                    | `col[2]`       | `Details`                | `col[2]`       |
| `account`     | `BSB Number`/`Account Number`  | `col[3]` (nickname; often empty) | `Account`      | —              |
| `balance`     | `Balance`                      | —              | `Balance`                | `col[3]`       |
| `type`        | `Transaction Type`             | —              | —                        | —              |
| `payee`       | —                              | `col[4]`       | —                        | —              |
| `note`        | —                              | `col[6]`       | —                        | —              |

Not carried: ANZ `col[5]`/`col[7]` (always empty); Bankwest `Cheque`; Macquarie
`Category` / `Subcategory` / `Original Description` (used only for detection).

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Licence

MIT — see [LICENSE](LICENSE).
