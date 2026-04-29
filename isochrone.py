import osmnx as ox
import networkx as nx
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import unary_union

place = "Eindhoven, Netherlands"

# Get bike network
G = ox.graph_from_place(place, network_type='bike')

# Project graph to meters
G = ox.project_graph(G)

# Add travel time (seconds)
for u, v, k, data in G.edges(keys=True, data=True):
    length = data['length']  # meters
    speed = (18/3.6) # m/s (18 km/h)
    data['travel_time'] = length / speed



# Pick a starting node (e.g., centroid of a buurt)
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
buurten = gpd.read_file("cbs_buurten.shp")
buurten = buurten.to_crs(G.graph['crs'])