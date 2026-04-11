import pandas as pd
import os

# 1. Define where to search
root_path = r'C:\Users\samba\Downloads' 

listing_dfs = []
print("--- STARTING FILE INGESTION (LISTED TRANSACTIONS) ---")

# 2. Search through all folders and subfolders
for root, dirs, files in os.walk(root_path):
    for file in files:
        # 3. STRICT FILTER: Only grab files matching the exact Listing naming convention
        if file.startswith('CRMLSListing') and file.endswith('.csv'):
            full_path = os.path.join(root, file)
            
            try:
                # low_memory=False prevents the mixed data type warning
                temp_df = pd.read_csv(full_path, low_memory=False)
                listing_dfs.append(temp_df)
                
                # VALIDATION LAYER 1: Row count for each individual file
                print(f"Success - Loaded {file}: {len(temp_df)} rows")
            except Exception as e:
                print(f"Error reading {file}: {e}")

# 4. Combine, Validate, Clean, and Export
if listing_dfs:
    # Merge them all together
    df_listing = pd.concat(listing_dfs, ignore_index=True)
    
    # VALIDATION LAYER 2: Row count after concatenation
    print("\n" + "="*40)
    print("--- CONCATENATION COMPLETE ---")
    print(f"Total rows combined (Pre-Filter): {len(df_listing)}")
    print("="*40)

    # VALIDATION LAYER 3: Frequency table before filtering
    print("\n--- PROPERTY TYPES (BEFORE FILTER) ---")
    if 'PropertyType' in df_listing.columns:
        print(df_listing['PropertyType'].value_counts(dropna=False))
    else:
        print("WARNING: 'PropertyType' column not found!")

    # FILTER: Keep only 'Residential'
    if 'PropertyType' in df_listing.columns:
        df_listing = df_listing[df_listing['PropertyType'] == 'Residential']

    # VALIDATION LAYER 4: Row count after filtering
    print("\n" + "="*40)
    print("--- FILTERING COMPLETE ---")
    print(f"Total rows (Post-Residential Filter): {len(df_listing)}")
    print("="*40)

    # VALIDATION LAYER 5: Frequency table after filtering
    print("\n--- PROPERTY TYPES (AFTER FILTER) ---")
    if 'PropertyType' in df_listing.columns:
        print(df_listing['PropertyType'].value_counts(dropna=False))
    
    # --- CLEANING & FEATURES ---
    # Fix the List Price column (remove $, commas, convert to float)
    if 'List Price' in df_listing.columns:
        df_listing['List Price'] = df_listing['List Price'].replace(r'[\$,]', '', regex=True).astype(float)

    # Export to the final CSV
    df_listing.to_csv('Master_Listing_Analysis.csv', index=False)
    print("\n--- COMPLETE: Master_Listing_Analysis.csv is ready for Tableau! ---")
else:
    print("\nNo Listing files were found in your Downloads.")