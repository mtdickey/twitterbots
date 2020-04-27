# -*- coding: utf-8 -*-
"""

Script to tweet maps for the @DMV_COVID19 Twitterbot.

@author: Michael Dickey

"""

## Essential packages
import io
import requests
import numpy as np
import pandas as pd
import geopandas as gpd
from twython import Twython
from datetime import datetime
import matplotlib.pyplot as plt

## Twitter API keys and access info
import tweet_config as config

### Connect to Twitter API
api = Twython(config.api_key, config.api_secret,
              config.access_token,
              config.access_token_secret)

def setup_data():
    """
    Function to set up 2 GeoDataFrames with the number of confirmed cases and deaths by county.
    
    :return: dict; A dictionary with 2 keys, "Confirmed" and "Deaths", each containing a GeoDataFrame as a value 
    """

    ### Read in current data from usafacts.org
    confirmed_response = requests.get("https://usafactsstatic.blob.core.windows.net/public/data/covid-19/covid_confirmed_usafacts.csv")
    confirmed_file_object = io.StringIO(confirmed_response.content.decode('utf-8'))
    confirmed_df = pd.read_csv(confirmed_file_object)
    deaths_response = requests.get("https://usafactsstatic.blob.core.windows.net/public/data/covid-19/covid_deaths_usafacts.csv")
    deaths_file_object = io.StringIO(deaths_response.content.decode('utf-8'))
    deaths_df = pd.read_csv(deaths_file_object)
    
    ## Read in crosswalk of Maryland county names since shapefile didn't come with FIPS
    md_crosswalk = pd.read_csv("shapefiles/md_shapefile_usafact_mapping.csv")
    
    ## Read in population from 2019 Census estimates
    pop_response = requests.get("https://usafactsstatic.blob.core.windows.net/public/data/covid-19/covid_county_population_usafacts.csv")
    pop_file_object = io.StringIO(pop_response.content.decode('utf-8'))
    pop_df = pd.read_csv(pop_file_object)
    pop_df = pop_df.drop(['County Name', 'State'], axis = 1)
    
    # Read kml/shape files
    dc_gdf = gpd.read_file('shapefiles/Washington_DC_Boundary.shp')
    md_gdf = gpd.read_file('shapefiles/MarylandCounty.shp')
    md_gdf = md_gdf.to_crs(epsg=4326)
    va_gdf = gpd.read_file('shapefiles/VirginiaCounty.shp')
    va_gdf = va_gdf.to_crs(epsg=4326)

    ## Clean it up and add them together
    dc_gdf['countyFIPS'] = 11001
    dc_gdf = dc_gdf[['countyFIPS', 'geometry']].copy()
    md_gdf = (md_gdf.merge(md_crosswalk, left_on = 'CountyName',
                          right_on = 'county_name_shapefile')
               .rename({'CountyName': 'Name'}, axis = 1))
    md_gdf = md_gdf[['countyFIPS', 'geometry']]
    va_gdf = va_gdf.rename({'STCOFIPS': 'countyFIPS',
                            'NAME': 'Name'}, axis = 1)[['countyFIPS', 'geometry']].copy()
    va_gdf['countyFIPS'] = va_gdf['countyFIPS'].astype(int)
    states_gdf = gpd.pd.concat([dc_gdf, md_gdf, va_gdf], sort = False)
    
    ## Merge the population in with the geometry
    states_gdf = states_gdf.merge(pop_df, on = 'countyFIPS')
    
    ## Merge the geometry df with deaths and confirmed_df
    states_confirmed_gdf = states_gdf.merge(confirmed_df, on = 'countyFIPS')
    states_deaths_gdf    = states_gdf.merge(deaths_df,    on = 'countyFIPS')
    
    ## Combine into a dictionary
    gdf_dict = {'Confirmed': states_confirmed_gdf,
                'Deaths': states_deaths_gdf}
    
    return gdf_dict


