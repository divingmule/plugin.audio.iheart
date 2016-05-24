import urllib
import urllib2
import os
import json
import time
from traceback import format_exc
from urlparse import urlparse, parse_qs

import StorageServer
from BeautifulSoup import BeautifulSoup, BeautifulStoneSoup

import xbmcplugin
import xbmcgui
import xbmcvfs
import xbmcaddon

addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo('id')
addon_path = xbmc.translatePath(addon.getAddonInfo('path'))
addon_profile = xbmc.translatePath(addon.getAddonInfo('profile'))
addon_fanart = addon.getAddonInfo('fanart')
addon_icon = addon.getAddonInfo('icon')
base_url = 'https://api2.iheart.com/api'
addon_version = addon.getAddonInfo('version')
cache = StorageServer.StorageServer("iheart", 1)
profile = xbmc.translatePath(addon.getAddonInfo('profile'))
if not xbmcvfs.exists(profile):
    xbmcvfs.mkdirs(profile)
favorites_file = os.path.join(profile, 'favorites')
fav_list = []
if xbmcvfs.exists(favorites_file):
    fav_list = eval(open(favorites_file).read())


def addon_log(string):
    try:
        log_message = string.encode('utf-8', 'ignore')
    except:
        log_message = 'addonException: addon_log: %s' %format_exc()
    xbmc.log("[%s-%s]: %s" %(addon_id, addon_version, log_message),
                             level=xbmc.LOGNOTICE)


def make_request(url, data=None, headers={}):
    addon_log('Request URL: %s' %url)
    try:
        req = urllib2.Request(url, data, headers)
        response = urllib2.urlopen(req)
        data = response.read()
        response.close()
        return data
    except urllib2.URLError, e:
        addon_log( 'We failed to open "%s".' %url)
        if hasattr(e, 'reason'):
            addon_log('We failed to reach a server.')
            addon_log('Reason: %s' %e.reason)
        if hasattr(e, 'code'):
            addon_log('We failed with error code - %s.' %e.code)


def get_stations(data=None):
    if data is None:
        url = base_url + '/v2/recs/genre?genreId=&offset=0&limit=24'
        data = json.loads(make_request(url))
    station_list = []
    if data.has_key('values'):
        for i in data['values']:
            item = {}
            if i['content'].has_key('streams'):
                item['label'] = i['label'].encode('utf-8')
                item['sub_label'] = i['subLabel']
                item['id'] = i['content']['id']
                item['genre'] = i['content']['genres'][0]['name']
                item['thumb'] = i['imagePath']
                item['thumb_'] = i['content']['logo']
                item['streams'] = i['content']['streams']
                station_list.append(item)
        return station_list
    elif data.has_key('hits'):
        for i in data['hits']:
            item = {}
            if i.has_key('streams'):
                item['label'] = i['name'].encode('utf-8')
                item['sub_label'] = i['description']
                item['id'] = i['id']
                item['genre'] = i['genres'][0]['name']
                item['thumb'] = i['logo']
                item['streams'] = i['streams']
                station_list.append(item)
            elif i.has_key('content') and i['stationType'] == 'LIVE':
                item['label'] = i['content'][0]['name'].encode('utf-8')
                item['sub_label'] = i['content'][0]['description']
                item['id'] = i['id']
                item['genre'] = i['content'][0]['genres'][0]['name']
                item['thumb'] = i['content'][0]['logo']
                item['streams'] = i['content'][0]['streams']
                station_list.append(item)
        return station_list


def get_stw_stream(url):
    data = BeautifulStoneSoup(make_request(url))
    server_url = ('http://%s/%s' %
            (data('server')[0].ip.string, data.mount.string))
    return server_url


def get_talk_categories():
    return json.loads(make_request(base_url + '/v1/talk/getCategories'))


def display_main():
    add_dir('Menu', '', 'menu', addon_icon)
    display_stations(cache.cacheFunction(get_stations))


