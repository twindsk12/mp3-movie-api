# MP3 Movie API

This project is a movie API created by using Python, FastAPI, and SQLite. It is organized into separate modules for the API, database, movie storage, data processing, and caching. Users can upload movie CSV files through the /upload endpoint, which saves the records in a SQLite database so that it is still available after restarting. The /movies endpoint retrieves stored movies, while /movies/search makes it so you can search through the data. The /movies/process endpoint checks the data for missing values, removes duplicates, and identifies any outliers. The caching for movie results is done through FakeRedis to prevent running the same database queries repeatedly. When new data is uploaded or processed, the cache is cleared so that the API returns the most recent results.

## Running the Application

Start the API:

python -m uvicorn main:app --reload


Access the API:

http://127.0.0.1:8000/docs

## Running Tests

Run the test using:

python -m pytest tests -v

## Sample Processing Request

Send a POST request to `/movies/process` with this JSON body:

```json
{
    "validation": {
        "required_columns": ["title", "release_year", "rating", "genre"],
        "numeric_columns": ["release_year", "rating"]
    },
    "processing": {
        "remove_duplicates": true,
        "missing": {
            "enabled": true,
            "axis": "rows"
        },
        "outliers": {
            "enabled": true,
            "columns": ["rating"],
            "method": "iqr",
            "threshold": 1.5
        }
    }
}
```

##Expected Result:
The sample dataset goes from 20 rows to 16 with 4 rows being removed during the cleaning processs.


```json
{
  "validation_rows_removed": 0,
  "cleaning_report": {
    "rows_before": 20,
    "rows_after": 16,
    "rows_removed": 4,
    "columns_before": 4,
    "columns_after": 4,
    "columns_removed": 0
  }
```
