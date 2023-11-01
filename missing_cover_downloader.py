from steam.client import SteamClient
from steam.steamid import SteamID
from steam.webapi import WebAPI
from steam.enums import EResult
import sys, os, os.path
import platform
import re
import json
import urllib.request
import struct
import traceback
import vdf
import argparse
import asyncio
import aiohttp
import license_parser

OS_TYPE = platform.system()
if OS_TYPE == "Windows":
    import winreg
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
elif OS_TYPE == "Darwin" or OS_TYPE == "Linux":
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

def split_list(l,n):
    for i in range(0,len(l),n):
        yield l[i:i+n]
    
def retry_func(func,errorhandler=print,retry=3):
    for _ in range(retry):
        try:
            rst = func()
            return rst,True
        except Exception as ex:
            errorhandler(ex)
            continue
    return None,False


async def retry_func_async(func,errorhandler=print,retry=3):
    for _ in range(retry):
        try:
            rst = await func()
            return rst,True
        except Exception as ex:
            errorhandler(ex)
            continue
    return None,False
    

def input_steamid():
    str = input("Enter steamid or profile url:")
    try:
        return SteamID(int(str))
    except ValueError:
        return SteamID.from_url(str)
        
class SteamDataReader(object): 

    @staticmethod
    def get_steam_installpath():
        if OS_TYPE == "Windows":
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Valve\Steam"
            )
            return winreg.QueryValueEx(key, "SteamPath")[0]
        elif OS_TYPE ==  "Darwin":
            return  os.path.expandvars('$HOME') + "/Library/Application Support/Steam"
        elif OS_TYPE ==  "Linux":
            return  os.path.expandvars('$HOME') + "/.steam/steam"

    
    def get_appids_from_packages(self,packages):
        rst = set()
        for _,pkg in packages.items():
            rst = rst | {appid for k,appid in pkg['appids'].items()}
        return list(rst)


    def get_missing_cover_dict_from_app_details(self,apps):  
        rst = {}
        for appid,app in apps.items():
            if "common" in app and app["common"]["type"].lower() == "game" and not "library_assets" in app["common"]:
                rst[int(appid)] = app["common"]["name"]
        return rst

    def get_app_details(self,packages):
        return {}

    def get_package_details(self,apps):
        return {}

    def get_owned_packages(self):
        return []
    
    def get_missing_cover_app_dict(self,usedb=True):
        
        owned_packageids = self.get_owned_packages()
        print("Total packages in library:",len(owned_packageids))
        print("Retriving package details")
        owned_packages = self.get_package_details(owned_packageids)
        print("Retriving apps in packages")
        owned_appids = self.get_appids_from_packages(owned_packages)
        print("Total apps in library:",len(owned_appids))
        if usedb and os.path.exists("missingcoverdb.json"):
            with open("missingcoverdb.json",encoding="utf-8") as f:
                missing_cover_apps = {int(appid):value for appid,value in json.load(f).items()}
            print("Loaded database with {} apps missing covers".format(len(missing_cover_apps)))
            owned_appids = set(owned_appids)
            return {appid:value for appid,value in missing_cover_apps if appid in owned_appids}
        else:
            print("Retriving app details")
            owned_apps = self.get_app_details(owned_appids)
            return self.get_missing_cover_dict_from_app_details(owned_apps)
            

class SteamDataReaderRemote(SteamDataReader):

    def __init__(self,client,request_batch=200):
        self.client = client
        self.request_batch = request_batch

    def get_steam_id(self):
        return self.client.steam_id

    def get_app_details(self,appids):
        rst = {}
        for i,sublist in enumerate(split_list(appids,self.request_batch)):
            print("Loading app details: {}-{}".format(i*self.request_batch+1,i*self.request_batch+len(sublist)))
            subrst, success = retry_func(lambda: self.client.get_product_info(sublist))
            if success:
                rst.update(subrst['apps'])
        return rst
    
    def get_package_details(self,pkgids):
        rst = {}
        for i,sublist in enumerate(split_list(pkgids,self.request_batch)):
            print("Loading package details: {}-{}".format(i*self.request_batch+1,i*self.request_batch+len(sublist)))
            subrst, success = retry_func(lambda: self.client.get_product_info([],sublist))
            if success:
                rst.update(subrst['packages'])
        return rst

    def get_owned_packages(self):
        timeout = 30
        for _ in range(timeout):
            if len(self.client.licenses) == 0:
                self.client.sleep(1)
            else:
                break
        return list(self.client.licenses.keys())

