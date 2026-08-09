"""Pipeline for parallel downloading and processing of DICOM images from Google
Cloud Storage."""

import concurrent.futures
import logging
from pathlib import Path
from typing import Any

import hydra
import polars as pl
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError
from omegaconf import DictConfig
from PIL import Image, UnidentifiedImageError

# Configure production-standard logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def process_image(file_path: Path, cfg: DictConfig) -> str | None:
    """Resizes an image and center crops it based on the configuration.

    Args:
        file_path: The local path to the downloaded image file.
        cfg: The Hydra configuration dictionary containing processing parameters.

    Returns:
        An error message string if processing fails, otherwise None.
    """
    try:
        with Image.open(file_path) as img:
            if cfg.image.resize.enabled:
                resize_size: int = cfg.image.resize.size
                img = img.resize((resize_size, resize_size), Image.Resampling.LANCZOS)
            if cfg.image.crop.enabled:
                width, height = img.size
                new_width: int = cfg.image.crop.size
                new_height: int = cfg.image.crop.size
                left: float = (width - new_width) / 2
                top: float = (height - new_height) / 2
                right: float = (width + new_width) / 2
                bottom: float = (height + new_height) / 2
                img = img.crop((left, top, right, bottom))
            img.save(file_path)
            return None
    except UnidentifiedImageError:
        return "Image processing error: Cannot identify image file."
    except OSError as e:
        return f"Image processing error: File IO operation failed: {e}"
    except ValueError as e:
        return f"Image processing error: Invalid parameters applied during transform: {e}"


def download_and_process_single(
    row: dict[str, Any],
    cfg: DictConfig,
    storage_client: storage.Client,
) -> tuple[str, str, str]:
    """Handles the download and processing pipeline for a single record.

    Args:
        row: A dictionary mapping column names to row values for a single record.
        cfg: The Hydra configuration dictionary.
        storage_client: An initialized Google Cloud Storage client instance.

    Returns:
        A tuple containing the status ("SUCCESS", "FAILED", "SKIPPED"), the dicom_id,
        and a descriptive result message.
    """
    subj_id: str = str(row["subject_id"])
    study_id: str = str(row["study_id"])
    dicom_id: str = str(row["dicom_id"])

    folder_group: str = f"p{subj_id[:2]}"
    folder_subject: str = f"p{subj_id}"
    folder_study: str = f"s{study_id}"
    file_name: str = f"{dicom_id}.jpg"
    blob_name: str = f"{cfg.gcp.bucket_prefix}/{folder_group}/{folder_subject}/{folder_study}/{file_name}"

    local_dest_dir: Path = Path(cfg.output_directory) / folder_subject / folder_study
    local_dest_dir.mkdir(parents=True, exist_ok=True)
    local_file_path: Path = local_dest_dir / file_name

    if local_file_path.exists():
        return "SKIPPED", dicom_id, f"Skipped: {file_name} (Already exists)"

    try:
        bucket = storage_client.bucket(cfg.gcp.bucket_name)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(str(local_file_path))

        process_error: str | None = process_image(local_file_path, cfg)
        if process_error:
            return "FAILED", dicom_id, f"Failed: {file_name}. Details: {process_error}"

        return "SUCCESS", dicom_id, f"Success: {file_name}"

    except GoogleCloudError as gcp_err:
        return "FAILED", dicom_id, f"GCP Download Failed: {file_name}. Details: {gcp_err}"
    except OSError as os_err:
        return "FAILED", dicom_id, f"Local OS/File Error: {file_name}. Details: {os_err}"


@hydra.main(version_base=None, config_path=".", config_name="cxr_downloader_config")
def run_parallel_pipeline(cfg: DictConfig) -> None:
    """Executes the main parallel download and processing pipeline.

    Args:
        cfg: The primary Hydra configuration object.
    """
    df: pl.DataFrame = pl.read_csv(cfg.csv_file_path)
    total_rows: int = df.height
    limit: int = cfg.trial_run_limit if cfg.trial_run_limit is not None else total_rows
    df_subset: pl.DataFrame = df.head(limit)
    total_tasks: int = df_subset.height

    logger.info(f"Found {total_rows} total rows. Executing {total_tasks} files.")
    logger.info(f"Starting parallel processing with {cfg.max_workers} workers...")

    storage_client = storage.Client()
    failed_files: list[dict[str, Any]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=cfg.max_workers) as executor:
        futures = {
            executor.submit(download_and_process_single, row, cfg, storage_client): row
            for row in df_subset.iter_rows(named=True)
        }
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            status, dicom_id, result_msg = future.result()
            percent_complete: float = (i / total_tasks) * 100

            logger.info(f"[{i}/{total_tasks}] ({percent_complete:.1f}%) | {result_msg}")

            if status == "FAILED":
                original_row: dict[str, Any] = futures[future]
                failed_files.append(
                    {
                        "subject_id": original_row["subject_id"],
                        "study_id": original_row["study_id"],
                        "dicom_id": original_row["dicom_id"],
                        "error": result_msg,
                    },
                )

    logger.info("=" * 40)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 40)

    if failed_files:
        logger.warning(f"{len(failed_files)} files failed to download or process.")
        failed_df: pl.DataFrame = pl.DataFrame(failed_files)
        failed_df.write_csv(cfg.failed_csv_path)
        logger.info(f"A list of these files and their errors has been saved to: {cfg.failed_csv_path}")
    else:
        logger.info("Success! All files were downloaded and processed without any errors.")


if __name__ == "__main__":
    run_parallel_pipeline()
