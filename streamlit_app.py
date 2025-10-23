import json

import folium
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# Page configuration
st.set_page_config(
    page_title="LIHTC Properties in Philadelphia",
    page_icon="🏠",
    layout="wide"
)

st.title("🏠 LIHTC Properties in Philadelphia by Council District")

# Load and process LIHTC data
@st.cache_data
def load_lihtc_data():
    df = pd.read_csv('dashboard_data/properties.csv', dtype='str')
    # Convert lat/lng to numeric, handling any potential string values
    df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
    df['lng'] = pd.to_numeric(df['lng'], errors='coerce')
    df['numberofunits'] = pd.to_numeric(df['numberofunits'], errors='coerce')
    df['council_district'] = df['council_district'].astype(int).astype(str)
    df['senate_district'] = df['senate_district'].astype(int).astype(str)
    df['has_active_rental_license'] = df['has_active_rental_license'].astype(int).astype(bool)
    # Drop rows with invalid coordinates
    df['lhhp_certification_status'] = df['lhhp_certification_status'].fillna('Unknown')
    df['lhhp_status_type'] = df['lhhp_status_type'].fillna('Unknown')
    return df

# Load violations data
@st.cache_data
def load_violations_data():
    return pd.read_csv('dashboard_data/violations.csv', dtype='str')

@st.cache_data
def load_subsidies_data():
    return pd.read_csv('dashboard_data/subsidies.csv', dtype='str')

# Load data
lihtc_df = load_lihtc_data()

council_mapping = {
    '1': 'Mark Squilla',
    '2': 'Kenyatta Johnson',
    '3': 'Jamie Gauthier',
    '4': 'Curtis Jones Jr.',
    '5': 'Jeffery Young Jr.',
    '6': 'Michael Driscoll',
    '7': 'Quetcy Lozada',
    '8': 'Cindy Bass',
    '9': 'Anthony Phillips',
    '10': 'Brian J. O’Neill'
}

# Display total numbers above everything
st.subheader("📊 Total LIHTC Properties Overview")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Properties", f"{len(lihtc_df):,}")

with col2:
    total_units = lihtc_df['numberofunits'].sum()
    st.metric("Total Units", f"{total_units:,.0f}", help="Total number of housing units (based on rental license data) across all LIHTC properties in Philadelphia")

with col3:
    certified_properties = len(lihtc_df[lihtc_df['lhhp_certification_status'] == 'Certified'])
    st.metric("Lead Certified Properties", f"{certified_properties:,}")

with col4:
    avg_units = lihtc_df['numberofunits'].mean() if len(lihtc_df) > 0 else 0
    st.metric("Avg Units per Property", f"{avg_units:.1f}", help="Average number of housing units (based on rental license data) per LIHTC property in Philadelphia")

st.divider()

# Geographical Filters section
st.subheader("🌍 Geographical Filters")
col_geo1, col_geo2, col_geo3 = st.columns(3)

with col_geo1:
    # Council district filter with names
    council_options = ['All'] + sorted(lihtc_df['council_district'].dropna().unique().tolist())
    selected_district = st.selectbox(
        "Select a Council District:",
        options=council_options,
        format_func=lambda x: f'{x} - {council_mapping[x]}' if x!='All' else x,
        index=0
    )

with col_geo2:
    # Senate district filter
    senate_mapping = {'1': 'Saval, Nikil', '8': 'Williams, Anthony H.', '7': 'Hughes, Vincent J.', '2': 'Tartaglione, Christine M.', '4': 'Haywood, Arthur L., lll', '3': 'Street, Sharif T.', '5': 'Dillon, Jimmy'}
    senate_options = ['All'] + sorted(lihtc_df['senate_district'].dropna().unique().tolist())
    selected_senate = st.selectbox(
        "Select a Senate District:",
        format_func=lambda x: f'{x} - {senate_mapping[x]}' if x!='All' else x,
        options=senate_options,
        index=0
    )

with col_geo3:
    # Map overlay toggles
    st.write("**Map Overlays:**")
    show_council_districts = st.checkbox("Show Council Districts", value=False)
    show_senate_districts = st.checkbox("Show Senate Districts", value=False)

st.divider()

# Data Filters section
st.subheader("📊 Data Filters")
col_data1, col_data2, col_data3 = st.columns(3)

