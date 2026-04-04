import pandas as pd
import os

# 1. Define where to search
root_path = r'C:\Users\samba\Downloads' 

listing_dfs = []
print("Scanning Downloads for Listed transactions...")

# 2. Search through all folders and subfolders
for root, dirs, files in os.walk(root_path):
    for file in files:
        # 3. STRICT FILTER: Only grab files matching the exact Listing naming convention
        if file.startswith('CRMLSListing') and file.endswith('.csv'):
            full_path = os.path.join(root, file)
            
            try:
                temp_df = pd.read_csv(full_path)
                listing_dfs.append(temp_df)
                print(f"Success - Loaded: {file}")
            except Exception as e:
                print(f"Error reading {file}: {e}")

# 4. Combine, Clean, and Export
if listing_dfs:
    # Merge them all together
    df_listing = pd.concat(listing_dfs, ignore_index=True)
    
    # --- CLEANING & FEATURES ---
    # Fix the List Price column (remove $, commas, convert to float)
    if 'List Price' in df_listing.columns:
        df_listing['List Price'] = df_listing['List Price'].replace(r'[\$,]', '', regex=True).astype(float)

    # Export to the final CSV
    df_listing.to_csv('Master_Listing_Analysis.csv', index=False)
    print("\n--- COMPLETE: Master_Listing_Analysis.csv is ready for Tableau! ---")
else:
    print("\nNo Listing files were found in your Downloads.")