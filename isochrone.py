import osmnx as ox
import networkx as nx
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import unary_union
import pandas as pd

#We start looking in Eindhoven, but we can change this later on when wanted
place = "Eindhoven, Netherlands"

#We get the open source biking network in the Netherlands
G = ox.graph_from_place(place, network_type='bike') #For now we are only looking at the bike network in Eindhoven
G = ox.project_graph(G) #project graph to meters

#Calculate travel time for each edge based on length and an average biking speed of 18 km/h
for u, v, k, data in G.edges(keys=True, data=True):
    length = data['length']  # meters
    speed = (18/3.6) # m/s (18 km/h)
    data['travel_time'] = length / speed


#Pick a starting node, we chose the center of Eindhoven, but this can be changed to any point in the city
center_point = (51.4416, 5.4697)  # Eindhoven center
center_node = ox.distance.nearest_nodes(G, center_point[1], center_point[0])

#Make radius of where the local path is
subgraph = nx.ego_graph(G, center_node, radius=600, distance='travel_time') #10 minutes = 600 seconds

#Get node points
nodes, edges = ox.graph_to_gdfs(subgraph)

#Buffer nodes to create area
node_points = nodes.geometry
isochrone = unary_union(node_points.buffer(50))  # 50m smoothing


#Intersect with buurt boundaries from the CBS data

df_kwb2025 = pd.read_excel(r'C:\Users\20192436\Projects\DesignforAI\Data\CBS\kwb2025.xlsx')


gdf = gpd.read_file(r"C:\Users\20212599\OneDrive - TU Eindhoven\Documents\Studie\2025-2026\1BM130 Design of AI-driven business operation\Shared group folder\Data files\CBS\wijkenbuurten_2025_v1.gpkg", layer='buurten')
#print(gdf.head())
#print(gdf.columns)

gdf = gdf[~gdf['buurtnaam'].isin([
    'Buitenland',
    'Groot binnenwater',
    'Buitenwater'
])]


#Now we want to merge the geocoordinates with the data from CBS about the distances
df_kwb2025 = pd.read_excel(r'C:\Users\20212599\OneDrive - TU Eindhoven\Documents\Studie\2025-2026\1BM130 Design of AI-driven business operation\Shared group folder\Data files\CBS\kwb2025.xlsx')

df_kwb2025['gwb_code'] = df_kwb2025['gwb_code'].str.upper()
gdf['buurtcode'] = gdf['buurtcode'].str.upper()

#Merge the datasets on the buurtcode and gwb_code, which should be the same for each buurt
merged = gdf.merge(df_kwb2025, left_on='buurtcode', right_on='gwb_code')
#Sanity check; to see whether the merge has approximately the same amount of rows as the original gdf file
#print(len(gdf))
#print(len(merged))
#Sanity check; to see wehther the merged crs has the correct type of coordinate system (it should be in meters, not in lat/lon)
#print(merged.crs)

#Make the isochrone and project it onto the merged crs, so that we can intersect it with the buurt boundaries
isochrone = gpd.GeoSeries([isochrone], crs=G.graph['crs']).to_crs(merged.crs)


merged['intersection_area'] = merged.geometry.intersection(isochrone.iloc[0]).area
merged['weight'] = (
    merged['intersection_area'] /
    merged.geometry.area
)

# Example: weighted population
accessible_pop = (merged['aantal_inwoners'] * merged['weight']).sum()
print(f"Estimated population within 10 minutes biking from the city centre of Eindhoven: {accessible_pop:.0f}")

print("Rows:", merged.shape[0])
print("Columns:", merged.shape[1])
print("\nColumn names:")
print(merged.columns.tolist())

print("\nMissing values per column:")
print(merged.isna().sum())



# ---------------------------------------------------------
# 1. DESCRIPTIVE STATS FOR ALL NUMERIC COLUMNS
# ---------------------------------------------------------
numeric_cols = merged.select_dtypes(include='number').columns
print("\nNumeric column summary:")
print(merged[numeric_cols].describe().T)