with col_data1:
    # Placeholder for future data filters
    pass

with col_data2:
    # Certification status filter (multiselect)
    cert_statuses = sorted(lihtc_df['lhhp_certification_status'].unique().tolist())
    selected_cert_statuses = st.multiselect(
        "Lead Certification Status:",
        options=cert_statuses,
        default=cert_statuses  # Show all by default
    )

with col_data3:
    # Rental license filter
    rental_license_options = ['All', 'Active', 'Inactive']
    selected_rental_license = st.selectbox(
        "Rental License Status:",
        options=rental_license_options,
        index=0,  # Default to "All"
        help="Filter by rental license status"
    )

# Additional data filter row
col_data4, col_data5 = st.columns(2)

with col_data4:
    # Number of units filter
    st.write("**Units Filter:**")
    units_filter_mode = st.radio(
        "Filter by Units:",
        options=["Include All", "Filter with Minimum"],
        index=1,  # Default to "Filter with Minimum"
        horizontal=True
    )
    
    if units_filter_mode == "Filter with Minimum":
        min_units = st.number_input(
            "Minimum Units:",
            min_value=0,
            value=20,
            step=1,
            help="Show only properties with at least this many units"
        )
    else:
        min_units = None

with col_data5:
    # LIHTC Max End Date year range filter
    st.write("**LIHTC Latest End Date Year Range:**")
    
    # Get available years from the data
    lihtc_df['Max End Date'] = pd.to_datetime(lihtc_df['Max End Date'], errors='coerce')
    available_years = sorted(lihtc_df['Max End Date'].dt.year.dropna().unique())
    
    if len(available_years) > 0:
        min_year = int(available_years[0])
        max_year = int(available_years[-1])
        
        year_range = st.slider(
            "Select Year Range:",
            min_value=min_year,
            max_value=max_year,
            value=(2025, 2035),
            step=1,
            help="Filter properties by LIHTC Max End Date year range"
        )
    else:
        year_range = None

# Apply filters
filtered_df = lihtc_df.copy()

# Filter by council district
if selected_district == 'All':
    district_title = "All LIHTC Properties in Philadelphia"
else:
    filtered_df = filtered_df[filtered_df['council_district'] == selected_district].copy()
    district_title = f"LIHTC Properties in Council District {selected_district}"

# Filter by senate district
if selected_senate != 'All':
    filtered_df = filtered_df[filtered_df['senate_district'] == selected_senate].copy()
    senate_title = f" in Senate District {selected_senate}"
else:
    senate_title = ""


# Filter by certification status
if len(selected_cert_statuses) == 0:
    # If no statuses selected, show no results
    filtered_df = filtered_df.iloc[0:0].copy()  # Empty dataframe with same structure
    status_title = " (No Status Selected)"
elif len(selected_cert_statuses) == len(cert_statuses):
    # If all statuses selected, don't filter
    status_title = ""
else:
    # Filter by selected statuses
    filtered_df = filtered_df[filtered_df['lhhp_certification_status'].isin(selected_cert_statuses)].copy()
    if len(selected_cert_statuses) == 1:
        status_title = f" with {selected_cert_statuses[0]} Status"
    else:
        status_title = f" with {', '.join(selected_cert_statuses)} Status"

# Filter by rental license status
if selected_rental_license == 'Active':
    # Filter for properties that have an active rental license
    filtered_df = filtered_df[filtered_df['has_active_rental_license'] == True].copy()
    rental_title = " with Active Rental License"
elif selected_rental_license == 'Inactive':
    # Filter for properties that do not have an active rental license
    filtered_df = filtered_df[filtered_df['has_active_rental_license'] == False].copy()
    rental_title = " with Inactive Rental License"
else:
    # Include all properties regardless of rental license status
    rental_title = ""

# Filter by number of units
if units_filter_mode == "Filter with Minimum" and min_units is not None:
    # Filter for properties with at least the minimum number of units
    filtered_df = filtered_df[filtered_df['numberofunits'] >= min_units].copy()
    units_title = f" with ≥{min_units} Units"
else:
    # Include all properties regardless of unit count
    units_title = ""

