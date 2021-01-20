# -*- coding: utf-8 -*-
"""

Twitterbot for @DMV_COVID19.  

Tweets daily updates on trends in DC, Maryland, and Virginia COVID-19 data.

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
confirmed_response = requests.get("https://static.usafacts.org/public/data/covid-19/covid_confirmed_usafacts.csv")
confirmed_file_object = io.StringIO(confirmed_response.content.decode('utf-8'))
confirmed_df = pd.read_csv(confirmed_file_object)
deaths_response = requests.get("https://usafactsstatic.blob.core.windows.net/public/data/covid-19/covid_deaths_usafacts.csv")
deaths_file_object = io.StringIO(deaths_response.content.decode('utf-8'))
deaths_df = pd.read_csv(deaths_file_object)
DF_DICT = {'Confirmed': {'df': confirmed_df,
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

### Read in log data
TWEET_HISTORY_DF = pd.read_csv("log/DMV_COVID19_full_tweet_log.csv")
TWEET_HISTORY_DF['data_date'] = (TWEET_HISTORY_DF['data_date'].apply(lambda x: 
                                  datetime.strptime(x,"%Y-%m-%d")))

### Connect to Twitter API
api = Twython(config.api_key, config.api_secret,
              config.access_token,
              config.access_token_secret)


### States of interest
STATES = {'DC': 'D.C',
          'MD': 'Maryland',
          'VA': 'Virginia',
          'All': 'the DMV'}


def tidy_timeseries(data, state, series_type, county = None):
    """
    Function to take USA Facts time series data and put it into a tidy format
     for a given state. Used upon instantiating the RonaTweeter class.
    
    :param data (DataFrame): DataFrame in raw format
    :param state (str): Abbreviation for state of interest
    :param series_type (str): Type of series of interest (confirmed/deaths)
    :param county (str): Name of county of interest
    
    :return: DataFrame in tidy format
    """
    
    ## Remove some extra columns
    data = data.drop(columns = [c for c in data.columns if 'Unnamed' in c])
    
    ## Subset to state/county and pivot/melt dates to an individual column
    if state != 'All' and county is None:
        ## If there's an individual state without a county
        tidy_df = (data[data['State'] == state]
                      .drop(columns = ['countyFIPS', 'County Name'])
                      .groupby('State').sum().reset_index()
                      .melt(id_vars = ['State', 'stateFIPS'],
                            var_name = 'date_str',
                            value_name = series_type))
    
    elif county is not None:
        ## For an individual county (ad-hoc functionality)
        tidy_df = (data[((data['State'] == state) & (data['County Name'] == county))]
                      .groupby(['State', 'stateFIPS', 'County Name', 'countyFIPS'])
                      .sum().reset_index()
                      .melt(id_vars = ['State', 'stateFIPS', 'County Name', 'countyFIPS'],
                            var_name = 'date_str',
                            value_name = series_type))
    
    else:
        ## For "All" states
        tidy_df = (data[data['State'].isin(['DC', 'MD', 'VA'])]
                      .drop(columns = ['countyFIPS', 'County Name'])
                      .groupby('State').sum().reset_index()
                      .melt(id_vars = ['State', 'stateFIPS'],
                            var_name = 'date_str',
                            value_name = series_type))
    
    ## Cast to integer
    tidy_df[series_type] = tidy_df[series_type].astype(int)
    
    ## Determine date format and filter data from 3/9 and earlier
    if len(tidy_df['date_str'][0]) > 8:
        fmt = "%m/%d/%Y"
    else:
        fmt = "%m/%d/%y"
    tidy_df['Date'] = tidy_df['date_str'].apply(lambda x: datetime.strptime(x, fmt))
    tidy_df = tidy_df[tidy_df['Date'] > datetime(2020, 3, 9)]
    
    ## Find the increase since the day before (lagged difference)
    tidy_df['lag1'] = tidy_df[series_type].shift()
    tidy_df['new'] = tidy_df[series_type] - tidy_df['lag1']
    
    return tidy_df


class RonaTweeter():
    """
    The RonaTweeter class contains methods for wrangling COVID-19 data and composing 
     different types of tweets.
    """
    
    def __init__(self, state, series_type, county = None):
        """
        Instantiate the class with the following parameters.
        
        :param state (str): Abbreviation for the state of interest
        :param series_type (str): Name of time series (confirmed/deaths)
        :param county (str): Name of the county of interest
        """
        self.state = state
        self.series_type = series_type
        self.county = county
        self.tidy_data = tidy_timeseries(DF_DICT[series_type]['df'],
                                         state, series_type, county)
        self.ts_plot_location = None
        self.new_case_plot_location = None
        self.log_df = None
    
    def plot_timeseries(self):
        """
        Function to plot tidied USA facts time series data.
        
        :param data (DataFrame): DataFrame in tidy format from tidy_timeseries()
        :param location (str): State of interest
        :param series_name (str): Name of time series (confirmed/deaths/recovered)
        :return: str with filepath/location of plot to tweet
        """
        
        ## Initialize lineplot
        plt.figure(figsize=(14,7))
        chart = plt.figure(figsize=(14,7))
                
        ## Plot the data and rotate date axis labels
        if self.state != 'All':
            chart = sns.lineplot(x="Date", y=self.series_type, data=self.tidy_data)
        else:
            chart = sns.lineplot(x="Date", y=self.series_type, data=self.tidy_data, hue = 'State')
        plt.xticks(rotation=30)
        
        ## Most recent date
        update_dt = self.tidy_data['Date'].max().strftime("%Y-%m-%d")
        update_dt_title = self.tidy_data['Date'].max().strftime("%b. %d, %Y")
        
        ## Set the title depending on location, series name, and recent date
        series_title = DF_DICT[self.series_type]['series_title']    
        if self.county is None:
            loc_name = STATES[self.state]
        else:
            loc_name = f"{self.county}, {self.state}"
        
        ## Save the plot
        plot_title = f'{series_title} in {loc_name}\nAs of {update_dt_title}'
        plt.title(plot_title)
        filename = f'plots/{loc_name.replace(", ", "")}_{self.series_type}_{update_dt}.png'
        plt.savefig(filename)
        
        ## Make the status
        ## Compose status with current number and date
        ## Sum across all states and list each state's value in order
        current_date_df = self.tidy_data[self.tidy_data['Date'] == self.tidy_data['Date'].max()].sort_values(self.series_type, ascending = False).copy()
        current_number = np.sum(current_date_df[self.series_type])
        top_phrasing = ''
        for i, row in current_date_df.iterrows():
            top_phrasing = f"{top_phrasing}{row['State']}: {np.round(row[self.series_type], 1):,}\n"
                    
        ## Paste it together in a sentence
        status = f"There have been {current_number:,} {DF_DICT[self.series_type]['status']} COVID-19 in {loc_name}, as of {update_dt_title}.\n\n{top_phrasing}\nSource: @usafacts #MadewithUSAFacts."
        
        ## Log it
        self.new_tweet_log(ts_status = status, ts_plot_name = filename, current_date = self.tidy_data['Date'].max(),
                      location = self.state, new_case_plot_name = None, new_case_status = None)

        
        self.ts_plot_location = filename
        return filename, status
    
    
    def new_case_curve(self):
        """
        Function to plot the curve of new cases over time for a location of interest.
        
        :return: filepath with location of plot to tweet (str)
        """
        
        ## Subset to only positive days (negative new cases/deaths don't make sense)
        data = self.tidy_data[self.tidy_data['new'] >= 0].copy()
        data['label'] = [dt[:-3] if (dt.endswith('10/20') | dt.endswith('/1/20') | dt.endswith('20/20')) else ''
                         for dt in data['date_str'] ]  ## Label only certain days
        
        ## Initialize histogram
        chart = plt.figure(figsize=(14,7))
        
        ## Barplot across dates
        chart = sns.barplot(x = 'Date', y = 'new', 
                            color = DF_DICT[self.series_type]['curve_color'],
                            data = data)
        chart.set_xticklabels(data['label'], rotation=30, fontsize=10)
        chart.set(xlabel = '', ylabel = DF_DICT[self.series_type]['curve_y_axis'])
        
        ## Set the title depending on location, series name, and recent date
        curve_title = DF_DICT[self.series_type]['curve_title']    
        if self.county is None:
            loc_name = STATES[self.state]
        else:
            loc_name = f"{self.county}, {self.state}"
        
        ## Most recent date
        update_dt = data['Date'].max().strftime("%Y-%m-%d")
        update_dt_title = data['Date'].max().strftime("%b. %d, %Y")
        
        ## Save the plot
        plot_title = f'{curve_title} in {loc_name}\nAs of {update_dt_title}'
        plt.title(plot_title)
        filename = f'plots/new_curve_{loc_name.replace(", ", "")}_{self.series_type}_{update_dt}.png'
        plt.savefig(filename)
        
        ## Make the status
        ### Sum across all states and list each state's value in order
        current_number = int(data[data['Date'] == data['Date'].max()].copy()['new'])
        ## Paste it together in a sentence
        status = f"There were {current_number:,} {DF_DICT[self.series_type]['new_case_status']} COVID-19 in {loc_name} on {update_dt_title}.\nSource: @usafacts #MadewithUSAFacts."
        
        ## Log it
        self.new_tweet_log(ts_status = None, ts_plot_name = None, current_date = data['Date'].max(),
                      location = self.state, new_case_plot_name = filename, new_case_status = status)
        
        self.new_case_plot_location = filename
        return filename, status
    
    
    def send_tweet(self, tweet_type):
        """
        Method to send tweets conditional upon no other tweets in the log 
        sent for the given state/series
        
        """
        
        ## Limit the tweet_history to the state and get the most recent date
        tweet_history_state = TWEET_HISTORY_DF[TWEET_HISTORY_DF['location'] == self.state]
        max_dt_state_history = tweet_history_state['data_date'].max()
        
        ## If there's a new date in the data for that state make a status and a plot
        if self.tidy_data['Date'].max() > max_dt_state_history:
                        
            ## Get the plot/status based on the tweet_type
            if tweet_type == 'new_cases':
                plot_filename, status = self.new_case_curve()
            elif tweet_type == 'time_series':
                plot_filename, status = self.plot_timeseries()
            
            ## Tweet the status
            with open(plot_filename, 'rb') as img_open:
                response = api.upload_media(media = img_open)
                api.update_status(status=status, media_ids = [response['media_id']])
    
    
    def new_tweet_log(self, ts_status, ts_plot_name, current_date, location,
                      new_case_plot_name, new_case_status):
        """
        Take in tweet metadata and add it to the log.
        """
        
        ## Logging tweets sent
        tweets_sent = pd.DataFrame({'status': [ts_status],
                                    'plot_filepath': [ts_plot_name],
                                    'data_date': [current_date],
                                    'location': [location],
                                    'new_case_plot_filepath': [new_case_plot_name],
                                    'new_case_status': [new_case_status]})
        
        ## Append if there's an existing DF in the log    
        if self.log_df is not None:
            log_df = self.log_df.append(tweets_sent)
        else:
            log_df = tweets_sent
        
        self.log_df = log_df
        return log_df


def main():
    """
    Run the whole way through and send tweets for all states and series when necessary.
    """
    
    logs = []    
    ## Iterate through the time series and states
    for series in DF_DICT.keys():
        for loc in STATES.keys():
            
            ## Instantiate a class to do the tweetin'
            MyRonaTweeter = RonaTweeter(state = loc, series_type = series)
            
            ## Create the plots, statuses and tweet
            if loc == 'All':
                ### Timeseries lineplot for "All" states
                MyRonaTweeter.send_tweet(tweet_type = 'time_series')
            else:
                # New case curves for individual states
                MyRonaTweeter.send_tweet(tweet_type = 'new_cases')
            
            if MyRonaTweeter.log_df is not None:
                ## If there was a tweet logged, add it to the list
                logs.append(MyRonaTweeter.log_df)
    
    if len(logs) > 0:
        tweets_sent_df = pd.concat(logs)
        tweets_sent_df.to_csv(f"log/tweet_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv",
                              index = False)
        new_log_df = pd.concat([TWEET_HISTORY_DF, tweets_sent_df], sort = False)
        new_log_df.to_csv("log/DMV_COVID19_full_tweet_log.csv",
                          index = False)


if __name__ == "__main__":
    main()