def display_stations(station_list):
    playable_streams = ['stw_stream', 'shoutcast_stream', 'pls_stream',
            'flv_stream', 'rtmp_stream', 'hls_stream']
    for i in station_list:
        stream_key = [x for x in playable_streams if i['streams'].has_key(x)]
        if stream_key:
            if stream_key[0] == 'stw_stream' and i['streams']['stw_stream']:
                stream = '%s-STW' %i['streams'][stream_key[0]]
            else:
                stream = i['streams'][stream_key[0]]
            try:
                title = i['label'].encode('utf-8')
            except:
                addon_log(format_exc())
                continue
            info = {'title': title, 'genre': i['genre']}
            add_dir(title, stream, 'play', i['thumb'], info, i['id'])


def get_markets():
    url = base_url + '/v2/content/markets?countryCode=US&limit=10000'
    return json.loads(make_request(url))


def get_market(market_id):
    url = (base_url + '/v2/content/liveStations?countryCode=US&'
            'limit=10000&marketId=%s')
    return json.loads(make_request(url %market_id))


def get_genres():
    url = base_url + '/v2/content/liveStationGenres?countryCode=US&limit=10000'
    return json.loads(make_request(url))


def get_genre(genre_id):
    url = base_url + '/v2/content/liveStations?genreId=%s&limit=1000'
    return json.loads(make_request(url %genre_id))


def display_markets():
    data = cache.cacheFunction(get_markets)
    dialog = xbmcgui.Dialog()
    ret = dialog.select('Markets', ['%s, %s' %(i['city'], i['stateName']) for
            i in data['hits']])
    if ret >= 0:
        display_market(data['hits'][ret]['marketId'])


def display_market(market_id):
    data = cache.cacheFunction(get_market, market_id)
    display_stations(get_stations(data))


def display_genres():
    data = cache.cacheFunction(get_genres)
    dialog = xbmcgui.Dialog()
    ret = dialog.select('Genres', [i['name'] for i in data['hits']])
    if ret >= 0:
        data = cache.cacheFunction(get_genre, data['hits'][ret]['id'])
        display_stations(get_stations(data))


def display_talk_categories():
    data = cache.cacheFunction(get_talk_categories)
    dialog = xbmcgui.Dialog()
    ret = dialog.select('Select', [i['name'] for i in data['categories']])
    if ret >= 0:
        display_talk_category(data['categories'][ret]['categoryId'])


def display_talk_category(categoryId):
    url = ('%s/v1/talk/getCategory?categoryId=%s&includeShows=true' %
            (base_url, categoryId))
    data = json.loads(make_request(url))
    for i in data['categories'][0]['shows']:
        add_dir(i['title'].encode('utf-8'), i['id'], 'show', i['imagePath'])


def display_show_episodes(show_id):
    url = ('%s/v1/talk/getShow?showId=%s&offset=0&maxRows=20' %
            (base_url, show_id))
    data = json.loads(make_request(url))
    for i in data['showRestValue']['allepisodes']:
        add_dir(i['title'].encode('utf-8'), i['externalUrl'], 'play',
                i['image'], {'duration': i['duration']})


def display_menu():
    menu_items = ['Favorites','Markets', 'Genres', 'Search', 'Podcasts']
    dialog = xbmcgui.Dialog()
    ret = dialog.select('Menu', menu_items)
    if ret >= 0:
        if menu_items[ret] == 'Markets':
            display_markets()
        elif menu_items[ret] == 'Genres':
            display_genres()
        elif menu_items[ret] == 'Search':
            search()
        elif menu_items[ret] == 'Favorites':
            get_favorites()
        elif menu_items[ret] == 'Podcasts':
            display_talk_categories()
        elif menu_items[ret] == 'Last Played':
            get_last_played()