# Filter by LIHTC Max End Date year range
if year_range is not None:
    start_year, end_year = year_range
    # Convert Max End Date to datetime if not already done
    filtered_df['Max End Date'] = pd.to_datetime(filtered_df['Max End Date'], errors='coerce')
    # Filter by year range
    filtered_df = filtered_df[
        (filtered_df['Max End Date'].dt.year >= start_year) & 
        (filtered_df['Max End Date'].dt.year <= end_year)
    ].copy()
    year_title = f" with LIHTC Latest End Date {start_year}-{end_year}"
else:
    year_title = ""

# Create display title
display_title = district_title + senate_title + status_title + rental_title + units_title + year_title

# Display filtered counts
st.subheader("📈 Filtered Results")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Properties", f"{len(filtered_df):,}")

with col2:
    numberofunits = filtered_df['numberofunits'].sum()
    st.metric("Total Units", f"{numberofunits:,.0f}", help="Total number of housing units (based on rental license data) across all LIHTC properties in Philadelphia")

with col3:
    certified_properties = len(filtered_df[filtered_df['lhhp_certification_status'] == 'Certified'])
    st.metric("Lead Certified Properties", f"{certified_properties:,}")

with col4:
    avg_units = filtered_df['numberofunits'].mean() if len(filtered_df) > 0 else 0
    st.metric("Avg Units per Property", f"{avg_units:.1f}", help="Average number of housing units (based on rental license data) per LIHTC property in Philadelphia")

st.divider()

# Create a map centered on Philadelphia
m = folium.Map(
    location=[39.9526, -75.1652],  # Philadelphia coordinates
    zoom_start=11,
    tiles='OpenStreetMap'
)

# Add GeoJSON overlays based on toggles
if show_council_districts:
    council_geojson = folium.GeoJson(
        'geojson/Council_Districts_2024.geojson',
        style_function=lambda feature: {
            'fillColor': 'lightblue',
            'color': 'blue',
            'weight': 2,
            'fillOpacity': 0.1
        },
        tooltip=folium.GeoJsonTooltip(
            fields=['DISTRICT'],
            aliases=['Council District:'],
            localize=True
        )
    ).add_to(m)

if show_senate_districts:
    senate_geojson = folium.GeoJson(
        'geojson/PaSenatorial2024_03.geojson',
        style_function=lambda feature: {
            'fillColor': 'lightgreen',
            'color': 'green',
            'weight': 2,
            'fillOpacity': 0.1
        },
        tooltip=folium.GeoJsonTooltip(
            fields=['LEG_DISTRI', 'S_LASTNAME', 'S_FIRSTNAM'],
            aliases=['Senate District:', 'Senator:', ''],
            localize=True
        )
    ).add_to(m)

# Add individual property points to the map
def get_marker_color(row):
    """Get marker color based on subsidy status"""
    if row['Subsidy Status'] == 'Active':
        return 'green'
    elif row['Subsidy Status'] == 'Inactive':
        return 'red'
    elif row['Subsidy Status'] == 'Inconclusive':
        return 'orange'
    else:
        return 'gray'

# Add markers for each filtered property
for idx, row in filtered_df.iterrows():
    if pd.notna(row['lat']) and pd.notna(row['lng']):
        folium.CircleMarker(
            location=[row['lat'], row['lng']],
            radius=6,
            popup=folium.Popup(
                f"""
                <b>Address:</b> {row['parcel_address']}<br/>
                <b>Council District:</b> {row['council_district']}<br/>
                <b>Senate District:</b> {row['senate_district']}<br/>
                <b>Units (From Rental License):</b> {row['numberofunits']}<br/>
                <b>Subsidy Status:</b> {row['Subsidy Status']}<br/>
                <b>LIHTC Latest End Date:</b> {row['Max End Date']}
                """,
                max_width=300
            ),
            color='black',
            weight=1,
            fillColor=get_marker_color(row),
            fillOpacity=0.7
        ).add_to(m)

# Function to find the nearest property to clicked coordinates
def find_nearest_property(lat, lng, df):
    """Find the nearest property to the clicked coordinates"""
    if df.empty:
        return None
    
    # Calculate distance from clicked point to each property
    df['distance'] = ((df['lat'] - lat) ** 2 + (df['lng'] - lng) ** 2) ** 0.5
    
    # Return the nearest property
    nearest_idx = df['distance'].idxmin()
    return df.loc[nearest_idx]

# Map section
st.subheader("🗺️ Property Map")

