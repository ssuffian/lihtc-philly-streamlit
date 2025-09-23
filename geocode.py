import os
import shutil
import sqlite3
import tempfile
from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd
import typer

pd.set_option('display.max_rows', 500)
pd.set_option('display.width', 150)

app = typer.Typer()

def _create_temp_sql(filepath):
    temp_dir = '.'
    temp_db_path = os.path.join(temp_dir, 'temp.db')
    shutil.copy2(filepath, temp_db_path)
    return temp_db_path

# Take the parcel numbers from the LIHTC Properties and get all associated parcels
@app.command()
def get_associated_parcels(
    input_file: str = typer.Option("data/All Properties (Philly, Geocode Attempt) - geocoded_results.csv", help="Input CSV file with parcel data"),
    output_file: str = typer.Option("data/all_parcels.csv", help="Output CSV file for all parcels")
):
    """Get all associated parcels from LIHTC properties using RTT data."""
    typer.echo(f"Loading parcel data from {input_file}")
    df_parcels_orig = pd.read_csv(input_file, dtype='str')


    parcel_col = 'parcel_number / OPA Number'
    df_parcels_orig = df_parcels_orig.rename(columns={parcel_col: 'parcel_number'})

    # REMOVE parcel_number that is just a dash
    empty_parcel_num_str = ['-','scattered site',np.nan]
    unknown_df = df_parcels_orig[df_parcels_orig['parcel_number'].isin(empty_parcel_num_str)]
    property_names = ','.join(unknown_df['Property Name'].tolist())
    typer.echo(f"Removed {len(unknown_df)} LIHTC Properties with an unknown OPA Number: {property_names}")
    df_parcels_orig = df_parcels_orig[~df_parcels_orig['parcel_number'].isin(empty_parcel_num_str)]
    df_parcels_orig['parcel_number'] = df_parcels_orig['parcel_number'].astype(str).str.zfill(9)

    typer.echo("Creating temporary database...")
    temp_db_path = _create_temp_sql('data/open_data_philly.db')
    con = sqlite3.connect(temp_db_path)

    typer.echo("Processing parcels...")
    df_parcels_orig.to_sql('parcels', con, if_exists='replace', index=False)

    df_parcels = pd.read_sql('''
        SELECT parcels.*, rtt_summary.document_id FROM parcels 
        left join (
            select opa_account_num, cast(max(document_id) as integer) as document_id from rtt_summary group by opa_account_num
        ) rtt_summary
        on parcels.parcel_number = rtt_summary.opa_account_num
    ''', con)

    df_parcels = df_parcels[['NHPD Property ID','Property Name', 'Property Address', 'parcel_number', 'document_id']].rename(columns={'Property Name':'lihtc_property_name', 'Property Address':'lihtc_property_address', 'parcel_number':'lihtc_property_parcel_number','NHPD Property ID':'nhpd_property_id'})
    df_parcels.to_sql('parcels', con, if_exists='replace', index=False)
    
    typer.echo("Finding associated addresses...")
    df_addresses = pd.read_sql('''
        SELECT parcels.nhpd_property_id, parcels.lihtc_property_name, parcels.lihtc_property_address, parcels.lihtc_property_parcel_number, cast(parcels.document_id as integer) as document_id, rtt_summary.street_address as parcel_address, rtt_summary.opa_account_num as parcel_number FROM parcels 
        join rtt_summary
        on parcels.document_id = rtt_summary.document_id
    ''', con).drop_duplicates()

    # Remove duplicates due to mulitple NHPD IDs per address (like the 1720/1724 W GIRARD AVE)
    def _remove_duplicates(group):
        group['nhpd_property_ids'] = ','.join(group['nhpd_property_id'].tolist())
        if len(group) > 1:
            group['duplicated'] = True
            address_match = group[group['lihtc_property_address'].str.upper() == group['parcel_address']]
            # If there is an exact match in the group, only return that
            if len(address_match) > 0:
                return address_match
            # Otherwise return all of them
            return group
        group['duplicated'] = False
        return group

    # df_deduped_addresses = df_addresses.groupby('parcel_number').apply(_remove_duplicates, include_groups=False).reset_index()

    df_addresses_no_deeds = df_parcels[df_parcels['document_id'].isna()].copy()
    df_addresses_no_deeds['parcel_address'] = df_addresses_no_deeds['lihtc_property_address']
    df_addresses_no_deeds['parcel_number'] = df_addresses_no_deeds['lihtc_property_parcel_number']
    df_addresses_out = pd.concat([df_addresses, df_addresses_no_deeds]).rename(columns={'document_id':'rtt_document_id'})
    
    typer.echo(f"Saving results to {output_file}")
    df_addresses_out.to_csv(output_file, index=False)

    con.close()
    os.remove(temp_db_path)
    typer.echo(f"✅ Successfully processed {len(df_addresses)} parcels from {len(df_parcels_orig)} LIHTC properties")
    
    
