from json import load
from time import sleep
from atproto import Client
import requests


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
            aqi, pm25, pm25_fc, o3, o3_fc = self._getDesiredData(data= station_data)
            
            color = self._getColor(aqi)
            name = self._formatName(name= station_name)

            pm25_trend = self._getForecastDif(pm25, pm25_fc)
            o3_trend = self._getForecastDif(o3, o3_fc)

            pm25 = self._fixNumLen(pm25)
            o3 = self._fixNumLen(o3)

            line1 = f"{color} {name} aqi {aqi}{color}"
            line2 = f"pm25 {pm25}{pm25_trend}  o3 {o3}{o3_trend}"

            station_report = f"{line1}\n{line2}"

            if self.full_report == "":
                self.full_report = station_report
            
            else:
                self.full_report = f"{self.full_report}\n\n{station_report}"
        
    def _getDesiredData(self, data: dict) -> tuple:
        aqi =  int(data["data"]["aqi"])

        pm25 = int(data["data"]["iaqi"]["pm25"]["v"])
        pm25_fc = int(data["data"]["forecast"]["daily"]["pm25"][3]["avg"])

        o3 =   int(data["data"]["iaqi"]["o3"]["v"])
        o3_fc = int(data["data"]["forecast"]["daily"]["o3"][3]["avg"])

        return (aqi, pm25, pm25_fc, o3, o3_fc)

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

    def _getForecastDif(self, current: int, forecast: int) -> str:
        change = forecast - current

        if change > 0:
            return f"⬆️"

        elif change < 0:
            return f"⬇️"

        else:
            return "None"

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

def main(isLive: bool) -> None:
    username, password, api_token = getCredentials()

    station_data: dict[str, dict] = getStationData(api_token)
    dp = DataProcessor(station_data)
    post = dp.full_report

    if isLive:
        client = initClient(username, password)

        # Create and send a new post
        post = client.send_post(post)
    
    
    print(f"Char Count:{len(post)}")
    print("========================")
    print(post)
        


main(isLive= False)



