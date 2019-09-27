from steam.client import SteamClient
from steam.steamid import SteamID
from steam.webapi import WebAPI
from steam.enums import EResult
import sys, os, os.path
import platform
import re
import json
import winreg
import urllib.request
import struct
import traceback
import vdf
import struct
from collections import namedtuple

OS_TYPE = platform.system()
if OS_TYPE == "Windows":
    import winreg
elif OS_TYPE == "Darwin":
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context


SGDB_API_KEY = "e7732886b6c03a829fccb9c14fff2685"
STEAM_CONFIG = "{}/config/config.vdf"
STEAM_LOGINUSER = "{}/config/loginusers.vdf"
STEAM_GRIDPATH = "{}/userdata/{}/config/grid"
STEAM_APPINFO =  "{}/appcache/appinfo.vdf"
STEAM_PACKAGEINFO = "{}/appcache/packageinfo.vdf"
STEAM_CLIENTCONFIG = "{}/userdata/{}/7/remote/sharedconfig.vdf"
STEAM_USERCONFIG = "{}/userdata/{}/config/localconfig.vdf"


def get_owned_packages(client):
    timeout = 30
    for i in range(timeout):
        if len(client.licenses) == 0:
            client.sleep(1)
        else:
            break
    return list(client.licenses.keys())
    
def get_missing_cover_apps(apps):  
    rst = {}
    for appid,app in apps.items():
        if "common" in app and app["common"]["type"] == "Game" and not "library_assets" in app["common"]:
            rst[int(appid)] = app["common"]["name"]
    return rst
    
def split_list(l,n):
    for i in range(0,len(l),n):
        yield l[i:i+n]
    
def retry_func(func,errorhandler=print,retry=3):
    for i in range(retry):
        try:
            rst = func()
            return rst,True
        except Exception as ex:
            errorhandler(ex)
            continue
    return None,False
    
def get_app_details(client,appids,split=200):
    rst = {}
    for i,sublist in enumerate(split_list(appids,split),1):
        print("Loading app details:",i*split)
        subrst, success = retry_func(lambda: client.get_product_info(sublist))
        if success:
            rst.update(subrst['apps'])
    return rst




def appinfo_loads(data):

    # These should always be present.
    version, universe = struct.unpack_from("<II",data,0)
    offset = 8
    if version != 0x07564427 and universe != 1:
        raise ValueError("Invalid appinfo header")
    result = {}
    # Parsing applications
    app_fields = namedtuple("App",'size state last_update access_token checksum change_number')
    app_struct = struct.Struct("<3IQ20sI")
    while True:
        app_id = struct.unpack_from('<I',data,offset)[0]
        offset += 4

        # AppID = 0 marks the last application in the Appinfo
        if app_id == 0:
            break

        # All fields are required.
        app_info = app_fields._make(app_struct.unpack_from(data,offset))

        offset += app_struct.size
        size = app_info.size + 4 - app_struct.size
        app = vdf.binary_loads(data[offset:offset+size])
        offset += size

        result[app_id] = app['appinfo']

    return result


def get_app_details_local(steampath):
    appinfo_path = STEAM_APPINFO.format(steampath)
    if not os.path.isfile(appinfo_path):
        raise FileNotFoundError("appinfo.vdf not found")
    with open(appinfo_path,"rb") as f:
        appinfo = appinfo_loads(f.read())
    return appinfo

        
def get_package_details(client,pkgids,split=200):
    rst = {}
    for i,sublist in enumerate(split_list(pkgids,split),1):
        print("Loading package details:",i*split)
        subrst, success = retry_func(lambda: client.get_product_info([],sublist))
        if success:
            rst.update(subrst['packages'])
    return rst
    
    
    
def get_appids_from_packages(packages):
    rst = set()
    for pkgid,pkg in packages.items():
        rst = rst | {appid for k,appid in pkg['appids'].items()}
    return list(rst)
    
def query_cover_for_apps(appid):
    req = urllib.request.Request("https://www.steamgriddb.com/api/v2/grids/steam/{}?styles=alternate".format(','.join(appid) if isinstance(appid, list) else appid))
    req.add_header("Authorization", "Bearer {}".format(SGDB_API_KEY))
    jsondata = json.loads(urllib.request.urlopen(req).read().decode("utf-8"))
    return jsondata
    
