import requests
import os
import re
from urllib.parse import urlencode, unquote_plus, quote_plus
from operator import itemgetter, attrgetter

import StorageServer

import xbmcplugin
import xbmcgui
import xbmcvfs
import xbmcaddon

addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo('id')
addon_version = addon.getAddonInfo('version')
addon_path = addon.getAddonInfo('path')
addon_profile = addon.getAddonInfo('profile')
addon_fanart = addon.getAddonInfo('fanart')
addon_icon = addon.getAddonInfo('icon')
profile = addon.getAddonInfo('profile')
cache = StorageServer.StorageServer(addon_id, 1)
base_url = 'https://api2.iheart.com/api'
country_api_url = 'https://us.api.iheart.com'
country_code = 'US'
market_id = None

if not xbmcvfs.exists(profile):
    xbmcvfs.mkdirs(profile)
favorites_file = os.path.join(profile, 'favorites')
fav_list = list()
if xbmcvfs.exists(favorites_file):
    with xbmcvfs.File(favorites_file) as f:
        fav_list = eval(f.read())
location_file = os.path.join(profile, 'location')
if xbmcvfs.exists(location_file):
    with xbmcvfs.File(location_file) as f:
        location = eval(f.read())
        country_api_url = location[0]
        country_code = location[1]
        if len(location) == 3:
            market_id = location[2]


def addon_log(string, debug_level=False):
    if debug_level:
        debug_level = xbmc.LOGINFO
    else:
        debug_level = xbmc.LOGDEBUG
    xbmc.log(f'[{addon_id}-{addon_version}]: {string}', level=debug_level)


def make_request(url, is_json=True):
    addon_log(f'Request URL: {url}')
    try:
        res = requests.get(url)
        if not res.status_code == requests.codes.ok:
            addon_log(f'Bad status code: {res.status_code}')
            res.raise_for_status()
        if not res.encoding == 'utf-8':
            res.encoding = 'utf-8'
        if is_json:
            return res.json()
        else:
            return res.text
    except requests.exceptions.HTTPError as error:
        addon_log(f'We failed to open {url}.', True)
        addon_log(f'HTTPError: {error}', True)


def get_stations(data=None):
    if data is None:
        url = f'{country_api_url}/api/v2/content/liveStations?countryCode={country_code}'
        if not market_id:
            url = f'{url}&limit=60'
        else:
            url = f'{url}&limit=1000&marketId={market_id}'
        data = make_request(url)
    station_list = []
    if 'values' in data:
        addon_log(f'VALUE Data: {data}')
        for i in data['values']:
            item = {}
            if 'streams' in i['content']:
                item['label'] = i['label']
                item['sub_label'] = i['subLabel']
                item['id'] = i['content']['id']
                item['genre'] = i['content']['genres'][0]['name']
                item['thumb'] = i['imagePath']
                item['thumb_'] = i['content']['logo']
                item['streams'] = i['content']['streams']
                station_list.append(item)
        return station_list
    elif 'hits' in data:
        addon_log(f'HITS Data: {data}')
        for i in data['hits']:
            item = {}
            if 'streams' in i:
                item['label'] = i['name']
                item['sub_label'] = i['description']
                item['id'] = i['id']
                item['genre'] = i['genres'][0]['name']
                item['thumb'] = i['logo']
                item['streams'] = i['streams']
                station_list.append(item)
            elif 'content' in i and i['stationType'] == 'LIVE':
                item['label'] = i['content'][0]['name']
                item['sub_label'] = i['content'][0]['description']
                item['id'] = i['id']
                item['genre'] = i['content'][0]['genres'][0]['name']
                item['thumb'] = i['content'][0]['logo']
                item['streams'] = i['content'][0]['streams']
                station_list.append(item)
        return station_list


def display_main():
    if not xbmcvfs.exists(location_file):
        set_location()
    add_dir('Menu', 'Menu', 'menu', addon_icon)
    if country_code == 'WW':
        display_podcast_categories()
    else:
        display_stations(get_stations())


def display_stations(station_list):
    for i in station_list:
        addon_log(f'STREAMS {i["streams"]}')
        # pls streams have media info in the correct format
        if 'secure_pls_stream' in i['streams']:
            stream = i['streams']['secure_pls_stream']
        elif 'pls_stream' in i['streams']:
            stream = i['streams']['pls_stream']
        # shoutcast_streams have media info but not the correct format
        elif 'secure_shoutcast_stream' in i['streams']:
            stream = i['streams']['secure_shoutcast_stream']
        elif 'shoutcast_stream' in i['streams']:
            stream = i['streams']['shoutcast_stream']
        else:
            # hls streams don't seem to have media data
            hls_streams = [i['streams'][x] for x in i['streams'] if
                           i['streams'][x].endswith('m3u8')]
            if hls_streams:
                secure_stream = [x for x in hls_streams if x.startswith('https')]
                if secure_stream:
                    stream = secure_stream[0]
                else:
                    stream = hls_streams[-1]
            else:
                secure_streams = [i['streams'][x] for x in i['streams'] if
                                  i['streams'][x].startswith('https')]
                if secure_streams:
                    stream = secure_streams[0]
                else:
                    stream = [i['streams'][x] for x in i['streams']][0]
        title = i['label']
        addon_log(f'Stream URL:{title} {stream}')
        info = {'title': title, 'genre': i['genre']}
        add_dir(title, stream, 'play', i['thumb'], info, i['id'])