class SteamDataReaderLocal(SteamDataReader):

    def __init__(self,steampath):
        self.steam_path = steampath
        self.appinfo = None
        self.packageinfo = None

    def get_steam_id(self):
        loginuser_path = STEAM_LOGINUSER.format(self.steam_path)
        if os.path.isfile(loginuser_path):
            with open(loginuser_path,'r',encoding='utf-8') as f:
                login_user = vdf.load(f)
            login_steamids = list(login_user['users'].keys())
            if len(login_steamids) == 1:
                return SteamID(int(login_steamids[0]))
            elif len(login_steamids) == 0:
                return SteamID()
            else:
                for id,value in login_user.items():
                    if value.get("mostrecent") == 1:
                        return int(id)
                return SteamID(int(login_steamids[0]))
        
    def get_app_details(self,appids):
        if not self.appinfo:
            print("Loading appinfo.vdf")
            self.appinfo = self.load_appinfo()
            print("Total apps in local cache",len(self.appinfo))
        return {appid:self.appinfo[appid] for appid in appids if appid in self.appinfo}

    def get_package_details(self,packageids):
        if not self.packageinfo:
            print("Loading packageinfo.vdf")
            self.packageinfo = self.load_packageinfo()
            print("Total packages in local cache",len(self.packageinfo))
        return {packageid:self.packageinfo[packageid] for packageid in packageids if packageid in self.packageinfo}

    def load_appinfo(self):
        appinfo_path = STEAM_APPINFO.format(self.steam_path)
        if not os.path.isfile(appinfo_path):
            raise FileNotFoundError("appinfo.vdf not found")
        with open(appinfo_path,"rb") as f:
            appinfo = vdf.appinfo_loads(f.read())
        return appinfo

    def load_packageinfo(self):
        package_info_path = STEAM_PACKAGEINFO.format(self.steam_path)
        if not os.path.isfile(package_info_path):
            raise FileNotFoundError("packageinfo.vdf not found")
        with open(package_info_path,"rb") as f:
            packageinfo = vdf.packageinfo_loads(f.read())
        return packageinfo

    def get_owned_packages(self):
        steamid32 = self.get_steam_id().as_32
        license_cache_path = f"{self.steam_path}/userdata/{steamid32}/config/licensecache"
        licenses = license_parser.parse(license_cache_path, steamid32).licenses
        #local_config_path = STEAM_USERCONFIG.format(self.steam_path,self.get_steam_id().as_32)
        #with open(local_config_path,'r',encoding='utf-8',errors='replace') as f:
        #    local_config = vdf.load(f)
        return [package.package_id for package in licenses]
        
    


async def query_cover_for_apps(appid,session,styles=None):
    url = "https://www.steamgriddb.com/api/v2/grids/steam/{}?dimensions=600x900".format(','.join(appid) if isinstance(appid, list) else appid)
    if styles:
        url = f'{url}&styles={styles}'
    jsondata = await fetch_url(url,session,'json',headers={"Authorization": "Bearer {}".format(SGDB_API_KEY)})
    if isinstance(appid, list) and jsondata['success']:
        jsondata['data'] = zip(appid, jsondata['data'])
    return jsondata

async def query_sgdbid_for_appid(appid,session):
    url = "https://www.steamgriddb.com/api/v2/games/steam/{}".format(appid)
    jsondata = await fetch_url(url,session,'json',headers={"Authorization": "Bearer {}".format(SGDB_API_KEY)})
    return jsondata

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



async def fetch_url(url, session:aiohttp.ClientSession,returntype='bin',**kwargs):
    resp = await session.get(url,**kwargs)
    resp.raise_for_status()
    if returntype == 'bin':
        return await resp.read()
    elif returntype == 'html':
        return await resp.text()
    elif returntype == 'json':
        return await resp.json()
    raise ValueError("Unsupported return type")


async def download_image(url,gridpath,appid,session,retrycount=3):
    try:
        data, success = await retry_func_async(lambda:fetch_url(url,session,'bin'),
                        lambda ex: print("Download error: {}, retry".format(ex)),retrycount)
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


async def download_cover(appid,path,session,args,excludeid=-1,retrycount=3):
    
    try:
        rst = await query_cover_for_apps(appid,session,args.styles)
    except :
        print("Failed to retrive cover data")
        return False
    if rst["success"]:
        # sort by score
        covers = rst["data"]
        covers.sort(key=lambda x:x["score"],reverse=True)
        print("Found {} covers".format(len(covers)))
        for value in covers:
            if value["id"] == excludeid:
                continue
            print("Downloading cover {} by {}, url: {}".format(value["id"],value["author"]["name"],value["url"]))
            success = await download_image(value["url"],path,appid,session)
            if success:
                return True
    return False

