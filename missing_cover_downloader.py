from steam.client import SteamClient
from steam.steamid import SteamID
from steam.webapi import WebAPI
from steam.enums import EResult
import os,os.path
import re
import json
import winreg
import urllib.request
import struct
import traceback


SGDB_API_KEY = "e7732886b6c03a829fccb9c14fff2685"


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
    
def retry_func(func,retry=3):
    for i in range(retry):
        try:
            rst = func()
            return rst,True
        except:
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
    
def query_cover_for_app(appid):
    req = urllib.request.Request("https://www.steamgriddb.com/api/v2/grids/steam/{}?styles=alternate".format(appid))
    req.add_header("Authorization", "Bearer {}".format(SGDB_API_KEY))
    jsondata = json.loads(urllib.request.urlopen(req).read().decode("utf-8"))
    return jsondata
    
    
def input_steamid():
    str = input("Enter steamid or profile url:")
    try:
        return SteamID(int(str))
    except ValueError:
        return SteamID.from_url(str)
        
def get_steam_installpath():
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"SOFTWARE\Valve\Steam"
    )
    return winreg.QueryValueEx(key, "SteamPath")[0]

def quick_get_image_size(data):
    height = -1
    width = -1

    size = len(data)
    # handle GIFs
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
    # handle JPEG2000s
    else:
            raise ValueError("Unsupported format")
 
    return width, height    

def download_cover(appid,path,retrycount=3):

    try:
        rst = query_cover_for_app(appid)
    except :
        print("Failed to retrive cover data")
        return False
    if rst["success"]:
        # sort by score
        covers = rst["data"]
        covers.sort(key=lambda x:x["score"],reverse=True)
        print("Found {} covers".format(len(covers)))
        for value in covers:
            try:
                print("Downloading ID:{}  url: {}".format(value["id"],value["url"]))
                for i in range(retrycount):
                    try:
                        data = urllib.request.urlopen(value["url"]).read()
                        break
                    except urllib.error.URLError:
                        print("Download error, retry")
                width, height = quick_get_image_size(data)
                if width == 600 and height == 900:
                    filename = "{}p{}".format(appid,value["url"][-4:])
                    with open(os.path.join(path,filename),"wb") as f:
                        f.write(data)
                    print("Saved to",filename)
                    return True
                else:
                    print("Image size incorrect:",width,height)
            except:
                traceback.print_exc()
    return False


#def main():
try:
    steam_path = get_steam_installpath()
except:
    print("Could not find steam install path")
    quit()
print("Steam path:",steam_path)
use_profile = False
client = SteamClient()
owned_apps = []
if client.cli_login() != EResult.OK:
    print("Login Error")
    quit()
else:
    print("Login Success")

steamid = client.steam_id
print("SteamID:",steamid.as_32)
steam_grid_path = os.path.join(steam_path,"userdata",str(steamid.as_32), r'config\grid')
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
missing_cover_appids = {appid for appid in missing_cover_apps.keys()} & set(owned_appids)
print("Total games missing cover in library:",len(missing_cover_appids))
local_cover_appids = {int(file[:len(file)-5]) for file in os.listdir(steam_grid_path) if re.match(r"^\d+p.(png|jpg)$",file)}
print("Total local covers found:",len(local_cover_appids))
local_missing_cover_appids = missing_cover_appids - local_cover_appids
print("Total missing covers locally:",len(local_missing_cover_appids))
total_downloaded = 0
for appid in local_missing_cover_appids:
    print("Finding cover for {} {}".format(appid,missing_cover_apps[appid]))
    success = download_cover(appid,steam_grid_path)
    if success:
        total_downloaded += 1
print("Total cover downloaded:",total_downloaded)

    
    