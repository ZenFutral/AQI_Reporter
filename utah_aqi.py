from json import load
from time import sleep
from datetime import datetime
from atproto import Client
from atproto import client_utils
import requests, pickle, feedparser

def getCredentials() -> tuple[str, str, str]:
    with open('credentials.json', 'r') as f:
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
    aqi_severity: dict[range, str] = {
        range(0,    50): "🟢",
        range(51,  100): "🟡",
        range(101, 150): "🟠",
        range(151, 200): "🔴",
        range(201, 300): "🟣",
        range(301, 999): "🟤"}

    def __init__(self, station_data: dict[str, dict]):
        self.full_report = ''

        for _, (station_name, station_data) in enumerate(station_data.items()):
            min_aqi, dominent_pollution, max_aqi, avg_aqi, favg_aqi, fmax_aqi = self._getDesiredData(data= station_data)
            
            min_color = self._getColor(min_aqi)
            max_color = self._getColor(max_aqi)
            name = self._formatName(name= station_name)

            trend = self._getAQITrend(avg_aqi, favg_aqi)

            aqi_range = f"{min_aqi}-{max_aqi}"
            spacer_len = 5 - len(aqi_range)
            text_spacer = ''

            for _ in range(spacer_len):
                text_spacer = f"{text_spacer} "
            
            line1 = f"{name}{min_color} {aqi_range}{text_spacer}{max_color} 24hr{trend}"

            station_report = f"{line1}"

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
        
        return max(results)
   
    def _getDesiredData(self, data: dict) -> tuple:
        # Current aqi
        dominent_pollution =  data["data"]["dominentpol"]

        max_aqi = self._pullForcast(data, 2, 'max')
        min_aqi = self._pullForcast(data, 2, 'min')
        avg_aqi = self._pullForcast(data, 2, 'avg')
       
        fmax_aqi = self._pullForcast(data, 3, 'max')
        favg_aqi = self._pullForcast(data, 3, 'avg')
       
        return (min_aqi, dominent_pollution, max_aqi, avg_aqi, favg_aqi, fmax_aqi)

    def _getColor(self, aqi: int) -> str:
        for _, (key, value) in enumerate(DataProcessor.aqi_severity.items()):
            if aqi in key:
                return value
        
        # THIS SHOULD NEVER HAPPEN
        return ""

    def _formatName(self, name: str) -> str:
        if name == "salt-lake-city":
            return "SLC  "
        
        elif name == "utah/lindon":
            return "Utah "
        
        elif name == "washington":
            return "Wash."
        
        return name.capitalize()

    def _getAQITrend(self, current: int, forecast: int) -> str:
        change = forecast - current

        if change > 0:
            return "⬆️"

        elif change < 0:
            return "⬇️"

        else:
            return "🟦"

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

    def __init__(self, title_length):
        self.history_limit = 10
        self.url = None
        self.title_length = title_length

        self._loadLinkHist()
        article_list = self._getWHO()
        self._checkURLs(article_list)

        if self.url == None:
            article_list = self._getScienceDaily()
            self._checkURLs(article_list)

        if self.url != None:
            self.link_history.append(self.url)
            self._saveLinkHist()
        
        else:
            self.url = ""

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
        response = [(i.title, i.id) for i in response.entries]
        response.reverse()
        return [i for i in response if len(i[0]) < self.title_length]

    def _checkURLs(self, article_list):
        for article in article_list:
            if article not in self.link_history:
                self.title = article[0]
                self.url = article[1]

    def _loadLinkHist(self):
        try: 
            with open('link_hist.pkl', 'rb') as f:
                self.link_history = pickle.load(f)
        
        except EOFError:
            self.link_history = []

    def _saveLinkHist(self):
        if len(self.link_history) > self.history_limit:
            self.link_history = self.link_history[1:]

        with open('link_hist.pkl', 'wb') as f:
            pickle.dump(self.link_history, f)

def main(isLive: bool = False) -> None:
    username, password, api_token = getCredentials()

    station_data: dict[str, dict] = getStationData(api_token)
    dp = DataProcessor(station_data)
    report = dp.full_report

    chars_remaining = 300 - len(report)

    nf = NewsFinder(chars_remaining)

    tb = client_utils.TextBuilder()
    tb.text(f"{report}\n\n")
    tb.link(nf.title, nf.url)
    post = tb.build_text()
    facets = tb.build_facets()

    if isLive:
        client = initClient(username, password)

        # Create and send a new post
        record_response = client.send_post(text= post, facets= facets)
    
    print(f"Char Count:{len(post)}")
    print("========================")
    print(post)
    print("========================")
    print(record_response)

        
main(isLive= True)
