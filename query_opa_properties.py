#!/usr/bin/env python3
"""
Philadelphia OPA Properties Query Script

This script provides CLI commands to query Philadelphia Office of Property Assessment (OPA)
data using Typer. It includes commands for geocoding LIHTC properties and querying violations.

Commands:
- geocode: Geocode LIHTC properties using OPA data
- violations: Query violations for all properties in geocoded results
"""

import csv
import json
import logging
import pdb
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
import typer
from tqdm import tqdm
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("opa_query.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Initialize Typer app
app = typer.Typer()


def handle_exception(exc_type, exc_value, exc_traceback):
    """Handle unhandled exceptions by starting the debugger"""
    if issubclass(exc_type, KeyboardInterrupt):
        # Don't debug on Ctrl+C
        return

    traceback.print_exc()
    pdb.post_mortem()


# Set the exception handler
sys.excepthook = handle_exception


class OPAPropertiesQuery:
    """Class to handle OPA properties API queries"""

    def __init__(self):
        self.base_url = "https://phl.carto.com/api/v2/sql"
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "LIHTC-OPA-Query/1.0 (Educational Research)"}
        )

    def get_violations(self, parcel_number: str) -> List[Dict]:
        query = f"""
        SELECT * FROM violations 
        WHERE opa_account_num = '{parcel_number}'
        """

        response = self.session.post(self.base_url, data={"q": query})
        response.raise_for_status()
        data = response.json()
        if data.get("rows"):
            return data["rows"]
        else:
            return []


def load_lihtc_data(csv_file: str) -> list[dict]:
    """Load LIHTC properties data from CSV file"""
    properties = []

    try:
        with open(csv_file, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Only include properties with valid coordinates
                try:
                    lat = float(row.get("Latitude", 0))
                    lng = float(row.get("Longitude", 0))

                    if lat != 0 and lng != 0:
                        properties.append(
                            {
                                "nhpd_property_id": row.get("NHPD Property ID", ""),
                                "property_name": row.get("Property Name", ""),
                                "address": row.get("Property Address", ""),
                                "lat": lat,
                                "lng": lng,
                                "total_units": row.get("Total Units", ""),
                                "status": row.get("Property Status", ""),
                                "owner_name": row.get("Owner Name", ""),
                                "owner_type": row.get("Owner Type", ""),
                                "latest_end_date": row.get("Latest End Date", ""),
                            }
                        )
                except (ValueError, TypeError):
                    logger.warning(
                        f"Invalid coordinates for property: {row.get('Property Name', 'Unknown')}"
                    )
                    continue

    except FileNotFoundError:
        logger.error(f"CSV file not found: {csv_file}")
        return []
    except Exception as e:
        logger.error(f"Error reading CSV file: {e}")
        return []

    logger.info(f"Loaded {len(properties)} LIHTC properties with valid coordinates")
    return properties


@app.command()
def violations(
    geocoded_csv: str = typer.Option(
        "output/geocoded_results.csv",
        "--input",
        "-i",
        help="Geocoded results CSV filename",
    ),
    output_csv: str = typer.Option(
        "violations.csv", "--output", "-o", help="Output violations CSV filename"
    ),
):
    """Query violations for all properties in geocoded results"""
    try:
        output_dir = Path("lihtc-philly/public")
        output_dir.mkdir(exist_ok=True)
        input_path = Path(geocoded_csv)
        output_path = output_dir / output_csv

        if not input_path.exists():
            logger.error(f"Geocoded results file not found: {input_path}")
            raise typer.Exit(1)

        # Initialize query object
        opa_query = OPAPropertiesQuery()

        # Load geocoded data
        logger.info(f"Loading geocoded data from {input_path}...")
        geocoded_properties = []

        with open(input_path, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Only include properties with parcel numbers
                geocoded_properties.append(
                    {
                        "property_name": row.get("lihtc_property_name", ""),
                        "parcel_number": row["parcel_number"],
                        "NHPD Property ID": str(int(row["NHPD Property ID"])),
                    }
                )

        logger.info(f"Found {len(geocoded_properties)} properties with parcel numbers")

        if not geocoded_properties:
            logger.warning("No properties with parcel numbers found. Exiting.")
            return

        # Collect all violations
        all_violations = []
        properties_with_violations = 0

        # Process each property with tqdm progress bar
        pbar = tqdm(geocoded_properties, desc="Querying violations")
        for property_data in pbar:
            # Query violations for this parcel
            violations = opa_query.get_violations(property_data["parcel_number"])

            if violations:
                properties_with_violations += 1
                # Add property context to each violation
                for violation in violations:
                    violation_with_context = {
                        **property_data,
                        **violation,  # Include all violation fields
                    }
                    all_violations.append(violation_with_context)

                # Update progress bar description with running counts
                pbar.set_description(
                    f"{len(all_violations)} violations at {properties_with_violations} properties"
                )

            # Rate limiting
            time.sleep(0.1)

        # Write violations to CSV
        if all_violations:
            logger.info(f"Writing {len(all_violations)} violations to {output_path}...")
            logger.info(
                "Violations output includes NHPD ID column for linking back to LIHTC properties"
            )

            with open(output_path, "w", newline="", encoding="utf-8") as file:
                fieldnames = all_violations[0].keys()
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_violations)

            logger.info(
                f"Successfully wrote {len(all_violations)} violations to {output_path}"
            )

        else:
            logger.info("No violations found for any properties")
    except:
        traceback.print_exc()
        pdb.post_mortem()


if __name__ == "__main__":
    app()
