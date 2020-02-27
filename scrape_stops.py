from splinter import Browser
from bs4 import BeautifulSoup
import os
import json
import platform

def init_browser():
    if platform.system().lower() == 'windows'.lower():
        executable_path = {
            'executable_path': 
            os.path.join(os.getcwd(), 'chromedriver.exe')}
        return Browser('chrome', **executable_path, headless=True)
    else:
        return Browser('chrome', headless=True)

br = init_browser()

def get_html(browser, url):
    browser.visit(url)
    html = browser.html
    return html

def get_listings(html):
    soup = BeautifulSoup(html, "html.parser")
    stops = soup.find_all('tr', attrs={'height': 25})
    collection = []
    for stop in stops:
        try:
            collection.append(stop.find('span', class_='emphasized').text)
        except Exception as e:
            print(e)
    collection = [name.replace('\n', '').replace(' /', '').replace('   ', '') for name in collection]
    collection = [name.replace('\t', '').replace('Street', 'St').replace('Avenue', 'Av').replace('Road', 'Rd').replace('Square', 'Sq') for name in collection]
    for i, name in enumerate(collection):
        if name[0] == ' ':
            collection[i] = name[1:]
        elif name[-1] == ' ':
            collection[i] = name[:-1]
    collection = [name.replace('-', ' - ') for name in collection]
    return collection

codes = {'A': 'aline', 'C': 'cline', 'E': 'eline',
         'B': 'bline', 'D': 'dline', 'F': 'fline', 
         'M': 'mline', 'L': 'lline', 'J': 'jline',
         'Z': 'zline', 'N': 'nline', 'Q': 'qline',
         'R': 'rline', '1': 'oneline', '2': 'twoline',
         '3': 'threelin', '4': 'fourline', '5': 'fiveline',
         '6': 'sixline', '7': 'sevenlin'}

stopcache = {}
for code in list(codes.items()):
    stop_list = get_listings(get_html(br, f'http://web.mta.info/nyct/service/{code[1]}.htm'))
    stopcache[code[0]] = stop_list

with open('stops.json', 'w') as fp:
    json.dump(stopcache, fp)