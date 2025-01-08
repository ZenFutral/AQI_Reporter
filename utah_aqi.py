from json import load
from time import sleep
from random import choice
from datetime import datetime
from atproto import Client
from atproto import client_utils
import requests, pickle, feedparser
from pathlib import Path

def getCredentials() -> tuple[str, str, str]:
    with open(f'{cur_dir}/credentials.json', 'r') as f:
        data = load(f)
    
    user: str = data['username']
    pwrd: str = data['password']
    key:  str = data['api_token']

    return (user, pwrd, key)

def getStationData(api_token) -> dict[str, dict]:
    stations: list[str] = ["cache", "weber", "davis", "salt-lake-city", "utah/lindon", "washington"]
    station_data: dict[str, dict] = {}
    
    for stat in stations:
        sleep(0.1)
        request_url = f"https://api.waqi.info/feed/utah/{stat}/?token={api_token}"
        response = requests.get(request_url).json()
        station_data[stat] = response
    
    return station_data

class DataProcessor:
    aqi_severity: dict[range, bytes] = {
        range(0,    51): b'\xf0\x9f\x9f\xa2',
        range(51,  101): b'\xf0\x9f\x9f\xa1',
        range(101, 151): b'\xf0\x9f\x9f\xa0',
        range(151, 201): b'\xf0\x9f\x94\xb4',
        range(201, 301): b'\xf0\x9f\x9f\xa3',
        range(301, 999): b'\xf0\x9f\x9f\xa4'}

    def __init__(self, station_data: dict[str, dict]):
        self.full_report = ''

        for _, (station_name, station_data) in enumerate(station_data.items()):
            min_aqi, max_aqi, avg_aqi, favg_aqi = self._getDesiredData(data= station_data)
            
            min_color = self._getColor(min_aqi).decode()
            max_color = self._getColor(max_aqi).decode()
            name = self._formatName(name= station_name)

            trend = self._getAQITrend(avg_aqi, favg_aqi).decode()

            aqi_range = f"{min_aqi}-{max_aqi}"
            spacer_len = 5 - len(aqi_range)
            text_spacer = ''

            for _ in range(spacer_len):
                text_spacer = f"{text_spacer} "
            
            station_report = f"{name}{min_color!r} {aqi_range}{text_spacer}{max_color!r} 24hr{trend!r}"
            station_report = station_report.replace("'","")

            if self.full_report == "":
                self.full_report = station_report
            
            else:
                self.full_report = f"{self.full_report}\n\n{station_report}"
        
    def _pullForcast(self, data: dict, day_idx: int, item: str):
        # From a given day, pulls all 3 reported pollutants
        forcast = data["data"]["forecast"]["daily"]
        stats = ['pm25', 'pm10', 'o3']
        results = []

        for s in stats:
            try:
                results.append(forcast[s][day_idx][item])
            
            except IndexError:
                continue

            except KeyError:
                continue
        
        return max(results)
   
    def _getDesiredData(self, data: dict) -> tuple:
        max_aqi = self._pullForcast(data, 2, 'max')
        min_aqi = self._pullForcast(data, 2, 'min')
        avg_aqi = self._pullForcast(data, 2, 'avg')
       
        favg_aqi = self._pullForcast(data, 3, 'avg')
       
        return (min_aqi, max_aqi, avg_aqi, favg_aqi)

    def _getColor(self, aqi: int) -> bytes:
        for _, (key, value) in enumerate(DataProcessor.aqi_severity.items()):
            if aqi in key:
                return value
        
        # THIS SHOULD NEVER HAPPEN
        return b'0'

    def _formatName(self, name: str) -> str:
        if name == "salt-lake-city":
            return "SLC  "
        
        elif name == "utah/lindon":
            return "Utah "
        
        elif name == "washington":
            return "Wash."
        
        return name.capitalize()

    def _getAQITrend(self, current: int, forecast: int) -> bytes:
        change = forecast - current

        if change > 0:
            return b'\xe2\xac\x86\xef\xb8\x8f'

        elif change < 0:
            return b'\xe2\xac\x87\xef\xb8\x8f'

        else:
            return b'\xf0\x9f\x9f\xa6'

    def _fixNumLen(self, num: int) -> str:
        numstr = str(num)

        if len(numstr) == 1:
            return f" {numstr}"

        else:
            return numstr
            
