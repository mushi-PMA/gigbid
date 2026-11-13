"""Download the Kaggle datasets and copy the CSV files we need into data/raw/ (git-ignored).

Run:  python -m data.build.download
Anonymous download works for these public datasets. Needs the `kagglehub` package.
"""
from __future__ import annotations

import shutil
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "raw"

# kaggle dataset -> (csv file inside the dataset, name used in data/raw/)
DATASETS = {
    "ahmedmyalo/upwork-freelance-jobs-60k": ("Final_Upwork_Dataset.csv", "upwork_jobs_60k.csv"),
    "asaniczka/upwork-job-postings-dataset-2024-50k-records": ("upwork-jobs.csv", "upwork_jobs_2024.csv"),
    "asaniczka/freelance-contracts-dataset-1-3-million-entries": ("contracts.csv", "contracts.csv"),
    "sarveshchhetri/freelancer-success-earnings-and-churn-prediction": (
        "freelancer_gig_success_dataset.csv", "freelancer_stats.csv"),
}


def main() -> None:
    import kagglehub

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for handle, (csv_name, target_name) in DATASETS.items():
        target = RAW_DIR / target_name
        if target.exists():
            print("already there:", target.name)
            continue
        folder = Path(kagglehub.dataset_download(handle))
        shutil.copy(folder / csv_name, target)
        print("copied", handle, "->", target)


def raw_path(name: str) -> Path:
    path = RAW_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing. Run: python -m data.build.download")
    return path


if __name__ == "__main__":
    main()
