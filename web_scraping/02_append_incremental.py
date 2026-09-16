import os
import glob
from pathlib import Path

# Define directory paths
BASE_DIR = Path(
    "/Users/davidreynolds/projects/trustpilot_pet_insurance_reviews/web_scraping"
)
incremental_dir = BASE_DIR / "incremental"
curated_dir = BASE_DIR / "curated"

# Find all incremental files to identify the provider keys
incremental_pattern = os.path.join(incremental_dir, "*_reviews_incremental.csv")
incremental_files = glob.glob(incremental_pattern)

for inc_file_path in incremental_files:
    # Extract the file name (e.g., 'provider_key_reviews_incremental.csv')
    inc_file_name = os.path.basename(inc_file_path)

    # Isolate the provider_key
    provider_key = inc_file_name.replace("_reviews_incremental.csv", "")

    # Construct the corresponding curated file path
    curated_file_name = f"{provider_key}_reviews_all.csv"
    curated_file_path = os.path.join(curated_dir, curated_file_name)

    # Verify that the corresponding curated file exists before proceeding
    if not os.path.exists(curated_file_path):
        print(f"Warning: Curated file not found for key '{provider_key}'. Skipping.")
        continue

    print(f"Appending {inc_file_name} to {curated_file_name}...")

    # Open the curated file in append mode and the incremental file in read mode
    with open(curated_file_path, "a", encoding="utf-8") as curated_file:
        with open(inc_file_path, "r", encoding="utf-8") as inc_file:
            # Skip the header row of the incremental file
            next(inc_file)

            # Optional: Ensure the curated file ends with a newline before appending
            # This prevents stitching the first new row to the last old row if a newline is missing
            if curated_file.tell() > 0:
                curated_file.write("\n")

            # Write the remaining rows
            for line in inc_file:
                # Avoid writing extra blank rows if the file ends with trailing newlines
                if line.strip():
                    curated_file.write(line)

print("File merging complete!")
