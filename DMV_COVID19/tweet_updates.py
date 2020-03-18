# -*- coding: utf-8 -*-
"""

Twitterbot for @DMV_COVID19.  Tweets daily updates on trends in DC, Maryland, and Virginia COVID-19 data.

@author: Michael Dickey

"""

import sys
import requests
import numpy as np
import pandas as pd
from twython import Twython
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns; sns.set(color_codes=True)


## Twitter API keys and access info
import tweet_config as config

### Read in current data
confirmed_df = pd.read_csv("https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Confirmed.csv")
deaths_df    = pd.read_csv("https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Deaths.csv")
recovered_df = pd.read_csv("https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Recovered.csv")
dfs = {'Confirmed': confirmed_df, 
       'Deaths': deaths_df,
       'Recovered': recovered_df}

### Connect to Twitter API
api = Twython(config.api_key, config.api_secret,
              config.access_token,
              config.access_token_secret)


### States of interest
STATES = ['District of Columbia', 'Maryland', 'Virginia']


def tidy_timeseries(data, location, series_name):
    """
    Function to JHU time series data and put it into a tidy format.
    
    :param data (DataFrame): DataFrame from JHU timeseries CSV
    :param location (str): Province/State of interest
    :param series_name (str): Name of time series (confirmed/deaths/recovered)
    :return: DataFrame in tidy format
    """
    tidy_df = (data[data['Province/State'] == location]
                  .melt(id_vars = ['Province/State', 'Country/Region',
                                   'Lat', 'Long'], var_name = 'Date',
                        value_name = series_name)
                  .rename(columns = {'Date':'date_str'}))
    
    
    ## Only include after March 1, 2020 for these states
    tidy_df['Date'] = tidy_df['date_str'].apply(lambda x: datetime.strptime(x, "%m/%d/%y"))
    tidy_df = tidy_df[tidy_df['Date'] > datetime(2020, 2, 29)]
    
    return tidy_df


def plot_timeseries(data, location, series_name):
    """
    Function to JHU time series data and put it into a tidy format.
    
    :param data (DataFrame): DataFrame in tidy format from tidy_timeseries()
    :param location (str): Province/State of interest
    :param series_name (str): Name of time series (confirmed/deaths/recovered)
    :return: filepath with location of plot to tweet (str)
    """
    
    ## Initialize lineplot
    plt.figure(figsize=(10,5))
    chart = plt.figure(figsize=(10,5))
    
    ## Plot the data and rotate date axis labels
    chart = sns.lineplot(x="Date", y=series_name, data=data)
    plt.xticks(rotation=30)
    
    ## Most recent date
    update_dt = data['Date'].max().strftime("%Y-%m-%d")
    update_dt_title = data['Date'].max().strftime("%b. %d, %Y")
    
    ## Set the title depending on location, series name, and recent date
    if series_name == 'Confirmed':
        series_title = 'Number of Confirmed COVID-19 Cases'
    elif series_name == 'Deaths':
        series_title = 'Number of COVID-19 Deaths'
    elif series_name == 'Recovered':
        series_title = 'Number of COVID-19 Recoveries'
    
    ## Save the plot
    plot_title = f'{series_title} in {location}\nAs of {update_dt_title}'
    plt.title(plot_title)
    filename = f'plots/{location}_{series_name}_{update_dt}.png'
    plt.savefig(filename)
    
    return filename


def main():
    
    ## Iterate through the time series, states...
    statuses = []
    plot_names = []
    for series in dfs:
        for loc in STATES:
            ## Tidy the data
            ts_df = tidy_timeseries(dfs[series], loc, series)
            
            ## If there's at least 1 case of something and there's a new date in the data,
            #   make a status and a plot
            if ts_df[series].max() > 0:
                
                ## Create the plot
                plot_name = plot_timeseries(ts_df, loc, series)
                plot_names.append(plot_name)
                                
                ## Format DC differently to make it sound better in the status
                if loc == 'District of Columbia':
                    loc = 'D.C.'
                
                ## Compose status with current number
                current_number = ts_df[series][ts_df['Date'].idxmax()]
                current_date = ts_df['Date'].max().strftime("%b. %d, %Y")
                if series == 'Confirmed':
                    status = f'There have been {current_number} confirmed cases of COVID-19 in {loc}, as of {current_date}.'
                elif series == 'Deaths':
                    status = f'There have been {current_number} deaths from COVID-19 in {loc}, as of {current_date}.'
                elif series == 'Recovered':
                    status = f'The have been {current_number} recoveries from COVID-19 in {loc}, as of {current_date}.'
                statues.append(status)
                
                ## Tweet the trend plot if there's more than 10 cases, otherwise, just the status
                if current_number > 10:
                    image_open = open(plot_name, 'rb')
                    response = api.upload_media(media = image_open)
                    api.update_status_with_media(status=status, media_ids = [response['media_id']])
                else:
                    api.update_status(status=status)
                    
    ## Logging tweets sent
    tweets_sent = pd.DataFrame({'status': statuses, 'plot_filepath': plot_names})
    tweets_sent.to_csv(f"log/tweet_log_{datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}.csv",
                       index = False)
    
if __name__ == "__main__":
    main()
