import requests
import sys
import os

url = "http://localhost:8000/api/v1/upload"
filename = sys.argv[1]
with open(filename, 'rb') as f:
    files = {'file': (os.path.basename(filename), f.read())}
response = requests.post(url, files=files)
print(response.status_code)
print(response.text)