# ---------------------------------------------------------
# 2. SPATIAL DESCRIPTIVES
# ---------------------------------------------------------
merged['area_m2'] = merged.geometry.area

print("\nTop 10 buurten by share inside isochrone:")
print(
    merged[['buurtnaam', 'area_m2', 'intersection_area', 'weight']]
    .sort_values('weight', ascending=False)
    .head(10)
)

# ---------------------------------------------------------
# 3. ACCESSIBLE POPULATION
# ---------------------------------------------------------
accessible_pop = (merged['aantal_inwoners'] * merged['weight']).sum()
print(f"\nEstimated population within 10 minutes biking: {accessible_pop:.0f}")

merged['accessible_pop'] = merged['aantal_inwoners'] * merged['weight']

print("\nTop 10 buurten contributing most to accessible population:")
print(
    merged[['buurtnaam', 'accessible_pop']]
    .sort_values('accessible_pop', ascending=False)
    .head(10)
)

merged['share_pop_accessible'] = merged['accessible_pop'] / merged['aantal_inwoners']

# ---------------------------------------------------------
# 4. SOCIO-ECONOMIC DESCRIPTIVES
# ---------------------------------------------------------
# CBS 2025 uses different naming conventions → we select by patterns
socio_cols = [
    col for col in merged.columns 
    if "ink" in col.lower()          # income
    or "migratie" in col.lower()     # migration background
    or "huur" in col.lower()         # rental housing
    or "eengezins" in col.lower()    # single-family housing
]

print("\nSocio-economic variable summary:")
print(merged[socio_cols].describe().T)

# ---------------------------------------------------------
# 5. ACCESSIBILITY GROUPS
# ---------------------------------------------------------
for col in merged.columns:
    if merged[col].dtype == object:
        merged[col] = pd.to_numeric(merged[col], errors='coerce')

# ---------------------------------------------------------
# ACCESSIBILITY GROUPS
# ---------------------------------------------------------
merged['access_group'] = pd.cut(
    merged['weight'],
    bins=[-0.01, 0, 0.5, 1],
    labels=['outside', 'partial', 'mostly_inside']
)

# CBS 2025 income variable
income_var = "g_ink_po"

print("\nGroup comparison (population + income):")
print(
    merged.groupby('access_group')[['aantal_inwoners', income_var]].mean()
)


import matplotlib.pyplot as plt
import seaborn as sns


inside = merged[merged['weight'] > 0]

print("Number of buurten inside isochrone:", len(inside))

merged['inside_binary'] = merged['weight'].apply(lambda w: 'inside' if w > 0 else 'outside')

plot_df = merged.dropna(subset=['g_ink_po'])

plt.figure(figsize=(8,6))
sns.boxplot(
    data=plot_df,
    x='inside_binary',
    y='g_ink_po',
    hue='inside_binary',
    palette='Set2',
    legend=False
)
plt.title("Income comparison: inside vs outside 10-minute biking zone")
plt.xlabel("Buurt category")
plt.ylabel("Average income per person (g_ink_po)")
plt.tight_layout()
plt.show()


plt.figure(figsize=(8,5))
sns.histplot(
    inside['weight'],
    bins=20,
    kde=True,
    color='steelblue'
)
plt.title("Distribution of weights (only buurten inside isochrone)")
plt.xlabel("Weight (0–1)")
plt.ylabel("Count of buurten")
plt.tight_layout()
plt.show()



print("Geometry type:", merged.geometry.geom_type.unique())
print("CRS:", merged.crs)

fig, ax = plt.subplots(figsize=(10,10))
merged.plot(
    column='weight',
    cmap='viridis',
    linewidth=0.5,
    edgecolor='black',
    legend=True,
    ax=ax
)
plt.title("Buurten colored by share inside 10-minute biking isochrone")
plt.axis('off')
plt.show()


fig, ax = plt.subplots(figsize=(10,10))

merged.plot(
    column='accessible_pop',
    cmap='plasma',
    linewidth=0.5,
    edgecolor='black',
    legend=True,
    ax=ax
)

plt.title("Accessible population per buurt")
plt.axis('off')
plt.show()


