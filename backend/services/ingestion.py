import io
from typing import BinaryIO, Dict, Any, Tuple
import polars as pl


# Mapping of common column aliases found in IBM AMLSim and banking transaction logs
COLUMN_ALIASES = {
    "origin": ["origin", "nameorig", "from_account", "source", "orig_account", "orig", "orig_acct"],
    "destination": ["destination", "namedest", "to_account", "target", "dest_account", "dest", "bene_acct"],
    "amount": ["amount", "value", "monto", "sum", "base_amt"],
    "timestamp": ["timestamp", "step", "time", "date", "datetime", "trans_time", "tran_timestamp"],
}


def find_canonical_column(columns: list[str], target: str) -> str:
    """Find the column name in the dataset matching any of the candidate aliases."""
    normalized_cols = {col.lower().strip(): col for col in columns}
    candidates = COLUMN_ALIASES.get(target, [])
    for candidate in candidates:
        if candidate in normalized_cols:
            return normalized_cols[candidate]
    raise ValueError(
        f"Column matching required concept '{target}' was not found. "
        f"Available columns: {columns}. Expected one of: {candidates}"
    )


def read_amlsim_csv(source: BinaryIO | bytes | str) -> Tuple[pl.DataFrame, Dict[str, Any]]:
    """
    Ingests and normalizes an IBM AMLSim or equivalent financial transaction CSV dataset using Polars.

    Returns:
        Tuple containing:
            - Normalized Polars DataFrame with columns ['origin', 'destination', 'amount', 'timestamp']
            - Metadata summary dictionary
    """
    if isinstance(source, bytes):
        df = pl.read_csv(io.BytesIO(source))
    elif isinstance(source, str):
        df = pl.read_csv(source)
    else:
        # File-like object (e.g. UploadFile.file)
        content = source.read()
        df = pl.read_csv(io.BytesIO(content))

    if df.is_empty():
        raise ValueError("The provided CSV dataset is empty.")

    original_columns = df.columns
    orig_col = find_canonical_column(original_columns, "origin")
    dest_col = find_canonical_column(original_columns, "destination")
    amount_col = find_canonical_column(original_columns, "amount")

    # Timestamp is optional; if missing, generate sequential synthetic step
    has_timestamp = False
    for candidate in COLUMN_ALIASES["timestamp"]:
        for col in original_columns:
            if col.lower().strip() == candidate:
                timestamp_col = col
                has_timestamp = True
                break
        if has_timestamp:
            break

    select_exprs = [
        pl.col(orig_col).cast(pl.Utf8).alias("origin"),
        pl.col(dest_col).cast(pl.Utf8).alias("destination"),
        pl.col(amount_col).cast(pl.Float64).alias("amount"),
    ]

    if has_timestamp:
        ts_dtype = df[timestamp_col].dtype
        if ts_dtype in [pl.Utf8, pl.String]:
            # Try to parse string to datetime epoch seconds, falling back to float cast or null
            ts_expr = (
                pl.col(timestamp_col)
                .str.to_datetime(time_zone="UTC", strict=False)
                .dt.epoch("s")
                .cast(pl.Float64)
                .fill_null(pl.col(timestamp_col).cast(pl.Float64, strict=False))
                .fill_null(0.0)
                .alias("timestamp")
            )
            select_exprs.append(ts_expr)
        else:
            select_exprs.append(
                pl.col(timestamp_col).fill_null(0.0).cast(pl.Float64, strict=False).alias("timestamp")
            )
    else:
        select_exprs.append(
            pl.int_range(0, df.height, dtype=pl.Int64).cast(pl.Float64).alias("timestamp")
        )

    cleaned_df = (
        df.select(select_exprs)
        .filter(
            pl.col("origin").is_not_null()
            & pl.col("destination").is_not_null()
            & pl.col("amount").is_not_null()
            & (pl.col("amount") > 0)
        )
    )

    if cleaned_df.is_empty():
        raise ValueError("No valid transaction rows found after cleansing.")

    total_records = cleaned_df.height
    total_volume = float(cleaned_df["amount"].sum() or 0.0)
    unique_origins = set(cleaned_df["origin"].to_list())
    unique_destinations = set(cleaned_df["destination"].to_list())
    unique_accounts = len(unique_origins.union(unique_destinations))

    metadata = {
        "total_records": total_records,
        "total_volume": round(total_volume, 2),
        "unique_accounts": unique_accounts,
        "original_columns": original_columns,
    }

    return cleaned_df, metadata