def search():
    keyboard = xbmc.Keyboard('','Search')
    keyboard.doModal()
    if (keyboard.isConfirmed() == False):
        return
    search_q = keyboard.getText()
    if len(search_q) == 0:
        return
    search_params = {
        'countryCode': 'US',
        'keywords': search_q,
        'queryArtist': 'false',
        'queryBundle': 'false',
        'queryFeaturedStation': 'true',
        'queryKeyword': 'true',
        'queryStation': 'true',
        'queryTalkShow': 'false',
        'queryTalkTheme': 'false',
        'queryTrack': 'false',
        'startIndex': '0'
        }
    search_url = ('%s/v1/catalog/searchAll?%s' %
            (base_url, urllib.urlencode(search_params)))
    data = json.loads(make_request(search_url))
    if data.has_key('stations') and data['stations']:
        get_live_stations(data['stations'])


def get_live_stations(station_list):
    for i in station_list:
        sdata = (json.loads(make_request('%s/v2/content/liveStations/%s' %
                (base_url, i['id']))))
        display_stations(get_stations(sdata))


def add_dir(name, url, mode, iconimage, info={}, station_id=None):
    params = {'name': name, 'url': url, 'mode': mode, 'id': station_id}
    url = '%s?%s' %(sys.argv[0], urllib.urlencode(params))
    listitem = xbmcgui.ListItem(name, iconImage=iconimage,
            thumbnailImage=iconimage)
    is_folder = True
    if mode == 'play':
        is_folder = False
        listitem.setProperty('IsPlayable', 'true')
        fav_mode = 'add_favorite'
        menu_title = 'Add add-on favorite'
        if name in str(fav_list):
            fav_mode = 'rm_favorite'
            menu_title = 'Remove add-on favorite'
        contextMenu = [(menu_title,
                        'RunPlugin(plugin://plugin.audio.iheart/?'
                        'mode=%s&name=%s&url=%s&iconimage=%s)'
                        %(fav_mode, name, params['url'], iconimage))]
        listitem.addContextMenuItems(contextMenu)
    listitem.setProperty("Fanart_Image", addon_fanart)
    listitem.setInfo(type = 'music', infoLabels = info)
    xbmcplugin.addDirectoryItem(int(sys.argv[1]), url, listitem, is_folder)


def get_time():
    return str(int(time.time() * 1000))


def add_favorite(name, url, iconimage):
    fav_list.append((name, url, iconimage))
    a = open(favorites_file, "w")
    a.write(repr(fav_list))
    a.close()


def get_favorites():
    for name, item_url, iconimage in fav_list:
        add_dir(name, item_url, 'play', iconimage)


def rm_favorite(fav_name):
    new_list = list(fav_list)
    for i in range(len(new_list)):
        if new_list[i][0] == fav_name:
            del fav_list[i]
            break
    a = open(favorites_file, "w")
    a.write(repr(fav_list))
    a.close()
    xbmc.executebuiltin('Container.Refresh')


def resolve_url(stream_url, station_id):
    success = False
    resolved_url = ''
    if stream_url.endswith('-STW'):
        resolved_url = get_stw_stream(stream_url.rstrip('-STW'))
    else:
        resolved_url = stream_url
    if resolved_url:
        success = True
    item = xbmcgui.ListItem(path=resolved_url)
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), success, item)


def get_params():
    p = parse_qs(sys.argv[2][1:])
    for i in p.keys():
        p[i] = p[i][0]
    return p


params = get_params()
addon_log("params: %s" %params)

try:
    mode = params['mode']
except:
    mode = None
    addon_log('get root directory')

if mode is None:
    display_main()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'play':
    resolve_url(params['url'], params['id'])

elif mode == 'markets':
    display_markets()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'market':
    display_market(params['url'])
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'show':
    display_show_episodes(params['url'])
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'menu':
    display_menu()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'add_favorite':
    add_favorite(params['name'], params['url'], params['iconimage'])

elif mode == 'rm_favorite':
    rm_favorite(params['name'])