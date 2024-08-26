#!/usr/bin/env python
# coding: utf-8

import json
import geopandas as gpd
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import date
from shapely.geometry import Point
import folium
from folium.plugins import HeatMap


# Load the JSON file
with open('polygons.json', 'r') as file:
    file = json.load(file)

# Top level object is a list converting it to a dict to be able to convert it to a geodataframe
to_dict = file[0]

gdf_polygons = gpd.GeoDataFrame.from_features(to_dict['features'], crs="EPSG:4326")

# Reading orders file
df_orders = pd.read_csv('orders.csv')

# Create geometry for orders
geometry = [Point(xy) for xy in zip(df_orders.lng, df_orders.lat)]

# Create GeoDataFrame
gdf_orders = gpd.GeoDataFrame(df_orders, geometry=geometry, crs="EPSG:4326")

# Finding points which lie on the border
touches = gpd.sjoin(gdf_orders, gdf_polygons, how='left', predicate='touches')
border_points = touches[touches['index_right'].notna()]
uniq_border_points = border_points.drop_duplicates(subset='geometry', keep='first') #For the sake of this assignment keep first is fine, but may change it based on business needs for example to balance orders distribtuion based on resources allocation

# Finding points inside polygons (Execluding on border)
within = gpd.sjoin(gdf_orders, gdf_polygons, how='left', predicate='within')
within_points = within[within['index_right'].notna()]

# Finding orders outside polygons
intersects = gpd.sjoin(gdf_orders, gdf_polygons, how='left', predicate='intersects')
outer_orders = intersects[intersects['index_right'].isna()]


# Orders inside polygons (within + on border)
inner_orders = pd.concat([within_points,uniq_border_points], ignore_index=True)


# Converting started_at to date only
inner_orders['datetime'] = pd.to_datetime(inner_orders['started_at'])
inner_orders['date_only'] = inner_orders['datetime'].dt.date


# Streamlit app
st.title('Ontario Orders')

# Date filter
date_option = st.selectbox(
    'Filter data by date:',
    options=['All Time'] + sorted(inner_orders['date_only'].unique().tolist()) + ['2024-07-30']
)

if date_option == 'All Time':
    filtered_df = inner_orders
else:
    selected_date = pd.to_datetime(date_option)
    selected_date = selected_date.date()
    filtered_df = inner_orders[inner_orders['date_only'] == selected_date]

if filtered_df.empty:
    st.write(f"No data available for {selected_date}.")
else:        
    # group by CFSAUID
    order_count = filtered_df.groupby('CFSAUID').size().reset_index(name='order_count')
    
    # merge with orginal polygons based on CFSAUID
    polygons_count = gdf_polygons.merge(order_count, how='left', on='CFSAUID')
    
    # NA will show up black polygons
    polygons_count['order_count'] = polygons_count['order_count'].fillna(0)
    
    
    # Create a base map centered on Ontario
    m = folium.Map(location=[43.7, -79.42], zoom_start=9.7)
    
    
    # Plotting heatmap for orders within polygons
    folium.Choropleth(
        geo_data=polygons_count,
        data=polygons_count,
        columns=['CFSAUID', 'order_count'],
        key_on='feature.properties.CFSAUID',
        fill_color='YlOrRd',
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name='Order Count'
    ).add_to(m)
    
    # Save the map to an HTML file
    m.save('map.html')
    
    # Display the map in Streamlit
    with open('map.html', 'r') as f:
        map_html = f.read()
    components.html(map_html, height=600)
