from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import UploadFile, File, HTTPException
from typing import Any, Dict, List
from pydantic import BaseModel
from io import BytesIO
import numpy as np
import pandas as pd

app = FastAPI(title="Gard Eau Arbres API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Bienvenue sur l'API Gard Eau Arbres"}


def analyze_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """Return a concise EDA summary for the given DataFrame."""
    num_rows = int(df.shape[0])
    num_cols = int(df.shape[1])

    # Dtypes and memory
    dtypes: Dict[str, str] = {column: str(dtype) for column, dtype in df.dtypes.items()}
    memory_usage_bytes = int(df.memory_usage(deep=True).sum()) if num_cols > 0 else 0

    # Missing values
    if num_rows > 0 and num_cols > 0:
        missing_counts = df.isna().sum()
        per_column_missing: Dict[str, Dict[str, Any]] = {}
        for column in df.columns:
            missing_count = int(missing_counts[column])
            missing_pct = float((missing_count / num_rows) * 100.0) if num_rows else 0.0
            per_column_missing[column] = {"count": missing_count, "pct": missing_pct}
        total_missing_cells = int(missing_counts.sum())
        total_cells = num_rows * num_cols
        missing_cells_pct = float((total_missing_cells / total_cells) * 100.0) if total_cells else 0.0
    else:
        per_column_missing = {}
        total_missing_cells = 0
        missing_cells_pct = 0.0

    # Duplicates
    duplicate_rows = int(df.duplicated().sum()) if num_rows > 0 else 0

    # Numeric summary
    numeric_summary: Dict[str, Dict[str, Any]] = {}
    numeric_columns: List[str] = df.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_columns:
        desc = df[numeric_columns].describe().transpose()

        def to_float(value: Any) -> Any:
            if pd.isna(value):
                return None
            try:
                return float(value)
            except Exception:
                try:
                    return value.item()  # type: ignore[attr-defined]
                except Exception:
                    return None

        for column in numeric_columns:
            row = desc.loc[column]
            numeric_summary[column] = {stat: to_float(row[stat]) for stat in desc.columns}

    # Categorical summary
    categorical_summary: Dict[str, Dict[str, Any]] = {}
    categorical_columns: List[str] = df.select_dtypes(include=["object", "category", "string"]).columns.tolist()
    if categorical_columns:
        total = num_rows if num_rows else 1
        for column in categorical_columns:
            value_counts = df[column].astype("string").value_counts(dropna=False)
            top_values = []
            for value, count in value_counts.head(5).items():
                display_value = None if pd.isna(value) else str(value)
                pct = float((int(count) / total) * 100.0)
                top_values.append({"value": display_value, "count": int(count), "pct": pct})
            categorical_summary[column] = {
                "unique": int(df[column].nunique(dropna=True)),
                "top_values": top_values,
            }

    # Correlations (top pairs by absolute correlation)
    correlations: List[Dict[str, Any]] = []
    if len(numeric_columns) >= 2:
        corr_matrix = df[numeric_columns].corr()
        cols = list(corr_matrix.columns)
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                corr_value = corr_matrix.iloc[i, j]
                if pd.notna(corr_value):
                    correlations.append({
                        "col_a": cols[i],
                        "col_b": cols[j],
                        "corr": float(corr_value),
                    })
        correlations.sort(key=lambda item: abs(item["corr"]), reverse=True)
        correlations = [c for c in correlations if abs(c["corr"]) >= 0.5][:20]

    # Sample
    sample_records: List[Dict[str, Any]] = (
        df.head(5).to_dict(orient="records") if num_rows > 0 else []
    )

    return {
        "shape": {"rows": num_rows, "columns": num_cols},
        "columns": list(df.columns),
        "dtypes": dtypes,
        "memory_usage_bytes": memory_usage_bytes,
        "missing": {
            "per_column": per_column_missing,
            "total_missing_cells": total_missing_cells,
            "missing_cells_pct": missing_cells_pct,
        },
        "duplicates": {"row_duplicates": duplicate_rows},
        "numeric_summary": numeric_summary,
        "categorical_summary": categorical_summary,
        "correlations": correlations,
        "sample": sample_records,
    }


@app.post("/analyze/csv")
async def analyze_csv(file: UploadFile = File(...)):
    if not file.filename.endswith((".csv", ".tsv")):
        raise HTTPException(status_code=400, detail="Only CSV/TSV files are supported")
    try:
        content = await file.read()
        sep = "\t" if file.filename.endswith(".tsv") else ","
        df = pd.read_csv(BytesIO(content), sep=sep)
    except Exception as exc:  # pragma: no cover - parse errors
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}")
    return analyze_dataframe(df)


class RecordsPayload(BaseModel):
    records: List[Dict[str, Any]]


@app.post("/analyze/json")
async def analyze_json(payload: RecordsPayload):
    try:
        df = pd.DataFrame(payload.records)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=400, detail=f"Failed to build DataFrame: {exc}")
    return analyze_dataframe(df)
