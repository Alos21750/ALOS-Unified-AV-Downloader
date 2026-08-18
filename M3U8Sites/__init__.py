#!/usr/bin/env python
# coding: utf-8

import M3U8Sites.SiteJableTV
import M3U8Sites.Site91Porn
import M3U8Sites.SiteJavDB
import M3U8Sites.SiteMissAV
import M3U8Sites.SiteSupJav
import M3U8Sites.SiteHanime1

siteList = (
    M3U8Sites.SiteJableTV.SiteJableTV,              # https://jable.tv
    M3U8Sites.SiteJableTV.SiteJableTV_Backup,       # https://fs1.app
    M3U8Sites.SiteMissAV.SiteMissAV,                # https://missav.ai
    M3U8Sites.SiteSupJav.SiteSupJav,                # https://supjav.com
    M3U8Sites.SiteHanime1.SiteHanime1,              # https://hanime1.me

    M3U8Sites.Site91Porn.SiteJableOrg,              # https://www.jable.org
    M3U8Sites.Site91Porn.SiteThisAV,                # https://www.thisav.org
    M3U8Sites.Site91Porn.SitePigAV,                 # https://www.pigav.org
    M3U8Sites.Site91Porn.SitePorn5F,                # https://www.porn5f.org
    M3U8Sites.Site91Porn.Site85Tube,                # https://www.85tube.org
    M3U8Sites.Site91Porn.Site91Porn,                # https://www.91porn.best
    M3U8Sites.Site91Porn.SitePornBest,              # https://www.pornbest.org

    M3U8Sites.SiteJavDB.SiteJavdbLive,              # https://www.javdb.live
    M3U8Sites.SiteJavDB.SiteHAnimeXYZ,              # https://www.hanime.xyz
    M3U8Sites.SiteJavDB.SitePornTW,                 # https://www.porntw.com
    M3U8Sites.SiteJavDB.SitePornJP,                 # https://www.pornjp.org
    M3U8Sites.SiteJavDB.SitePornHK,                 # https://www.pornhk.org
    M3U8Sites.SiteJavDB.SitePornHoHo,               # https://www.pornhoho.com
    M3U8Sites.SiteJavDB.SitePornNVR,                # https://www.pornnvr.me
    M3U8Sites.SiteJavDB.SiteVideo01,                # https://www.video01.org
    M3U8Sites.SiteJavDB.SitePornLuLu,               # https://www.pornlulu.com
    M3U8Sites.SiteJavDB.SiteMIEN321,                # https://www.mien321.cc
    M3U8Sites.SiteJavDB.SiteAApp11,                 # https://www.aapp11.life
    M3U8Sites.SiteJavDB.SiteSeselah,                # https://www.seselah.com
    M3U8Sites.SiteJavDB.SiteXJISHI,                 # https://forum.xjishi.site
)

siteUrlList = (
    M3U8Sites.SiteJableTV.JableTVList,
)


def VaildateUrl(url):
    for site in siteList:
        if site.validate_url(url): return site
    return None


def CreateSite(url, savepath="", silence=False, max_workers=None):
    site = VaildateUrl(url)
    if site is None: return None
    if max_workers is None:
        return site(url, savepath=savepath, silence=silence)
    return site(
        url, savepath=savepath, silence=silence,
        max_workers=max_workers)


def CreateSiteUrlList(url, silence=False):
    for urlList in siteUrlList:
        jList = urlList(url, silence=silence)
        if jList.isVaildLinks():
            return jList
    return None


def consoles_main(url, dest=None, max_workers=None):
    if not url or url == '':
        url = input('輸入支援的網址: ')
    jjob = CreateSite(url, dest, max_workers=max_workers)
    if jjob and jjob.is_url_vaildate():
        jjob.start_download()
        print('下載完成!')


if __name__ == "__main__":
    consoles_main("")