async def download_covers(appids,gridpath,namedict,args):
    
    batch_query_data = []
    query_size = 50
    tasks = []
    proxies = urllib.request.getproxies()
    result = {'total_downloaded':0}
    if 'http' in proxies:
        os.environ['HTTP_PROXY'] = proxies['http']
        os.environ['HTTPS_PROXY'] = proxies['http']
    async with aiohttp.ClientSession(trust_env=True) as session:
        for index,sublist in enumerate(split_list(appids,query_size)):
            sublist = [str(appid) for appid in sublist]
            print('Querying covers {}-{}'.format(index*query_size+1,index*query_size+len(sublist)))
            query_covers = lambda lst: lambda :query_cover_for_apps(lst,session,args.styles)
            tasks.append(asyncio.create_task(retry_func_async(query_covers(sublist))))
            
        rsts = await asyncio.gather(*tasks)
        for rst, success in rsts:
            if success and rst['success']:
                batch_query_data.extend(rst['data'])
            else:
                print("Failed to retrieve cover info")
                sys.exit(4)
        async def task(queue,downloadresult):
            while True:
                appid,queryresult = await queue.get()
                print("Found most voted cover for {} {} by {}".format(appid,namedict[appid],queryresult["author"]["name"]))
                print("Downloading cover {}, url: {}".format(queryresult["id"],queryresult["url"]))
                try:
                    success = await download_image(queryresult['url'],gridpath,appid,session)       
                    if not success:     
                        print("Finding all covers for {} {}".format(appid,namedict[int(appid)]))
                        success = await download_cover(appid,gridpath,queryresult['id'],args)
                    if success:
                        downloadresult['total_downloaded'] += 1
                except Exception as ex:
                    print(ex)
                queue.task_done()
        tasks = []
        queue=asyncio.Queue()

        number_jobs = 0

        for appid,queryresult in batch_query_data:
            appid = int(appid)
            if not queryresult['success']:
                print("Error finding cover for {}, {}".format(appid,' '.join(queryresult['errors'])))
            elif len(queryresult['data']) == 0:
                print("No cover found for {} {}".format(appid,namedict[appid]))
            elif args.min_score!= None and queryresult['data'][0]['score'] < args.min_score:
                print("Most voted cover for {} {} has score of {} < {} , skipping.".format(appid,namedict[appid],queryresult['data'][0]['score'],args.min_score))
            else:
                number_jobs += 1
                queue.put_nowait((appid,queryresult['data'][0]))

        if number_jobs:
            print("Found {} covers, downloading...".format(number_jobs))

        consumers = [asyncio.create_task(task(queue,result)) for i in range(20)]
        
        await queue.join()
        for c in consumers:
            c.cancel()
    return result['total_downloaded']


async def query_cover_for_app_html(appid,session):
    try:
        jsondata, success = await retry_func_async(lambda:query_sgdbid_for_appid(appid,session),
                                                lambda ex: print("Error getting sgdb id for {}: {}, retry".format(appid,ex)))
        if success and jsondata['success']:
            gameid=jsondata['data']['id']
            url = 'https://www.steamgriddb.com/game/{}'.format(gameid)
            html, success = await retry_func_async(lambda:fetch_url(url,session,'html'),
                                                    lambda ex: print("Error getting html {}: {}, retry".format(url,ex)))
            if not success:
                print("Failed to retrive grids for {} frome steamgriddb",appid)
                return None, 0
            soup = BeautifulSoup(html)
            result = []
            grids = soup.select(".grid")
            for grid in grids:
                if len(grid.select("img.d600x900")) != 0:
                    result.append(
                        {
                            'id':int(grid['data-id']),
                            'url':grid.select('.dload')[0]['href'],
                            'score':0,
                            'author':grid.select('.details a')[0].text.strip()
                        }
                    )
            if len(result) == 0:
                return None,grids
            result.sort(key=lambda x:x["score"],reverse=True)
            return result[0],len(grids)
    except:
        pass
    return None,0
    
    

