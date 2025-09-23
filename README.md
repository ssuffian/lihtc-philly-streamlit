
### Getting Geocoded LIHTC-Properties

1. Download the LIHTC file from [here](https://nhpd.preservationdatabase.org/Data). Download the complete list of All Properties, as well as All Subsidies.
2. For processing purposes, filter this file to only include those where city='Philadelphia' and state='PA'. Name this file `lihtc_properties_philadelphia.csv`.
3. Ensure your LIHTC CSV file (`lihtc_properties_philadelphia.csv`) is in the same directory as the script.
4. Attempt to geocode this file based on [where-is-philly](https://github.com/ssuffian/who-is-where-philly). Share the output in a google-doc so the OPA account number mappings can be crowd-source confirmed.
5. Download the hand-geocoded file and put it in `data`. By default it looks for a file named 'All Properties (Philly, Geocode Attempt) - geocoded_results.csv'

### Getting Other Data (put in the `data/` folder):

1. Download latest db from the [odp-philly-backups](https://github.com/whoownsphilly/odp-data-backup/releases)
2. Download [Lead Data](https://opendataphilly.org/datasets/lead-paint-certs/)
3. Download Council districts and PA senate districts geojson files. 

### Regular updates required
- streamlit_app.py has a hardcoded dictionary of state senate and council districts to the names of the people holding those positions.

### Updating the data for the dashboard
```
# install geospatial which is needed for these scripts
uv sync --extra dev

# This takes each HUD property and gets every parcel number associated with it
python get-associated-parcels

# Pulls relevant data from lead, violations, and HUD data to generate the CSV files used directly for the dashboard
python generate-db-for-dashboard
```

Other data sources
- [Zip Codes](https://opendataphilly.org/datasets/zip-codes/)
- [HudUser](https://www.huduser.gov/lihtc/) - filtered download gets you lihtc_huduser.csv, ZIP gets use LIHTCPUB.CSV
- [Data.gov](https://catalog.data.gov/dataset/low-income-housing-tax-credit-lihtc-properties), [OPD](https://hudgis-hud.opendata.arcgis.com/datasets/810ccb34dd464ec4ad4697d35fff21a5_11/about)
