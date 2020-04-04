# -*- coding: utf-8 -*-
"""

Twitterbot for @DMV_COVID19.  Tweets daily updates on trends in DC, Maryland, and Virginia COVID-19 data.

@author: Michael Dickey

"""

## Essential packages
import io
import sys
import requests
import numpy as np
import pandas as pd
from twython import Twython
from datetime import datetime

## Viz
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns; sns.set(color_codes=True)


## Twitter API keys and access info
import tweet_config as config

### Read in current data from usafacts.org
confirmed_response = requests.get("https://usafactsstatic.blob.core.windows.net/public/data/covid-19/covid_confirmed_usafacts.csv")
confirmed_file_object = io.StringIO(confirmed_response.content.decode('utf-8'))
confirmed_df = pd.read_csv(confirmed_file_object)
deaths_response = requests.get("https://usafactsstatic.blob.core.windows.net/public/data/covid-19/covid_deaths_usafacts.csv")
deaths_file_object = io.StringIO(deaths_response.content.decode('utf-8'))
deaths_df = pd.read_csv(deaths_file_object)
dfs = {'Confirmed': confirmed_df, 
       'Deaths': deaths_df
       #,'Recovered': recovered_df
       }

### Connect to Twitter API
api = Twython(config.api_key, config.api_secret,
              config.access_token,
              config.access_token_secret)


### States of interest
STATES = ['DC', 'MD', 'VA']


def tidy_timeseries(data, location, series_name):
    """
    Function to take USA Facts time series data and put it into a tidy format
     for a given state.
    
    :param data (DataFrame): DataFrame from USAfacts timeseries CSV
    :param location (str): State of interest
    :param series_name (str): Name of time series (confirmed/deaths/recovered)
    :return: DataFrame in tidy format
    """
    data = data.drop(columns = [c for c in data.columns if 'Unnamed' in c])
    tidy_df = (data[data['State'] == location]
                  .drop(columns = ['countyFIPS', 'County Name'])
                  .groupby('State').sum().reset_index()
                  .melt(id_vars = ['State', 'stateFIPS'],
                        var_name = 'date_str',
                        value_name = series_name))
    tidy_df[series_name] = tidy_df[series_name].apply(lambda x: int(x))
    
    ## Only include after March 1, 2020 for these states
    tidy_df['Date'] = tidy_df['date_str'].apply(lambda x: datetime.strptime(x, "%m/%d/%y"))
    tidy_df = tidy_df[tidy_df['Date'] > datetime(2020, 2, 29)]
    
    return tidy_df


def plot_timeseries(data, location, series_name):
    """
    Function to plot tidied USA facts time series data.
    
    :param data (DataFrame): DataFrame in tidy format from tidy_timeseries()
    :param location (str): State of interest
    :param series_name (str): Name of time series (confirmed/deaths/recovered)
    :return: filepath with location of plot to tweet (str)
    """
    
    ## Initialize lineplot
    plt.figure(figsize=(14,7))
    chart = plt.figure(figsize=(14,7))
    
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
    
    if location == 'DC':
        loc_name = 'D.C.'
    elif location == 'MD':
        loc_name = 'Maryland'
    elif location == 'VA':
        loc_name = 'Virginia'
    
    ## Save the plot
    plot_title = f'{series_title} in {loc_name}\nAs of {update_dt_title}'
    plt.title(plot_title)
    filename = f'plots/{location}_{series_name}_{update_dt}.png'
    plt.savefig(filename)
    
    return filename


def main():
    
    ### Read in master file with all tweets sent previously
    tweet_history = pd.read_csv("log/DMV_COVID19_full_tweet_log.csv")
    tweet_history['data_date'] = tweet_history['data_date'].apply(lambda x: datetime.strptime(x, "%Y-%m-%d"))
    
    ## Iterate through the time series, states...
    statuses = []
    plot_names = []
    current_dates = []
    locations = []
    for series in dfs:
        for loc in STATES:
            
            ## Tidy the data
            ts_df = tidy_timeseries(dfs[series], loc, series)
            
            ## Limit the tweet_history to the state and get the most recent date
            tweet_history_state = tweet_history[tweet_history['location'] == loc]
            if len(tweet_history_state) == 0:
                ## low date if there hasn't been a tweet yet
                max_dt_state_history = pd.Timestamp('1900-01-01')
            else:
                max_dt_state_history = tweet_history_state['data_date'].max()
            
            ## If there's at least 1 case of something and there's a new date in the data for that state,
            #   make a status and a plot
            if ((ts_df[series].max() > 0) & 
               (ts_df['Date'].max() > max_dt_state_history) &
               (~np.isnan(np.round(ts_df[series][ts_df['Date'].idxmax()])))):
                
                ## Create the plot
                plot_name = plot_timeseries(ts_df, loc, series)
                plot_names.append(plot_name)
                                
                ## Format DC differently to make it sound better in the status
                locations.append(loc)
                if loc == 'DC':
                    loc_name = 'D.C.'
                elif loc == 'MD':
                    loc_name = 'Maryland'
                elif loc == 'VA':
                    loc_name = 'Virginia'
                
                ## Compose status with current number
                current_number = int(ts_df[series][ts_df['Date'].idxmax()])
                current_date = ts_df['Date'].max().strftime("%b. %d, %Y")
                current_datetime = ts_df['Date'].max()
                if current_number == 1:
                    have_has = 'has'
                    plural = ''
                else:
                    have_has = 'have'
                    plural = 's'
                if series == 'Confirmed':
                    status = f'There {have_has} been {current_number:,} confirmed case{plural} of COVID-19 in {loc_name}, as of {current_date}. Source: @usafacts #MadewithUSAFacts.'
                elif series == 'Deaths':
                    status = f'There {have_has} been {current_number:,} death{plural} from COVID-19 in {loc_name}, as of {current_date}. Source: @usafacts #MadewithUSAFacts.'
                elif series == 'Recovered':
                    if current_number == 1:
                        recover = 'recovery'
                    else:
                        recover = 'recoveries'
                    status = f'The {have_has} been {current_number:,} {recover} from COVID-19 in {loc_name}, as of {current_date}. Source: @usafacts #MadewithUSAFacts.'
                statuses.append(status)
                current_dates.append(current_datetime)
                
                ## Tweet the trend plot if there's more than 10 cases, otherwise, just the status
                if current_number > 10:
                    image_open = open(plot_name, 'rb')
                    response = api.upload_media(media = image_open)
                    api.update_status(status=status, media_ids = [response['media_id']])
                else:
                    api.update_status(status=status)
    
    ## Logging tweets sent
    tweets_sent = pd.DataFrame({'status': statuses, 'plot_filepath': plot_names,
                                'data_date': current_dates, 'location': locations})
    if len(tweets_sent) > 0:
        tweets_sent.to_csv(f"log/tweet_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv",
                           index = False)
        tweet_history_new = pd.concat([tweet_history, tweets_sent], sort = False)
        tweet_history_new.to_csv("log/DMV_COVID19_full_tweet_log.csv",
                                 index = False)
    
if __name__ == "__main__":
    main()