def get_steamid_local(steampath):
    loginuser_path = STEAM_LOGINUSER.format(steampath)
    if os.path.isfile(loginuser_path):
        with open(loginuser_path) as f:
            login_user = vdf.load(f)
        login_steamids = list(login_user['users'].keys())
        if len(login_steamids) == 1:
            return int(login_steamids[0])
        elif len(login_steamids) == 0:
            return None
        else:
            for id,value in login_user.items():
                if value.get("mostrecent") == 1:
                    return int(id)
            return int(login_steamids[0])
    
def input_steamid():
    str = input("Enter steamid or profile url:")
    try:
        return SteamID(int(str))
    except ValueError:
        return SteamID.from_url(str)
        
def get_steam_installpath():
    if OS_TYPE == "Windows":
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Valve\Steam"
        )
        return winreg.QueryValueEx(key, "SteamPath")[0]
    elif OS_TYPE ==  "Darwin":
        return  os.path.expandvars('$HOME') + "/Library/Application Support/Steam"

def quick_get_image_size(data):
    height = -1
    width = -1

    size = len(data)
    # handle PNGs
    if size >= 24 and data.startswith(b'\211PNG\r\n\032\n') and data[12:16] == b'IHDR':
        try:
            width, height = struct.unpack(">LL", data[16:24])
        except struct.error:
            raise ValueError("Invalid PNG file")
    # Maybe this is for an older PNG version.
    elif size >= 16 and data.startswith(b'\211PNG\r\n\032\n'):
        # Check to see if we have the right content type
        try:
            width, height = struct.unpack(">LL", data[8:16])
        except struct.error:
            raise ValueError("Invalid PNG file")
    # handle JPEGs
    elif size >= 2 and data.startswith(b'\377\330'):
        try:
            index = 0
            size = 2
            ftype = 0
            while not 0xc0 <= ftype <= 0xcf or ftype in [0xc4, 0xc8, 0xcc]:
                index+=size
                while data[index] == 0xff:
                    index += 1
                ftype = data[index]
                index += 1
                size = struct.unpack('>H', data[index:index+2])[0]
            # We are at a SOFn block
            index+=3  # Skip `precision' byte.
            height, width = struct.unpack('>HH', data[index:index+4])
        except struct.error:
            raise ValueError("Invalid JPEG file")
    else:
            raise ValueError("Unsupported format")
 
    return width, height    


def download_image(url,gridpath,appid,retrycount=3):
    try:
        data, success = retry_func(lambda:urllib.request.urlopen(url).read(),
                        lambda ex: print("Download error, retry"),retrycount)
        if not success:
            return False
        width, height = quick_get_image_size(data)
        if width == 600 and height == 900:
            filename = "{}p{}".format(appid,url[-4:])
            with open(os.path.join(gridpath,filename),"wb") as f:
                f.write(data)
            print("Saved to",filename)
            return True
        else:
            print("Image size incorrect:",width,height)
    except:
        traceback.print_exc()

    return False


def download_cover(appid,path,exclude=-1,retrycount=3):
    
    try:
        rst = query_cover_for_apps(appid)
    except :
        print("Failed to retrive cover data")
        return False
    if rst["success"]:
        # sort by score
        covers = rst["data"]
        covers.sort(key=lambda x:x["score"],reverse=True)
        print("Found {} covers".format(len(covers)))
        for value in covers:
            if value["id"] == exclude:
                continue
            print("Downloading cover {} by {}, url: {}".format(value["id"],value["author"]["name"],value["url"]))
            success = download_image(value["url"],path,appid)
            if success:
                return True
    return False


