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
                     'curve_title': 'New reported cases by day',
                     'curve_color': 'salmon',
                     'curve_y_axis': 'Confirmed Cases',
                     'status': 'confirmed cases of',
                     'new_case_status': 'new reported cases of'}, 
       'Deaths': {'df': deaths_df,
                  'series_title': 'Number of COVID-19 Deaths',
                  'curve_title': 'New reported deaths by day',
                  'curve_color': '#737373',
                  'curve_y_axis': 'Deaths',
                  'status': 'deaths from',
                  'new_case_status': 'new reported deaths of'}
       }

### Connect to Twitter API
api = Twython(config.api_key, config.api_secret,
              config.access_token,
              config.access_token_secret)


### States of interest
STATES = {'DC': 'D.C',
          'MD': 'Maryland',
          'VA': 'Virginia',
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
    if len(tidy_df['date_str'][0]) > 8:
        fmt = "%m/%d/%Y"
    else:
        fmt = "%m/%d/%y"
    tidy_df['Date'] = tidy_df['date_str'].apply(lambda x: datetime.strptime(x, fmt))
    tidy_df = tidy_df[tidy_df['Date'] > datetime(2020, 3, 9)]
    
    ## Find the increase since the day before (lagged difference)
    tidy_df['lag1'] = tidy_df[series_name].shift()
    tidy_df['new'] = tidy_df[series_name] - tidy_df['lag1']
    
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


def new_case_curve(data, location, series_name):
    """
    Function to plot the curve of new cases over time for a location of interest.
    
    :param data (DataFrame): DataFrame in tidy format from tidy_timeseries()
    :param location (str): State of interest
    :param series_name (str): Name of time series (confirmed/deaths/recovered)
    :return: filepath with location of plot to tweet (str)
    """
    
    ## Subset to only positive days (negative new cases/deaths don't make sense)
    data = data[data['new'] >= 0].copy()
    data['label'] = [dt[:-3] if (dt.endswith('10/20') | dt.endswith('/1/20') | dt.endswith('20/20')) else ''
                     for dt in data['date_str'] ]  ## Label only certain days
    
    ## Initialize histogram
    chart = plt.figure(figsize=(14,7))
    
    ## Barplot across dates
    chart = sns.barplot(x = 'Date', y = 'new', color = dfs[series_name]['curve_color'], data = data)
    chart.set_xticklabels(data['label'], rotation=30, fontsize=10)
    chart.set(xlabel = '', ylabel = dfs[series_name]['curve_y_axis'])
    
    ## Set the title depending on location, series name, and recent date
    curve_title = dfs[series_name]['curve_title']    
    loc_name = STATES[location]
    
    ## Most recent date
    update_dt = data['Date'].max().strftime("%Y-%m-%d")
    update_dt_title = data['Date'].max().strftime("%b. %d, %Y")
    
    ## Save the plot
    plot_title = f'{curve_title} in {loc_name}\nAs of {update_dt_title}'
    plt.title(plot_title)
    filename = f'plots/new_curve_{location}_{series_name}_{update_dt}.png'
    plt.savefig(filename)

    return filename

def main():
    
    ### Read in master file with all tweets sent previously
    tweet_history = pd.read_csv("log/DMV_COVID19_full_tweet_log.csv")
    tweet_history['data_date'] = tweet_history['data_date'].apply(lambda x: datetime.strptime(x, "%Y-%m-%d"))
    
    ## Iterate through the time series, states...
    ts_statuses = []
    ts_plot_names = []
    new_case_statuses = []
    new_case_plot_names = []
    current_dates = []
    locations = []
    for series in dfs:
        for loc in STATES:
            
            print(f"{series}_{loc}")
            
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
                
                print(f"inside first IF statement")

                ## Get the location name and add to the list for the log DF
                locations.append(loc)
                loc_name = STATES[loc]
                
                ## Current dates
                current_date = ts_df['Date'].max().strftime("%b. %d, %Y")
                current_datetime = ts_df['Date'].max()
                current_dates.append(current_datetime)
                
                ## Create the plots, statuses and tweet
                if loc == 'All': 
                    
                    print("Inside loc if statement")
                    
                    ### Lineplot for "All" states
                    ts_plot_name = plot_timeseries(ts_df, loc, series)
                    ts_plot_names.append(ts_plot_name)
                
                    ## Compose status with current number and date
                    ## Sum across all states and list each state's value in order
                    current_date_df = ts_df[ts_df['Date'] == ts_df['Date'].max()].sort_values(series, ascending = False).copy()
                    current_number = np.sum(current_date_df[series])
                    top_phrasing = ''
                    for i, row in current_date_df.iterrows():
                        top_phrasing = f"{top_phrasing}{row['State']}: {np.round(row[series], 1):,}\n"
                    
                    ## Paste it together in a sentence
                    ts_status = f"There have been {current_number:,} {dfs[series]['status']} COVID-19 in {loc_name}, as of {current_date}.\n\n{top_phrasing}\nSource: @usafacts #MadewithUSAFacts."
                    ts_statuses.append(ts_status)
                    
                    ## Tweet the status
                    with image_open as open(ts_plot_name, 'rb'):
                        response = api.upload_media(media = image_open)
                        api.update_status(status=ts_status, media_ids = [response['media_id']])
                    
                    ### Null values for new case curve
                    new_case_statuses.append(None)
                    new_case_plot_names.append(None)
                    
                else:
                    
                    print("Inside loc if statement")
                    
                    # New case curves for individual states
                    new_curve_plot_name = new_case_curve(ts_df, loc, series)
                    new_case_plot_names.append(new_curve_plot_name)
                    
                    ## Compose status with current number and date
                    ## Sum across all states and list each state's value in order
                    current_date_df = ts_df[ts_df['Date'] == ts_df['Date'].max()].copy()
                    current_number = int(current_date_df['new'])
                    
                    ## Paste it together in a sentence
                    new_case_status = f"There were {current_number:,} {dfs[series]['new_case_status']} COVID-19 in {loc_name} on {current_date}.\nSource: @usafacts #MadewithUSAFacts."
                    new_case_statuses.append(new_case_status)
                    
                    ## Tweet the status
                    with image_open as open(new_curve_plot_name, 'rb'):
                        response = api.upload_media(media = image_open)
                        api.update_status(status=new_case_status, media_ids = [response['media_id']])
                    
                    ### Null values for line plot
                    ts_statuses.append(None)
                    ts_plot_names.append(None)
    
    
    ## Logging tweets sent
    tweets_sent = pd.DataFrame({'status': ts_statuses, 'plot_filepath': ts_plot_names,
                                'data_date': current_dates, 'location': locations,
                                'new_case_plot_filepath': new_case_plot_names,
                                'new_case_status': new_case_statuses})
    
    if len(tweets_sent) > 0:
        tweets_sent.to_csv(f"log/tweet_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv",
                           index = False)
        tweet_history_new = pd.concat([tweet_history, tweets_sent], sort = False)
        tweet_history_new.to_csv("log/DMV_COVID19_full_tweet_log.csv",
                                 index = False)
    
if __name__ == "__main__":
    main()