def initClient(username: str, password: str):
    # Instantiate and login to client object
    client = Client()
    client.login(username, password)

    return client

class NewsFinder:
    # Check newsapi.org: https://newsapi.org/docs

    backup_urls = [
        ('Clean Air Fund', 'https://www.cleanairfund.org/'),
        ('Breathe Utah', 'https://www.breatheutah.org/'),
        ('Lung.org', 'https://www.lung.org/clean-air/stand-up-for-clean-air'),
        ('Your Air Your Utah', 'https://yourairyourutah.org/'),
        ('Climate and Clean Air', 'https://www.ccacoalition.org/')
    ]

    def __init__(self, title_length):
        self.history_limit = 20
        self.external_link_used = False
        self.article = None
        self.title_length = title_length
        self._loadLinkHist()

        while self.article == None:
            article_list = self._getWHO()
            self._checkArticles(article_list)

            article_list = self._getScienceDaily()
            self._checkArticles(article_list)

        if self.external_link_used:
            self.link_history.append(self.article)
            self._saveLinkHist()

        else:
            self.article = self._getBackupLink()

    def _getWHO(self):
        last_year = (datetime.now().year - 1)
        request_url = f"https://www.who.int/api/news/newsitems?$filter=dad28089-7534-4298-838f-4e1fbd046054%20in%20healthtopics%20and%20PublicationDateAndTime%20gt%20{last_year}-01-01T00:00:01Z&$orderby=PublicationDateAndTime%20desc"
        response = requests.get(request_url).json()
        data = [(i['Title'],f"https://www.who.int/news/item{i['ItemDefaultUrl']}") for i in response['value']]
        data.reverse()
        return [i for i in data if len(i[0]) < self.title_length]
        
    def _getScienceDaily(self):
        request_url = f"https://www.sciencedaily.com/rss/earth_climate/air_pollution.xml"
        response = feedparser.parse(request_url)
        data = [(i.title, i.id) for i in response.entries]
        data.reverse()
        return [i for i in data if len(i[0]) < self.title_length]

    def _getBackupLink(self):
        return choice(self.backup_urls)

    def _checkArticles(self, article_list):
        for article in article_list:
            if article not in self.link_history:
                self.external_link_used = True
                self.article = article

    def _loadLinkHist(self):
        try: 
            with open(f'{cur_dir}/link_hist.pkl', 'rb') as f:
                self.link_history = pickle.load(f)
        
        except EOFError:
            self.link_history = []

    def _saveLinkHist(self):
        if len(self.link_history) > self.history_limit:
            self.link_history = self.link_history[1:]

        with open(f'{cur_dir}/link_hist.pkl', 'wb') as f:
            pickle.dump(self.link_history, f)

def main(isLive: bool = False) -> None:
    username, password, api_token = getCredentials()

    station_data: dict[str, dict] = getStationData(api_token)
    dp = DataProcessor(station_data)
    report = dp.full_report

    chars_remaining = 300 - len(report)

    nf = NewsFinder(chars_remaining)
    title, url = nf.article

    tb = client_utils.TextBuilder()
    tb.text(f"{report}\n\n")
    tb.link(title, url)
    post = tb.build_text()
    facets = tb.build_facets()

    if isLive:
        client = initClient(username, password)

        # Create and send a new post
        record_response = client.send_post(text= post, facets= facets)
    
    print(f"Char Count:{len(post)}")
    print("========================")
    print(post)

cur_dir = Path.cwd()

# 'isLive' controls BlueSky posting   
main(isLive= False)
