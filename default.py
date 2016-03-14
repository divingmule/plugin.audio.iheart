import urllib
import urllib2
import re
import os
import json
import cookielib
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
base_url = 'https://api2.iheart.com/api/v2'
addon_version = addon.getAddonInfo('version')
cache = StorageServer.StorageServer("iheart", 1)
profile = xbmc.translatePath(addon.getAddonInfo('profile'))
favorites_file = os.path.join(profile, 'favorites')

def addon_log(string):
    try:
        log_message = string.encode('utf-8', 'ignore')
    except:
        log_message = 'addonException: addon_log: %s' %format_exc()
    xbmc.log("[%s-%s]: %s" %(addon_id, addon_version, log_message),
                             level=xbmc.LOGNOTICE)


def make_request(url):
    addon_log('Request URL: %s' %url)
    try:
        req = urllib2.Request(url)
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
        url = base_url + '/recs/genre?genreId=&offset=0&limit=24'
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
        return station_list


def get_stw_stream(url):
    data = BeautifulStoneSoup(make_request(url))
    u_format = 'http://%s/%s'
    mount = data.mount.string
    u_list = []
    for i in data('server'):
        u_list.append(u_format %(i.ip.string, mount))
    return u_list[0]


def display_main():
    add_dir('Menu', '', 'menu', addon_icon)
    data = cache.cacheFunction(get_stations)
    display_stations(data)


def display_stations(data):
    playable_streams = ['stw_stream', 'shoutcast_stream', 'pls_stream',
            'flv_stream', 'rtmp_stream', 'hls_stream']
    for i in data:
        stream_key = [x for x in playable_streams if i['streams'].has_key(x)]
        if stream_key:
            if stream_key[0] == 'stw_stream' and i['streams']['stw_stream']:
                stream = '%s-STW' %i['streams'][stream_key[0]]
            else:
                stream = i['streams'][stream_key[0]]
            info = {'title': i['label'], 'genre': i['genre']}
            add_dir(i['label'], stream, 'play', i['thumb'], info)


def get_markets():
    url = base_url + '/content/markets?countryCode=US&limit=10000'
    return json.loads(make_request(url))


def get_market(market_id):
    url = (base_url + '/content/liveStations?countryCode=US&'
            'limit=10000&marketId=%s')
    return json.loads(make_request(url %market_id))


def get_genres():
    url = base_url + '/content/liveStationGenres?countryCode=US&limit=10000'
    return json.loads(make_request(url))


def get_genre(genre_id):
    url = base_url + '/recs/genre?genreId=%s&limit=100'
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
        addon_log(str(data))
        display_stations(get_stations(data))


def display_menu():
    menu_items = ['Markets', 'Genres']
    dialog = xbmcgui.Dialog()
    ret = dialog.select('Menu', menu_items)
    if ret >= 0:
        if menu_items[ret] == 'Markets':
            display_markets()
        elif menu_items[ret] == 'Genres':
            display_genres()



def search():
    keyboard = xbmc.Keyboard('','Search')
    keyboard.doModal()
    if (keyboard.isConfirmed() == False):
        return
    search_q = keyboard.getText()
    if len(search_q) == 0:
        return
    add_stations('/search/?q=%s' %search_q)



def add_dir(name, url, mode, iconimage, info={}):
    params = {'name': name, 'url': url, 'mode': mode}
    url = '%s?%s' %(sys.argv[0], urllib.urlencode(params))
    listitem = xbmcgui.ListItem(name, iconImage=iconimage,
            thumbnailImage=iconimage)
    is_folder = True
    if mode == 'play':
        is_folder = False
        listitem.setProperty('IsPlayable', 'true')
    listitem.setProperty("Fanart_Image", addon_fanart)
    listitem.setInfo(type = 'music', infoLabels = info)
    xbmcplugin.addDirectoryItem(int(sys.argv[1]), url, listitem, is_folder)


def add_favorite(name, url, iconimage):
    favorites = xbmcvfs.exists(favorites_file)
    if not favorites:
        fav_list = []
    else:
        fav_list = eval(open(favorites_file).read())
    fav_list.append((name, url, iconimage))
    a = open(favorites_file, "w")
    a.write(repr(fav_list))
    a.close()


def get_favorites():
    if xbmcvfs.exists(favorites_file):
        fav_list = eval(open(favorites_file).read())
        for name, item_url, iconimage in fav_list:
            add_station(name.title(), item_url, iconimage, 'fav')


def rm_favorite(fav_name):
    fav_list = eval(open(favorites_file).read())
    new_list = list(fav_list)
    for i in range(len(new_list)):
        if new_list[i][0] == fav_name:
            del fav_list[i]
            break
    a = open(favorites_file, "w")
    a.write(repr(fav_list))
    a.close()


def resolve_url(stream_url):
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
    resolve_url(params['url'])


elif mode == 'markets':
    display_markets()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'market':
    display_market(params['url'])
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 'menu':
    display_menu()
    xbmcplugin.endOfDirectory(int(sys.argv[1]))