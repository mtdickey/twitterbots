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
from bs4 import BeautifulSoup
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns; sns.set(color_codes=True)


## Twitter API keys and access info
import config

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
    plot_title = f'{series_title} in {location}\nAs of {update_dt_title}'
    plt.title(plot_title)
    filename = f'plots/{location}_{series_name}_{update_dt}.png'
    plt.savefig(filename)
    
    return filename


def main():
    
    plots = []
    for series in dfs:
        for loc in STATES:
            ts_df = tidy_timeseries(dfs[series], loc, series)
            if ts_df[series].max() > 0:
                plot_name = plot_timeseries(ts_df, loc, series)
                plots.append(plot_name)
                
                ## Compose status with current number
                current_number = ts_df[ts_df['Date'] == ts_df['Date'].max()][series][0]
                current_date = ts_df['Date'].max().strftime("%b. %d, %Y")
                if series == 'Confirmed':
                    status = f'There have been {current_number} confirmed cases of COVID-19 in {loc}, as of {current_date}.'
                elif series == 'Deaths':
                    status = f'There have been {current_number} deaths from COVID-19 in {loc}, as of {current_date}.'
                elif series == 'Recovered':
                    status = f'The have been {current_number} recoveries from COVID-19 in {loc}, as of {current_date}.'
                
                api.update_with_media(plot_name, status=status)
    
if __name__ == "__main__":
    main()
