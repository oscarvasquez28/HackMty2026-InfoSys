"""
Dataset Generation Service.
Runs the forensic data estate seeder (scripts/seed_estate.py) inside a temporary
directory and packages its outputs (estate.db + ground_truth.json) as a ZIP
archive for immediate download. Nothing persists on the server.
"""
import asyncio
import datetime
import io
import logging
import pathlib
import random
import tempfile
import zipfile
from typing import Any, Dict, Optional, Tuple

from scripts.seed_estate import EstateSeeder, load_config

logger = logging.getLogger("forensic_auditor.dataset_generator")

MAX_SEED_VALUE = 999_999


def _run_seeder(tmp_dir: pathlib.Path, seed: int) -> Dict[str, pathlib.Path]:
    """Executes EstateSeeder synchronously inside tmp_dir (called via to_thread)."""
    config = load_config(None)
    config["general"]["seed"] = seed
    config["general"]["output_db_path"] = str(tmp_dir / "estate.db")
    config["general"]["ground_truth_path"] = str(tmp_dir / "ground_truth.json")
    config["general"]["submission_path"] = str(tmp_dir / "submission.json")

    seeder = EstateSeeder(config, seed=seed)
    db_path, gt_path, _ = seeder.run()
    return {
        "estate_db": pathlib.Path(db_path),
        "ground_truth": pathlib.Path(gt_path),
    }


def _build_zip(paths: Dict[str, pathlib.Path], seed: int) -> bytes:
    """Packages estate.db + ground_truth.json + a small README into zip bytes."""
    buffer = io.BytesIO()
    generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    readme = (
        "Forensic Auditor - Seeded Data Estate\n"
        f"Seed: {seed}\n"
        f"Generated at (UTC): {generated_at}\n"
        "Contents: estate.db (SQLite, estate_schema.sql), ground_truth.json\n"
        f"Reproduce locally: python scripts/seed_estate.py --seed {seed}\n"
    )
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(paths["estate_db"], arcname="estate.db")
        archive.write(paths["ground_truth"], arcname="ground_truth.json")
        archive.writestr("README.txt", readme)
    return buffer.getvalue()


async def generate_dataset_zip(seed: Optional[int] = None) -> Tuple[bytes, int, str]:
    """
    Generates a fresh data estate dataset and returns it as a ZIP archive.

    Returns:
        Tuple of (zip_bytes, seed_used, suggested_filename).
    """
    active_seed = seed if seed is not None else random.SystemRandom().randint(1, MAX_SEED_VALUE)
    filename = f"estate_seed_{active_seed}.zip"

    with tempfile.TemporaryDirectory(prefix=f"estate_seed_{active_seed}_") as tmp:
        tmp_dir = pathlib.Path(tmp)
        paths = await asyncio.to_thread(_run_seeder, tmp_dir, active_seed)
        zip_bytes = _build_zip(paths, active_seed)

    logger.info("Generated seeded dataset %s (%d bytes)", filename, len(zip_bytes))
    return zip_bytes, active_seed, filename