@app.command()
def generate_db_for_dashboard(
    parcels_filepath: str = typer.Option("data/all_parcels.csv", help="Input CSV file with parcel data"),
    subsidies_filepath: str = typer.Option("data/All Subsidies.xlsx - Philly.csv", help="Input CSV file with subsidies data"),
    lead_filepath: str = typer.Option("data/lhhp_lead_certifications.csv", help="Input CSV file with lead data"),
    open_data_philly_filepath: str = typer.Option("data/open_data_philly.db", help="Input database file with open data philly data"),
):
    """Generate database for dashboard with rental license information."""

    typer.echo("Creating temporary database...")
    temp_db_path = _create_temp_sql(open_data_philly_filepath)
    con = sqlite3.connect(temp_db_path)

    typer.echo(f"Loading parcel data")
    df_parcels = pd.read_csv(parcels_filepath, dtype='str')
    df_unique_parcels = df_parcels[['parcel_number', 'parcel_address']].value_counts()
    df_unique_parcels = df_unique_parcels.reset_index().rename(columns={'count':'num_associated_hud_properties'})
    df_unique_parcels.to_sql('parcels', con, if_exists='replace', index=False)

    typer.echo("Processing lead data...")
    df_lead = pd.read_csv(lead_filepath, dtype='str')
    df_lead = df_lead.dropna(subset=['li_rl_license']).set_index('opa_account')[['lhhp_status_type','lhhp_certification_status','lhhp_cert_date','lhhp_cert_expiration_date']]



    typer.echo("Processing rental licenses...")
    df_rental_license = pd.read_sql("""
        SELECT parcel_number, parcel_address, max(numberofunits) as numberofunits, max(num_associated_hud_properties) as num_associated_hud_properties, licensestatus is not null as has_active_rental_license
        from parcels 
        LEFT JOIN business_licenses
        ON business_licenses.opa_account_num = parcels.parcel_number
        AND licensestatus='Active'
        GROUP BY parcel_number, parcel_address
    """, con=con)
    df_rental_license = df_rental_license.drop_duplicates()

    df_nhpd_to_parcel_mapping = df_parcels[['nhpd_property_id', 'parcel_number']].dropna()


    typer.echo(f"Loading subsidy data")
    df_subsidies = pd.read_csv(subsidies_filepath, dtype='str')
    df_subsidies['End Date'] = pd.to_datetime(df_subsidies['End Date'])
    df_lihtc_subsidies = df_subsidies[df_subsidies['Subsidy Name']=='LIHTC']
    df_min_dates = df_lihtc_subsidies.groupby('NHPD Property ID')['End Date'].min()
    df_min_dates.name = 'Min End Date'
    
    # End Date subsidy
    df = pd.merge(
        df_nhpd_to_parcel_mapping,
        df_min_dates,
        left_on=['nhpd_property_id'],
        right_on=['NHPD Property ID'],
        how='left'
    )
    # Get ones with no_lihtc
    # df_parcels[df_parcels.nhpd_property_id.isin(df[df['Min End Date'].isna()].nhpd_property_id.drop_duplicates())][['nhpd_property_id','lihtc_property_name','lihtc_property_address']].drop_duplicates().to_csv('no_lihtc.csv')
    df = df.dropna(subset=['Min End Date'])
    df = df.groupby('parcel_number')[['Min End Date']].min()

    df_w_rental = df.join(df_rental_license.set_index('parcel_number'))
    df_w_rental = df_w_rental.join(df_lead)


    df_lat_lngs = pd.read_sql("""
        SELECT parcels.parcel_number, lat, lng from parcels 
        LEFT JOIN opa_properties_public
        ON opa_properties_public.parcel_number = parcels.parcel_number
    """, con=con).set_index('parcel_number')
    df_w_rental = df_w_rental.join(df_lat_lngs)

    # Add spatial joins for council district and senate district
    typer.echo("Adding spatial joins for council and senate districts...")
    
    # Load GeoJSON files
    council_districts = gpd.read_file('geojson/Council_Districts_2024.geojson')
    senate_districts = gpd.read_file('geojson/PaSenatorial2024_03.geojson')
    
    # Create GeoDataFrame from the rental data with coordinates
    df_with_coords = df_lat_lngs.dropna(subset=['lat', 'lng']).copy()
    gdf_with_coords = gpd.GeoDataFrame(
        df_with_coords,
        geometry=gpd.points_from_xy(df_with_coords['lng'], df_with_coords['lat']),
        crs='EPSG:4326'
    )
    
    # Ensure both GeoDataFrames have the same CRS
    council_districts = council_districts.to_crs('EPSG:4326')
    senate_districts = senate_districts.to_crs('EPSG:4326')
    
    # Perform spatial joins
    gdf_with_council = gpd.sjoin(gdf_with_coords, council_districts, how='left', predicate='within')['DISTRICT'].to_frame('council_district')
    gdf_with_senate = gpd.sjoin(gdf_with_coords, senate_districts, how='left', predicate='within')[['LEG_DISTRI']].rename(columns={'LEG_DISTRI':'senate_district'})
    
    # Join back to the main dataframe
    df_w_rental = df_w_rental.merge(gdf_with_council, on='parcel_number', how='left').merge(gdf_with_senate, on='parcel_number', how='left')

    df_w_rental.to_csv('dashboard_data/properties.csv')
    df_violations = pd.read_sql("""
        SELECT * from parcels join violations on parcels.parcel_number = violations.opa_account_num where violations.violationdate >= date('now', '-5 years')
    """, con=con)
    df_violations.to_csv('dashboard_data/violations.csv')

    df_joined_subsidies = pd.merge(
        df_nhpd_to_parcel_mapping,
        df_subsidies,
        left_on=['nhpd_property_id'],
        right_on=['NHPD Property ID'],
        how='inner'
    )
    df_joined_subsidies.to_csv('dashboard_data/subsidies.csv')

    con.close()
    os.remove(temp_db_path)


if __name__ == '__main__':
    app()