# Add legend
st.markdown("**Map Legend:**")
legend_col1, legend_col2, legend_col3, legend_col4 = st.columns(4)

with legend_col1:
    st.markdown("🟢 **Active** - Subsidy is currently active")
with legend_col2:
    st.markdown("🔴 **Inactive** - Subsidy has expired or ended")
with legend_col3:
    st.markdown("🟠 **Inconclusive** - Subsidy status unclear")
with legend_col4:
    st.markdown("⚫ **Other** - Unknown or missing status")

map_data = st_folium(m, width=1200, height=600, returned_objects=["last_object_clicked"])

# Initialize session state for selected property
if 'selected_property' not in st.session_state:
    st.session_state.selected_property = None

# Check if a location was clicked
if map_data['last_object_clicked'] is not None:
    clicked_lat = map_data['last_object_clicked']['lat']
    clicked_lng = map_data['last_object_clicked']['lng']
    
    # Find the nearest property to the clicked coordinates
    nearest_property = find_nearest_property(clicked_lat, clicked_lng, filtered_df)
    
    if nearest_property is not None:
        st.session_state.selected_property = nearest_property['parcel_number']
        st.write(f"Clicked near property: {nearest_property['parcel_address']} (District {nearest_property['council_district']})")
    else:
        st.write("No properties found near clicked location")

st.divider()

# Display filtered properties table
st.subheader("📋 Property Details")
st.write(display_title)

# Select and rename columns for display
display_columns = {
    'parcel_address': 'Address',
    'council_district': 'Council District',
    'senate_district': 'Senate District',
    'numberofunits': 'Units (From RL)',
    'lhhp_certification_status': 'Lead Certification Status',
    'lhhp_cert_expiration_date': 'Lead Expiration Date',
    'Subsidy Status': 'LIHTC Status',
    'Max End Date': 'LIHTC Latest End Date',
    'num_associated_hud_properties': 'Associated HUD Properties'
}

# Filter to only show selected columns
display_df = filtered_df[list(display_columns.keys())].copy()

# Rename columns for better display
display_df = display_df.rename(columns=display_columns)

# Format date columns
if 'Certification Date' in display_df.columns:
    display_df['Certification Date'] = pd.to_datetime(display_df['Certification Date'], errors='coerce').dt.strftime('%Y-%m-%d')
if 'Expiration Date' in display_df.columns:
    display_df['Expiration Date'] = pd.to_datetime(display_df['Expiration Date'], errors='coerce').dt.strftime('%Y-%m-%d')

