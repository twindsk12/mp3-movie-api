import io
import logging
from pathlib import Path

import pandas as pd

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from data_pipeline import (
    create_cleaning_report,
    process_data,
    validate_dataframe,
)

from src import (
    HealthResponse,
    MovieStorage,
    MovieCache,
    setup_logging,
)

from src.middleware import log_requests

from src.models import (
    MovieUploadInfo,
    MovieDataResponse,
    MovieProcessingReport,
    ProcessConfig,
)

from src.storage import MOVIE_COLUMNS


setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Processing API", version="1.0.0")
app.middleware("http")(log_requests)
storage = MovieStorage()
cache = MovieCache()


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return {"status": "ok", "version": "1.0.0"}

@app.post("/upload", response_model=MovieUploadInfo)
async def upload_movies(file: UploadFile = File(...)):
    """Read and store a CSV upload."""
    filename = file.filename or ""

    if Path(filename).suffix.lower() != ".csv":
        logger.warning("Unsupported file format: %s", filename)
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported."
        )

    contents = await file.read()

    try:
        df = pd.read_csv(io.BytesIO(contents))
    except (
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
            UnicodeDecodeError
    ) as error:
        logger.warning("Cannot read CSV: %s", error)
        raise HTTPException(
            status_code=400,
            detail="Cannot read the uploaded CSV."
        ) from error

    if set(df.columns) != set(MOVIE_COLUMNS) or len(df.columns) != len(MOVIE_COLUMNS):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must contain exactly these columns: {MOVIE_COLUMNS}"
        )

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="The uploaded CSV must contain at least one movie."
        )

    df = df[MOVIE_COLUMNS]

    storage.save(df)
    cache.invalidate()

    logger.info(
        "Uploaded movies: filename=%s, rows=%s",
        filename,
        len(df)
    )

    return {
        "filename": filename,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns)
    }


@app.get("/movies", response_model=MovieDataResponse)
def get_movies(limit: int = Query(default=100, ge=1)):
    # TODO: Use MovieStorage methods to retrieve up to limit rows and count the total number of stored movies.
    # Return {"data": ..., "total_rows": ...}.
    # If empty, return {"data": [], "total_rows": 0}.
    # Log the row count at INFO.

    # TODO 1: Look up the response using cache.get(limit).
    # If it is not None, log the cache hit at INFO and return it.

    # Keep Part 1's SQL retrieval, total count, and response construction here.

    # TODO 2: Before the existing return, cache the complete response
    # using cache.set(limit, response).
    # Keep the existing row-count log and return.

    cached = cache.get(limit)

    if cached is not None:
        logger.info("Retrieved movies: returned_rows=%s", len(cached["data"]))
        return cached

    records = storage.select_columns(MOVIE_COLUMNS, limit=limit)
    total_rows = storage.count_movies()

    response = {
        "data": records,
        "total_rows": total_rows
    }

    logger.info(
        "Retrieved movies: returned_rows=%s, total_rows=%s",
        len(records),
        total_rows
    )

    cache.set(limit, response)

    return response



@app.get("/movies/search", response_model=list[dict])
def query_movies(
    columns: list[str] = Query(default=["title"]),
    min_rating: float = Query(default=0, ge=0, le=10),
    limit: int = Query(default=100, ge=1)
):
    # TODO: Call storage.query_movies(columns, min_rating, limit).
    # Catch ValueError and raise HTTPException with status 400.
    # Return id plus the selected fields, or [] if there are no matches.
    # Log the selected columns and returned row count at INFO.
    try:
        results = storage.query_movies(
            columns,
            min_rating,
            limit
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        ) from error

    logger.info(
        "Movie search: columns=%s, returned_rows=%s",
        columns,
        len(results)
    )

    return results

@app.post("/movies/process", response_model=MovieProcessingReport)
def process_movies(config: ProcessConfig):
    # TODO 1: Retrieve data using storage.get().
    # Raise HTTPException with status 400 if empty.

    # TODO 2: Reuse MP2's configuration, validation, processing,
    # cleaning report, logging, and ValueError handling.

    # TODO 3: Save the processed DataFrame using storage.save().
    # Return validation_rows_removed and cleaning_report without a dataset ID.
    df = storage.get()

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="No movies have been uploaded."
        )

    config_dict = config.model_dump()

    validation_config = config_dict["validation"]

    required_columns = validation_config["required_columns"]
    numeric_columns = validation_config["numeric_columns"]

    try:
        for column in numeric_columns:
            if column not in df.columns:
                raise ValueError(
                    f"Numeric column '{column}' does not exist"
                )

        validated_df = validate_dataframe(
            df,
            required_columns=required_columns,
            numeric_columns=numeric_columns,
        )

        validation_rows_removed = len(df) - len(validated_df)

        validated_copy = validated_df.copy()

        processed_df = process_data(
            validated_df,
            config_dict,
        )

        cleaning_report = create_cleaning_report(
            validated_copy,
            processed_df,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    storage.save(processed_df)
    cache.invalidate()

    logger.info(
        "Processed movies: validation_removed=%s, "
        "rows_before=%s, rows_after=%s",
        validation_rows_removed,
        len(validated_copy),
        len(processed_df),
    )

    return {
        "validation_rows_removed": validation_rows_removed,
        "cleaning_report": cleaning_report,
    }
