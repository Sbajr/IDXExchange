import pandas as pd
import os

# --- SETTINGS ---
root_path = r'C:\Users\samba\Downloads' 
current_folder = os.path.dirname(os.path.abspath(__file__))

# 1. DATA INGESTION
listing_dfs = []
print("--- STAGE 1: INGESTION (RECURSIVE SEARCH) ---")
for root, dirs, files in os.walk(root_path):
    if 'raw' in root or 'crmls' in root:
        continue
    for file in files:
        if file.startswith('CRMLSListing') and file.endswith('.csv'):
            full_path = os.path.join(root, file)
            try:
                temp_df = pd.read_csv(full_path, low_memory=False)
                listing_dfs.append(temp_df)
                print(f"Loaded: {full_path} | Rows: {len(temp_df)}")
            except Exception as e:
                print(f"Error loading {file}: {e}")

if not listing_dfs:
    print("No Listing files found. Exiting.")
    exit()

df_listing = pd.concat(listing_dfs, ignore_index=True)
df_listing = df_listing.drop_duplicates()

# 2. PROPERTY TYPE FILTERING
df_listing = df_listing[df_listing['PropertyType'] == 'Residential']

# 3. MORTGAGE RATE ENRICHMENT 
print("\n--- STAGE 4: FRED MORTGAGE MERGE ---")
try:
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
    mortgage = pd.read_csv(url)
    mortgage.columns = [col.lower() for col in mortgage.columns]
    date_col_name = 'date' if 'date' in mortgage.columns else 'observation_date'
    mortgage[date_col_name] = pd.to_datetime(mortgage[date_col_name])
    mortgage.columns = ['date', 'rate_30yr_fixed']
    mortgage['year_month'] = mortgage['date'].dt.to_period('M')
    mortgage_monthly = mortgage.groupby('year_month')['rate_30yr_fixed'].mean().reset_index()
    
    def find_col_list(names, df):
        for n in names:
            for c in df.columns:
                if c.strip().lower() == n.lower(): return c
        return None

    date_col = find_col_list(['ListingContractDate', 'Listing Contract Date', 'ListingDate'], df_listing)
    if date_col:
        df_listing['year_month'] = pd.to_datetime(df_listing[date_col]).dt.to_period('M')
        df_listing = df_listing.merge(mortgage_monthly, on='year_month', how='left')
        print(f"Merge Complete. Validation (Null Rates): {df_listing['rate_30yr_fixed'].isnull().sum()}")
except Exception as e:
    print(f"Mortgage Merge Failed: {e}")

# 5. WEEKS 4-5 DATA CLEANING & LOGIC CHECKS
print("\n--- STAGE 5: DATA CLEANING & LOGIC CHECKS ---")
price_c = find_col_list(['ListPrice', 'List Price'], df_listing)
area_c = find_col_list(['LivingArea', 'Living Area'], df_listing)
dom_c = find_col_list(['DaysOnMarket', 'Days On Market'], df_listing)

# Physical Flags
df_listing['invalid_phys_attr_flag'] = False
if price_c: df_listing.loc[df_listing[price_c] <= 0, 'invalid_phys_attr_flag'] = True
if area_c: df_listing.loc[df_listing[area_c] <= 0, 'invalid_phys_attr_flag'] = True
if dom_c: df_listing.loc[df_listing[dom_c] < 0, 'invalid_phys_attr_flag'] = True

# Geo Flags
lat_c, lon_c = find_col_list(['Latitude'], df_listing), find_col_list(['Longitude'], df_listing)
df_listing['geo_error_flag'] = False
if lat_c and lon_c:
    df_listing[lat_c] = pd.to_numeric(df_listing[lat_c], errors='coerce')
    df_listing[lon_c] = pd.to_numeric(df_listing[lon_c], errors='coerce')
    df_listing['geo_error_flag'] = (df_listing[lon_c] > 0) | (df_listing[lat_c] == 0)

print(f"Flags - Invalid Phys: {df_listing['invalid_phys_attr_flag'].sum()} | Geo: {df_listing['geo_error_flag'].sum()}")

# 6. WEEK 6 FEATURE ENGINEERING & METRICS
print("\n--- STAGE 6: FEATURE ENGINEERING & METRICS ---")
if price_c and area_c:
    df_listing['Expected_PPSF'] = df_listing[price_c] / df_listing[area_c]
    
if date_col:
    df_listing['Year'] = pd.to_datetime(df_listing[date_col]).dt.year
    df_listing['Month'] = pd.to_datetime(df_listing[date_col]).dt.month
    df_listing['YrMo'] = pd.to_datetime(df_listing[date_col]).dt.to_period('M').astype(str)

# 7. WEEK 6 SEGMENT ANALYSIS
prop_type_c = find_col_list(['PropertySubType', 'PropertyType'], df_listing)
if prop_type_c and price_c:
    print(f"\n--- STAGE 7: SEGMENT ANALYSIS BY {prop_type_c} ---")
    summary_cols = {price_c: 'median'}
    if 'Expected_PPSF' in df_listing.columns: summary_cols['Expected_PPSF'] = 'mean'
    if dom_c: summary_cols[dom_c] = 'median'
    
    type_summary = df_listing.groupby(prop_type_c).agg(summary_cols).reset_index()
    print(type_summary.head())

# 8. WEEK 7 OUTLIER DETECTION (IQR METHOD)
print("\n--- STAGE 8: OUTLIER DETECTION (IQR) ---")
df_listing['is_outlier'] = False
initial_rows = len(df_listing)
median_before = df_listing[price_c].median() if price_c else None

for col in [price_c, area_c, dom_c]:
    if col and col in df_listing.columns:
        Q1 = df_listing[col].quantile(0.25)
        Q3 = df_listing[col].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        # Flag if outside bounds (ignore NaN)
        outlier_mask = (df_listing[col].notna()) & ((df_listing[col] < lower_bound) | (df_listing[col] > upper_bound))
        df_listing.loc[outlier_mask, 'is_outlier'] = True

df_listing_clean = df_listing[~df_listing['is_outlier']].copy()
final_rows = len(df_listing_clean)
median_after = df_listing_clean[price_c].median() if price_c else None

print(f"Original Rows: {initial_rows} | Filtered Rows: {final_rows} | Outliers Removed: {initial_rows - final_rows}")
print(f"Median {price_c} Before: {median_before} | After: {median_after}")

# 9. EXPORT
output_flagged = os.path.join(current_folder, 'Master_Listing_Flagged.csv')
output_filtered = os.path.join(current_folder, 'Master_Listing_Filtered.csv')

df_listing.to_csv(output_flagged, index=False)
df_listing_clean.to_csv(output_filtered, index=False)
print(f"\n--- SUCCESS: Saved Flagged Dataset to {output_flagged} ---")
print(f"--- SUCCESS: Saved Clean Filtered Dataset to {output_filtered} ---")