# Display the table
if len(display_df) > 0:
    # Initialize session state for selected row
    if 'selected_row' not in st.session_state:
        st.session_state.selected_row = None
    
    # Display the table with row selection
    selected_rows = st.dataframe(
        display_df,
        width='stretch',
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        key="property_table"
    )
    
    # Update selected row in session state
    if selected_rows.selection.rows:
        selected_idx = selected_rows.selection.rows[0]
        st.session_state.selected_row = selected_idx
    else:
        st.session_state.selected_row = None
    
    # Show detailed property information if a row is selected
    if st.session_state.selected_row is not None:
        st.divider()
        st.subheader("🔍 Selected Property Details")


        
        # Get the selected property data
        selected_property = filtered_df.iloc[st.session_state.selected_row]
        parcel_number = selected_property['parcel_number']

        # Create two columns for better layout
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Basic Information**")
            basic_info = {
                'Address': selected_property['parcel_address'],
                'Parcel Number': selected_property['parcel_number'],
                'Council District': selected_property['council_district'],
                'Senate District': selected_property['senate_district'],
                'Number of Units': selected_property['numberofunits'],
                'Latitude': selected_property['lat'],
                'Longitude': selected_property['lng']
            }
            
            for key, value in basic_info.items():
                st.write(f"**{key}:** {value}")
        
        with col2:
            st.write("**Certification & Compliance**")
            cert_info = {
                'Certification Status': selected_property['lhhp_certification_status'],
                'Certification Type': selected_property['lhhp_status_type'],
                'Certification Date': selected_property['lhhp_cert_date'],
                'Expiration Date': selected_property['lhhp_cert_expiration_date'],
                'Has Active Rental License': selected_property['has_active_rental_license']
            }
            
            for key, value in cert_info.items():
                st.write(f"**{key}:** {value}")
        
        # Property violations section - as a prominent subcategory
        st.markdown("---")  # Add a divider line
        st.markdown("### 🚨 Property Violations (Last 5 Years)")
        
        # Load violations data from CSV
        df_all_violations = load_violations_data()
        df_violations = df_all_violations[df_all_violations['opa_account_num'] == parcel_number].copy()
        
        # Filter to last 5 years
        if not df_violations.empty:
            df_violations['violationdate'] = pd.to_datetime(df_violations['violationdate'], errors='coerce')
            five_years_ago = pd.Timestamp.now() - pd.DateOffset(years=5)
            df_violations = df_violations[df_violations['violationdate'] >= five_years_ago].copy()
            df_violations = df_violations.sort_values('violationdate', ascending=False)
        
        if not df_violations.empty:
            # Create a container with background color for violations section
            with st.container():
                st.markdown("**Violation Summary by Type:**")
                violation_counts = df_violations.groupby('violationcodetitle').size().reset_index(name='count')
                violation_counts = violation_counts.sort_values('count', ascending=False)
                
                # Display the summary table
                st.dataframe(
                    violation_counts,
                    width='stretch',
                    hide_index=True,
                    column_config={
                        "violation_code_title": "Violation Type",
                        "count": "Count"
                    }
                )
                
                # Show total violations with emphasis
                total_violations = len(df_violations)
                st.markdown(f"**Total Violations (Last 5 Years):** `{total_violations}`")
                
                # Show detailed violations in an expandable section
                with st.expander("📋 View All Violation Details"):
                    st.dataframe(
                        df_violations,
                        width='stretch',
                        hide_index=True,
                    )
        else:
            st.info("✅ No violations found for this property in the last 5 years")
        
        # Property subsidies section - as a prominent subcategory
        st.markdown("---")  # Add a divider line
        st.markdown("### 💰 Property Subsidies")
        
        # Load subsidies data from CSV
        df_all_subsidies = load_subsidies_data()
        df_subsidies = df_all_subsidies[df_all_subsidies['parcel_number'] == parcel_number].copy()
        
        if not df_subsidies.empty:
            # Create a container for subsidies section
            with st.container():
                st.markdown("**Subsidy Summary by Type:**")
                subsidy_counts = df_subsidies.groupby('Subsidy Name').size().reset_index(name='count')
                subsidy_counts = subsidy_counts.sort_values('count', ascending=False)
                
                # Display the summary table
                st.dataframe(
                    subsidy_counts,
                    width='stretch',
                    hide_index=True,
                    column_config={
                        "count": "Count"
                    }
                )
                
                # Show total subsidies with emphasis
                total_subsidies = len(df_subsidies)
                st.markdown(f"**Total Subsidies:** `{total_subsidies}`")
                
                # Show detailed subsidies in an expandable section
                with st.expander("📋 View All Subsidy Details"):
                    st.dataframe(
                        df_subsidies,
                        width='stretch',
                        hide_index=True,
                    )
        else:
            st.info("ℹ️ No subsidies found for this property")
        
        # Additional details in full width
        st.write("**Additional Details**")
        additional_info = {
            'Max End Date': selected_property['Max End Date'],
            'Associated HUD Properties': selected_property['num_associated_hud_properties'],
            'Property Type': selected_property.get('property_type', 'N/A'),
            'Owner Name': selected_property.get('owner_name', 'N/A'),
            'Owner Address': selected_property.get('owner_address', 'N/A')
        }
        
        # Display additional info in a more compact format
        info_cols = st.columns(3)
        for i, (key, value) in enumerate(additional_info.items()):
            with info_cols[i % 3]:
                st.write(f"**{key}:** {value}")
        
        # Show all available columns in an expandable section
        with st.expander("📋 All Property Data (Raw)"):
            # Get all columns and their values
            all_data = selected_property.to_dict()
            
            # Create a more readable format
            for col, val in all_data.items():
                if pd.notna(val) and val != '':
                    st.write(f"**{col}:** {val}")
                else:
                    st.write(f"**{col}:** *No data*")
        
        # Add a button to clear selection
        if st.button("Clear Selection", type="secondary"):
            st.session_state.selected_row = None
            st.rerun()
        
else:
    st.info(f"No LIHTC properties found matching the selected filters")