def set_location():
    global country_api_url
    global country_code
    global market_id
    market_id = None
    countries = [('United States', 'US'), ('Canada', 'CA'), ('Australia', 'AU'),
                 ('New Zealand', 'NZ'), ('Mexico', 'MX'), ('Other (only podcasts are available)', 'WW')]
    dialog = xbmcgui.Dialog()
    ret = dialog.select('Select your location', [i[0] for i in countries])
    if not ret >= 0:
        return
    country_code = countries[ret][1]
    country_api_url = f'https://{country_code.lower()}.api.iheart.com'
    if country_code != 'WW':
        # returns countries available from current location
        data = make_request(f'{country_api_url}/api/v2/content/countries')
        if 'hits' not in data:
            addon_log('No hits for streamable countries')
            return
        streamable_countries = [(i['name'], i['abbreviation']) for i in data['hits']]
        if not streamable_countries:
            addon_log('No streamable countries in list')
            return
        elif streamable_countries and len(streamable_countries) > 1:
            dialog = xbmcgui.Dialog()
            ret = dialog.select('Countries available from your location', [i[0] for i in streamable_countries])
            if not ret >= 0:
                return
            country_code = streamable_countries[ret][1]
        else:
            country_code = streamable_countries[0][1]
    with xbmcvfs.File(location_file, 'w') as loc:
        loc.write(repr([country_api_url, country_code]))


def set_market():
    global market_id
    url = f'{country_api_url}/api/v2/content/markets?countryCode={country_code}&limit=10000'
    data = make_request(url)
    addon_log(f'MARKET Data: {data}')
    if 'hits' not in data:
        addon_log('No hits for markets')
        return
    market_list = sorted(data['hits'], key=itemgetter('name'))
    dialog = xbmcgui.Dialog()
    ret = dialog.select('Markets', [f"{i['city']}, {i['stateName']}" for i in market_list])
    if not ret >= 0:
        return
    market_id = market_list[ret]['marketId']
    addon_log(f'MARKET ID: {market_id}')
    with xbmcvfs.File(location_file, 'w') as loc:
        loc.write(repr([country_api_url, country_code, market_id]))
    url = f'{country_api_url}/api/v2/content/liveStations?countryCode={country_code}&limit=10000&marketId={market_id}'
    display_stations(get_stations(make_request(url)))


def get_genre(genre_id):
    url = f'{base_url}/v2/content/liveStations?genreId={genre_id}&limit=1000'
    return make_request(url)


def get_genres():
    # cache.cacheFunction
    url = f'{country_api_url}/api/v3/catalog/genres?genreType=liveStation'
    return make_request(url)


def display_genres():
    data = cache.cacheFunction(get_genres)
    dialog = xbmcgui.Dialog()
    ret = dialog.select('Genres', [i['genreName'] for i in data['genres']])
    if ret >= 0:
        display_stations(get_stations(get_genre(data['genres'][ret]['id'])))


def get_podcast_categories():
    # cache.cacheFunction
    return make_request(f'{country_api_url}/api/v3/podcast/categories')


def display_podcast_categories():
    data = cache.cacheFunction(get_podcast_categories)
    for i in data['categories']:
        add_dir(i['name'], i['id'], 'podcast_category', i['image'])


def display_podcast_category(category_id):
    url = f'{country_api_url}/api/v3/podcast/categories/{category_id}'
    data = make_request(url)
    for i in data['podcasts']:
        add_dir(i['title'], i['id'], 'podcast_episodes', i['imageUrl'])


def display_podcast_episodes(show_id):
    url = f'{country_api_url}/api/v3/podcast/podcasts/{show_id}/episodes'
    data = make_request(url)
    for i in data['data']:
        add_dir(i['title'], i['id'], 'podcast', i['imageUrl'], {'duration': i['duration']})


def resolve_podcast_url(show_id):
    url = f'{country_api_url}/api/v3/podcast/episodes/{show_id}'
    data = make_request(url)
    return data['episode']['mediaUrl']


def display_menu():
    menu_items = ['Set Market', 'Genres', 'Podcasts', 'Favorites', 'Search', 'Reset Location']
    if country_code == 'WW':
        menu_items = menu_items[3:]
    dialog = xbmcgui.Dialog()
    ret = dialog.select('Menu', menu_items)
    if ret >= 0:
        if menu_items[ret] == 'Set Market':
            set_market()
        elif menu_items[ret] == 'Genres':
            display_genres()
        elif menu_items[ret] == 'Search':
            search()
        elif menu_items[ret] == 'Favorites':
            get_favorites()
        elif menu_items[ret] == 'Podcasts':
            display_podcast_categories()
        elif menu_items[ret] == 'Reset Location':
            xbmcvfs.delete(location_file)
            xbmc.sleep(2000)
            display_main()


