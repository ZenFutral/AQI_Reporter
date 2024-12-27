# Import the Client class from the atproto library
from atproto import Client
from json import load

def getCredentials() -> tuple[str, str]:
    with open('credentials.json', 'r') as f:
        data = load(f)
    
    user: str = data['username']
    pwrd: str = data['password']

    return (user, pwrd)

# Instantiate the client object
client = Client()

# Log in using your Bluesky account credentials
username, password = getCredentials()
client.login(username, password)

# Create and send a new post
post = client.send_post('This is an API test. Please follow for future AQI updates!')

