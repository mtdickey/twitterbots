# -*- coding: utf-8 -*-
"""

Twitterbot for @DMV_COVID19.  Tweets daily updates on trends in DC, Maryland, and Virginia COVID-19 data.

@author: Michael Dickey

"""

## Essential packages
import io
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
dfs = {'Confirmed': {'df': confirmed_df,
                     'series_title': 'Number of Confirmed COVID-19 Cases',
                     'status': 'confirmed cases'}, 
       'Deaths': {'df': deaths_df,
                  'series_title': 'Number of COVID-19 Deaths',
                  'status': 'deaths'}
       }

### Connect to Twitter API
api = Twython(config.api_key, config.api_secret,
              config.access_token,
              config.access_token_secret)


### States of interest
STATES = {#'DC': 'D.C',
          #'MD': 'Maryland',
          #'VA': 'Virginia',
          'All': 'the DMV'}


def tidy_timeseries(data, location, series_name):
    """
    Function to take USA Facts time series data and put it into a tidy format
     for a given state.
    
    :param data (DataFrame): DataFrame from USAfacts timeseries CSV
    :param location (str): State of interest
    :param series_name (str): Name of time series (confirmed/deaths/recovered)
    :return: DataFrame in tidy format
    """
    
    ## Remove some extra columns
    data = data.drop(columns = [c for c in data.columns if 'Unnamed' in c])
    
    ## Subset to state and pivot/melt dates to an individual column
    if location != 'All':
        tidy_df = (data[data['State'] == location]
                      .drop(columns = ['countyFIPS', 'County Name'])
                      .groupby('State').sum().reset_index()
                      .melt(id_vars = ['State', 'stateFIPS'],
                            var_name = 'date_str',
                            value_name = series_name))
    else:
        tidy_df = (data[data['State'].isin(['DC', 'MD', 'VA'])]
                      .drop(columns = ['countyFIPS', 'County Name'])
                      .groupby('State').sum().reset_index()
                      .melt(id_vars = ['State', 'stateFIPS'],
                            var_name = 'date_str',
                            value_name = series_name))
    tidy_df[series_name] = tidy_df[series_name].astype(int)
    
    ## Only include after March 1, 2020 for these states
    tidy_df['Date'] = tidy_df['date_str'].apply(lambda x: datetime.strptime(x, "%m/%d/%y"))
    tidy_df = tidy_df[tidy_df['Date'] > datetime(2020, 3, 9)]
    
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
    if location != 'All':
        chart = sns.lineplot(x="Date", y=series_name, data=data)
    else:
        chart = sns.lineplot(x="Date", y=series_name, data=data, hue = 'State')
    plt.xticks(rotation=30)
    
    ## Most recent date
    update_dt = data['Date'].max().strftime("%Y-%m-%d")
    update_dt_title = data['Date'].max().strftime("%b. %d, %Y")
    
    ## Set the title depending on location, series name, and recent date
    series_title = dfs[series_name]['series_title']    
    loc_name = STATES[location]
    
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
            ts_df = tidy_timeseries(dfs[series]['df'], loc, series)
            
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
                                
                ## Get the location name and add to the list for the log DF
                locations.append(loc)
                loc_name = STATES[loc]
                
                ## Compose status with current number and date
                if loc == 'All': 
                    ## Sum across all states for all
                    current_date_df = ts_df[ts_df['Date'] == ts_df['Date'].max()].sort_values(series, ascending = False).copy()
                    current_number = np.sum(current_date_df[series])
                    top_phrasing = ''
                    for i, row in current_date_df.iterrows():
                        top_phrasing = f"{top_phrasing}{row['State']}: {np.round(row[series], 1):,}\n"
                else:
                    current_number = int(ts_df[series][ts_df['Date'].idxmax()])
                    top_phrasing = ''
                    
                current_date = ts_df['Date'].max().strftime("%b. %d, %Y")
                current_datetime = ts_df['Date'].max()
                                
                status = f"There have been {current_number:,} {dfs[series]['status']} of COVID-19 in {loc_name}, as of {current_date}.\n\n{top_phrasing}\nSource: @usafacts #MadewithUSAFacts."
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