async def download_covers_temp(appids,gridpath,namedict):
    from bs4 import BeautifulSoup

    queue=asyncio.Queue()

    proxies = urllib.request.getproxies()
    if 'http' in proxies:
        os.environ['HTTP_PROXY'] = proxies['http']
        os.environ['HTTPS_PROXY'] = proxies['http']
    
    async with aiohttp.ClientSession(trust_env=True) as session:
        async def get_url(sublist,queue):
            for appid in sublist:
                print("Finding cover for {} {}".format(appid,namedict[appid]))
                cover,total = await query_cover_for_app_html(appid,session)
                if not cover:
                    print("No cover found for {} {}".format(appid,namedict[appid]))
                    continue
                
                await queue.put((appid, cover, total, namedict[appid]))
                
        producers =  [asyncio.create_task(get_url(sublist,queue)) for sublist in split_list(appids,len(appids)//20)]
        
        #use dict to pass by reference
        result = {'total_downloaded':0}

        async def download_img(queue,result):
            while True:
                appid, cover, total, name = await queue.get()
                print("Found {} covers for {} {}".format(total,appid,name))
                print("Downloading cover with highest score, id: {} score:{} by {}, url: {}".format(cover["id"],cover["score"],cover["author"],cover["url"]))
                success = await download_image(cover["url"],gridpath,appid,session)
                if success:
                    result['total_downloaded'] += 1
                queue.task_done()
        
        consumers = [asyncio.create_task(download_img(queue,result)) for i in range(20)]
        await asyncio.gather(*producers)
        await queue.join()
        for c in consumers:
            c.cancel()
        
    return result['total_downloaded']

def main():

    parser = argparse.ArgumentParser(description='Downloads missing covers for new steam UI. Covers are downloaded from steamgriddb.com')
    parser.add_argument('-p','--path', dest='steam_path', type=str, default=None,
                        help='Set Steam installation path.')
    parser.add_argument('-l','--local', action='store_true', dest='local_mode',
                        help='Local mode, this is the default operation.')
    parser.add_argument('-r','--remote', action='store_true', dest='remote_mode',
                        help='Remote mode, if both local and remote are specified, will try local mode first.')
    parser.add_argument('-m','--minscore',  dest='min_score', type=int, default=None,
                        help='Set min score for a cover to be downloaded.')
    parser.add_argument('-s','--styles',  dest='styles', type=str, default=None,
                        help='Set styles of cover, can be comma separated list of alternate, blurred, white_logo, material or no_logo.')
    parser.add_argument('-o','--overwrite', action='store_true', dest='overwrite',
                        help='Overwrite covers that are already present in local steam grid path.')
    parser.add_argument('-d','--delete-local', action='store_true', dest='delete_local',
                        help='Delete local covers for games that already have official ones.')

    args = parser.parse_args()
    
    try:
        if args.steam_path:
            steam_path = args.steam_path
        else:
            steam_path = SteamDataReader.get_steam_installpath()
    except:
        print("Could not find steam install path")
        sys.exit(1)
    print("Steam path:",steam_path)
    
    local_mode = True
    remote_fallback = True
    if not args.local_mode and args.remote_mode:
        local_mode = False
    elif args.local_mode and not args.remote_mode:
        remote_fallback = False

    if local_mode:
        steam_data_reader = SteamDataReaderLocal(steam_path)
        try:
            steamid = steam_data_reader.get_steam_id()
            if not steamid.is_valid():
                steamid = SteamID(input_steamid())
            if not steamid.is_valid():
                print("Invalid steam id")
                sys.exit(2)
            print("SteamID:",steamid.as_32)
            
            
        except Exception as error:
            print(error)
            if remote_fallback:
                print("Switch to remote mode")
                local_mode = False
            else:
                sys.exit(2)


    if not local_mode:
        client = SteamClient()
        if client.cli_login() != EResult.OK:
            print("Login Error")
            sys.exit(3)
        else:
            print("Login Success")

        steam_data_reader = SteamDataReaderRemote(client)

        steamid = client.steam_id
        print("SteamID:",steamid.as_32)
        
    steam_grid_path = STEAM_GRIDPATH.format(steam_path,steamid.as_32)
    if not os.path.isdir(steam_grid_path):
        os.mkdir(steam_grid_path)
    print("Steam grid path:",steam_grid_path)
    missing_cover_app_dict =  steam_data_reader.get_missing_cover_app_dict(not local_mode)
    
    print("Total games missing cover in library:",len(missing_cover_app_dict))
    local_cover_map = {int(file[:len(file)-5]):file for file in os.listdir(steam_grid_path) if re.match(r"^\d+p.(png|jpg)$",file)}
    local_cover_appids = set(local_cover_map.keys())
    print("Total local covers found:",len(local_cover_appids))
    local_missing_cover_appids = missing_cover_app_dict.keys() - local_cover_appids
    print("Total missing covers locally:",len(local_missing_cover_appids))
    if args.overwrite:
        local_missing_cover_appids = set(missing_cover_app_dict.keys())

    if args.delete_local:
        local_duplicate_cover_appids = local_cover_appids - missing_cover_app_dict.keys()
        print(f'Found {len(local_duplicate_cover_appids)} games already have official covers.')
        for appid in local_duplicate_cover_appids:
            path = os.path.join(steam_grid_path,local_cover_map[appid])
            print(f'Deleting file {path}')
            os.remove(path)

    
    print("Finding covers from steamgriddb.com")
    local_missing_cover_appids = list(local_missing_cover_appids)
    local_missing_cover_appids.sort()
    
    total_downloaded = asyncio.run(download_covers(local_missing_cover_appids,steam_grid_path,missing_cover_app_dict,args))
    print("Total cover downloaded:",total_downloaded)
    

if __name__ == "__main__":
    main()