def main(local_mode = True):
    try:
        steam_path = get_steam_installpath()
    except:
        print("Could not find steam install path")
        sys.exit(1)
    print("Steam path:",steam_path)
    local_mode = True

    if local_mode:
        try:

            steamid = SteamID(get_steamid_local(steam_path))
            if not steamid.is_valid():
                steamid = SteamID(input_steamid())
            if not steamid.is_valid():
                sys.exit(2)
            print("SteamID:",steamid.as_32)
            steam_grid_path = STEAM_GRIDPATH.format(steam_path,steamid.as_32)
            if not os.path.isdir(steam_grid_path):
                os.mkdir(steam_grid_path)
            print("Steam grid path:",steam_grid_path)
            print("Reading cached appinfo")
            owned_apps = get_app_details_local(steam_path)
            print("Total apps in library:",len(owned_apps))
            missing_cover_apps =  get_missing_cover_apps(owned_apps)
            missing_cover_appids = set(missing_cover_apps.keys())
        except Exception as error:
            print(error)
            print("Switch to remote mode")
            local_mode = False


    if not local_mode:
        client = SteamClient()
        owned_apps = []
        if client.cli_login() != EResult.OK:
            print("Login Error")
            sys.exit(3)
        else:
            print("Login Success")

        steamid = client.steam_id
        print("SteamID:",steamid.as_32)
        steam_grid_path = STEAM_GRIDPATH.format(steam_path,steamid.as_32)
        if not os.path.isdir(steam_grid_path):
            os.mkdir(steam_grid_path)
        print("Steam grid path:",steam_grid_path)

    
        owned_packageids = get_owned_packages(client)
        print("Total packages in library:",len(owned_packageids))
        owned_packages = get_package_details(client,owned_packageids)
        print("Retriving package details")
        owned_appids = get_appids_from_packages(owned_packages)
        print("Total apps in library:",len(owned_appids))
        if os.path.exists("missingcoverdb.json"):
            with open("missingcoverdb.json",encoding="utf-8") as f:
                missing_cover_apps = {int(appid):value for appid,value in json.load(f).items()}
            print("Loaded database with {} apps missing covers".format(len(missing_cover_apps)))
        else:
            print("Getting app details")
            owned_apps = get_app_details(client,owned_appids)
            missing_cover_apps =  get_missing_cover_apps(owned_apps)
        client.logout()
        missing_cover_appids = set(missing_cover_apps.keys()) & set(owned_appids)
    print("Total games missing cover in library:",len(missing_cover_appids))
    local_cover_appids = {int(file[:len(file)-5]) for file in os.listdir(steam_grid_path) if re.match(r"^\d+p.(png|jpg)$",file)}
    print("Total local covers found:",len(local_cover_appids))
    local_missing_cover_appids = missing_cover_appids - local_cover_appids
    print("Total missing covers locally:",len(local_missing_cover_appids))
    total_downloaded = 0
    batch_query_data = []
    print("Finding covers from steamgriddb.com")
    local_missing_cover_appids = list(local_missing_cover_appids)
    query_size = 50
    for index,sublist in enumerate(split_list(local_missing_cover_appids,query_size)):
        sublist = [str(appid) for appid in sublist]
        print('Querying covers {}-{}'.format(index*query_size+1,index*query_size+len(sublist)))
        rst, success = retry_func(lambda:query_cover_for_apps(sublist))
        if success and rst['success']:
            batch_query_data.extend(rst['data'])
        else:
            print("Failed to retrieve cover info")
            sys.exit(4)
    for appid,queryresult in zip(local_missing_cover_appids,batch_query_data):
        if not queryresult['success'] or len(queryresult['data']) == 0:
            print("No cover found for {} {}".format(appid,missing_cover_apps[appid]))
            continue
        queryresult = queryresult['data'][0]
        print("Found most voted cover for {} {} by {}".format(appid,missing_cover_apps[appid],queryresult["author"]["name"]))
        print("Downloading cover {}, url: {}".format(queryresult["id"],queryresult["url"]))
        success = download_image(queryresult['url'],steam_grid_path,appid)       
        if not success:     
            print("Finding all covers for {} {}".format(appid,missing_cover_apps[int(appid)]))
            success = download_cover(appid,steam_grid_path,queryresult['id'])
        if success:
            total_downloaded += 1
    print("Total cover downloaded:",total_downloaded)

if __name__ == "__main__":
    main() 
    