def tweet_image(gdf, series_name, top_n = 5, pop_adjusted = False):
    """
    Function to tweet an image with choropleth map images for the most recent day of data.
    
    :param gdf (GeoDataFrame): GeoDataFrame with geometry of counties and dates in columns
    :param series_name (str): Either 'Confirmed' or 'Deaths', determines the wording of the tweet
    :param top_n (int): Top counties to list in the tweet
    :return: None; saves image to "plots" and tweets the image
    """
    
    ## Find the last day in the data
    variables = [col for col in gdf.columns] #variables are dates with '/' in column names
    last_day = variables[len(variables)-1]
    if len(last_day) > 8:
        fmt = "%m/%d/%Y"
    else:
        fmt = "%m/%d/%y"
    last_day_dt_str = datetime.strptime(last_day, fmt).strftime("%m/%d/%Y")
    
    ## If it's population adjusted, make a new column and use that as the variable
    if pop_adjusted:
        pop_adj_column = f'{last_day}_pop_adj'
        gdf[pop_adj_column] = gdf[last_day]/(gdf['population']/100000)
        variable = pop_adj_column
        pop_adj_note = 'per 100,000 people'
        pop_adj_filename_note = 'pop_adj'
    else:
        variable = last_day
        pop_adj_note = ''
        pop_adj_filename_note = ''
    
    ## Series phrasing for map title
    if series_name == 'Confirmed':
        map_phrasing = 'Confirmed Cases'
    else:
        map_phrasing = series_name
    
    ## Set the figure up
    vmin, vmax = 0, np.max(gdf[variable]) # set the range for the choropleth values
    fig, ax = plt.subplots(1, figsize=(15, 5))
    # remove the axis
    ax.axis('off')
    # add a title and annotation
    ax.set_title(f'COVID-19 {map_phrasing} {pop_adj_note} in the DMV by County\nAs of {last_day_dt_str}', fontdict={'fontsize': '25', 'fontweight' : '3'})
    ax.annotate('Source: USA Facts - usafacts.org/visualizations/coronavirus-covid-19-spread-map',
                 xy=(0.3, .05), xycoords='figure fraction', fontsize=12, color='#555555')
    # Create colorbar legend
    sm = plt.cm.ScalarMappable(cmap='Blues', norm=plt.Normalize(vmin=vmin, vmax=vmax))
    # empty array for the data range
    sm.set_array([]) # Not sure why this step is necessary, but many recommend it
    # add the colorbar to the figure
    fig.colorbar(sm)
    # create map
    gdf.plot(column=variable, cmap='Blues', vmin = vmin, vmax = vmax,
             linewidth=0.8, ax=ax,
             edgecolor='black')
    img_path = f"plots/dmv_{series_name}_{pop_adj_filename_note}_{last_day.replace(r'/', r'-')}_map.png"
    fig.savefig(img_path, dpi=300)
    
    ## Top X counties phrasing for status
    top_n_gdf = gdf.nlargest(top_n, variable)
    top_phrasing = ''
    for i, row in top_n_gdf.iterrows():
        if pop_adjusted:
            ## round to 1 decimal for 
            top_phrasing = f"{top_phrasing}{row['County Name']}, {row['State']}: {np.round(row[variable], 1):,}\n"
        else:
            ## Integers used for non-adjusted
            top_phrasing = f"{top_phrasing}{row['County Name']}, {row['State']}: {int(row[variable]):,}\n"
    
    ## Series phrasing
    if series_name == 'Confirmed':
        phrasing = 'confirmed COVID-19 cases'
    elif series_name == 'Deaths':
        phrasing = 'COVID-19 deaths'

    
    ## Tweet the image
    status = f'Number of {phrasing} {pop_adj_note} in the DMV by county, as of {last_day_dt_str}.\n\nTop {top_n}:\n{top_phrasing}'
    source_note = '\n\nSource: @usafacts #MadewithUSAFacts.'
    if (len(status) + len(source_note)) > 280:
        pass
    else:
        status = status + source_note
    image_open = open(img_path, 'rb')
    response = api.upload_media(media = image_open)
    api.update_status(status=status, media_ids = [response['media_id']])

    
    
def main():
    """
    Put all of the functions above together and run them for each dataset.
    """
    
    gdf_dict = setup_data()
            
    for series in gdf_dict:
        tweet_image(gdf_dict[series], series)
        tweet_image(gdf_dict[series], series, pop_adjusted = True)

if __name__ == "__main__":
    main()