def search():
    keyboard = xbmc.Keyboard('', 'Search for stations and podcasts')
    keyboard.doModal()
    if not keyboard.isConfirmed():
        return
    search_q = keyboard.getText()
    if len(search_q) == 0:
        return
    search_params = {
        "bundle": "true",
        "keyword": "true",
        "keywords": search_q,
        "maxRows": "3",
        "countryCode": country_code,
        "startIndex": "0",
        "albums": "false",
        "artist": "false",
        "playlist": "false",
        "station": "true",
        "podcast": "true",
        "track": "false"
    }
    search_url = f'{country_api_url}/api/v3/search/all?{urlencode(search_params)}'
    data = make_request(search_url)
    addon_log(f'SEARCH Data: {data}')
    if 'stations' in data['results'] and data['results']['stations']:
        for i in data['results']['stations']:
            station_data = make_request(f'{base_url}/v2/content/liveStations/{i["id"]}')
            display_stations(get_stations(station_data))
    if 'podcasts' in data['results'] and data['results']['podcasts']:
        for i in data['results']['podcasts']:
            add_dir(i['title'], i['id'], 'podcast_episodes', i['image'])


def parse_pls(url):
    # kodi will crash on these .pls files, so we parse them for the stream url
    data = make_request(url, False)
    streams = re.findall('=(.+?)\r\n', data)
    if streams:
        return streams[0]


def add_dir(name, url, dir_mode, icon, info=None, station_id=None):
    if info is None:
        info = {}
    url_params = {'name': name, 'url': url, 'mode': dir_mode, 'id': station_id}
    plugin_url = '%s?%s' % (sys.argv[0], urlencode(url_params))
    listitem = xbmcgui.ListItem(name)
    listitem.setArt({'thumb': icon, 'fanart': addon_fanart})
    is_folder = True
    if dir_mode in ['play', 'podcast']:
        is_folder = False
        listitem.setProperty('IsPlayable', 'true')
    fav_mode = 'add_favorite'
    menu_title = 'Add add-on favorite'
    if name in repr(fav_list):
        fav_mode = 'rm_favorite'
        menu_title = 'Remove add-on favorite'
    context_args = f'RunAddon(plugin.audio.iheart, mode={fav_mode}&name={quote_plus(name)}&url={url}&icon={icon})'
    listitem.addContextMenuItems([(menu_title, context_args)])
    listitem.setInfo(type='music', infoLabels=info)
    xbmcplugin.addDirectoryItem(int(sys.argv[1]), plugin_url, listitem, is_folder)


def add_favorite(name, url, icon):
    if name not in repr(fav_list):
        fav_list.append((name, url, icon))
        with xbmcvfs.File(favorites_file, 'w') as fav:
            fav.write(repr(fav_list))


def get_favorites():
    for name, item_url, icon in fav_list:
        fav_mode = 'play'
        if not item_url.startswith('http'):
            # it's a podcast id
            fav_mode = 'podcast_episodes'
        add_dir(name, item_url, fav_mode, icon)


def rm_favorite(fav_name):
    new_list = list(fav_list)
    for i in range(len(new_list)):
        if new_list[i][0] == fav_name:
            del fav_list[i]
            break
    with xbmcvfs.File(favorites_file, 'w') as fav:
        fav.write(repr(fav_list))


def resolve_url(stream_url):
    success = False
    if stream_url.endswith('.pls'):
        resolved_url = parse_pls(stream_url)
    else:
        resolved_url = stream_url
    if resolved_url:
        success = True
    item = xbmcgui.ListItem(path=resolved_url)
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), success, item)


params = ()
if '=' in sys.argv[2]:
    try:
        params = {i.split('=')[0]: unquote_plus(i.split('=')[1]) for
                  i in sys.argv[2][1:].split('&')}
        addon_log('Addon args: {}'.format(params), True)
    except IndexError as err:
        addon_log('IndexError {}; args: {}'.format(err, sys.argv[2]))

mode = None
if 'mode' in params:
    mode = params['mode']

if mode is None:
    display_main()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'play':
    resolve_url(params['url'])

elif mode == 'podcast_category':
    display_podcast_category(params['url'])
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'podcast_episodes':
    display_podcast_episodes(params['url'])
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'podcast':
    resolve_url(resolve_podcast_url(params['url']))

elif mode == 'menu':
    display_menu()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'add_favorite':
    add_favorite(params['name'], params['url'], params['icon'])
    get_favorites()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'rm_favorite':
    rm_favorite(params['name'])
    get_favorites()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
