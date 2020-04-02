SET log_file=%cd%\logfile.txt
call C:\Users\mtdic\Anaconda3\Scripts\activate.bat
cd C:\Users\mtdic\Documents\GitHub\twitterbots\DMV_COVID19
conda activate covid && python tweet_maps.py
pause