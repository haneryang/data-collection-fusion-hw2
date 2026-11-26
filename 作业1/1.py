# -*- coding: utf-8 -*-
"""
作业1：中国天气网 3~5 个城市 7 日天气预报爬取并入库
来源站点：http://www.weather.com.cn
方法：requests 请求 7 日预报页面 -> BeautifulSoup 解析 HTML -> 存入 SQLite 数据库
作者：102402154 韩尔洋
运行环境：Python 3.13 / requests / beautifulsoup4 / sqlite3(标准库)
运行方式：python 1.py
"""

import os
import time
import sqlite3
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# ----------------------------------------------------------------------------
# 1. 基础配置
# ----------------------------------------------------------------------------
# 待查询城市：城市名 -> 中国天气网城市编码（编码可在 weather.com.cn 对应城市页面 URL 中获得）
CITY_CODES = {
    "北京": "101010100",
    "上海": "101020100",
    "福州": "101230101",
    "广州": "101280101",
    "成都": "101270101",
}

BASE_URL = "http://www.weather.com.cn/weather/{code}.shtml"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
}

# 数据库文件放在本脚本所在目录下
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weather.db")

# 若需要改用 MySQL，可使用 pymysql 按如下方式连接（此处仅作预留说明）：
# import pymysql
# conn = pymysql.connect(host="127.0.0.1", port=3306, user="root",
#                        password="你的密码", database="weather", charset="utf8mb4")


def fetch_html(code: str) -> str:
    """根据城市编码请求 7 日预报页面，返回页面 HTML 文本。"""
    url = BASE_URL.format(code=code)
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.encoding = "utf-8"  # 天气网页面为 UTF-8 编码
    resp.raise_for_status()
    return resp.text


def parse_forecast(city: str, code: str, html: str) -> list[dict]:
    """解析 7 日预报列表，返回结构化字典列表。

    页面结构：<ul class="t clearfix"> 下有 7 个 <li>，分别对应今天起 7 天：
        <h1>24日（今天）</h1>            -> 日期
        <p class="wea">小雨转阴</p>       -> 天气现象
        <p class="tem"><span>18</span>/<i>11℃</i></p> -> 高/低温
        <p class="win"><em><span title="无持续风向"/></em><i><3级</i></p> -> 风
    """
    soup = BeautifulSoup(html, "html.parser")
    ul = soup.find("ul", class_="t clearfix")
    forecasts: list[dict] = []

    if ul is None:
        print(f"[警告] {city} 页面未找到 7 日预报列表")
        return forecasts

    for li in ul.find_all("li"):
        # 日期文本，如“24日（今天）”
        date_tag = li.find("h1")
        date_text = date_tag.get_text(strip=True) if date_tag else ""

        # 天气现象，优先取 title 属性，回退到标签文本
        wea_tag = li.find("p", class_="wea")
        if wea_tag is not None:
            weather = wea_tag.get("title") or wea_tag.get_text(strip=True)
        else:
            weather = ""

        # 温度：<span> 最高温，<i> 最低温（末尾带 ℃）
        tem_tag = li.find("p", class_="tem")
        temp_high, temp_low = "", ""
        if tem_tag is not None:
            span = tem_tag.find("span")
            i_tag = tem_tag.find("i")
            temp_high = span.get_text(strip=True) if span else ""
            temp_low = i_tag.get_text(strip=True).replace("℃", "") if i_tag else ""

        # 风向与风力
        win_tag = li.find("p", class_="win")
        wind_dir, wind_level = "", ""
        if win_tag is not None:
            em = win_tag.find("em")
            if em is not None:
                first_span = em.find("span")
                if first_span is not None:
                    wind_dir = first_span.get("title", "")
            level = win_tag.find("i")
            if level is not None:
                wind_level = level.get_text(strip=True)

        forecasts.append({
            "city": city,
            "city_code": code,
            "date_text": date_text,
            "weather": weather,
            "temp_high": temp_high,
            "temp_low": temp_low,
            "wind_dir": wind_dir,
            "wind_level": wind_level,
        })

    return forecasts


def init_db(conn: sqlite3.Connection) -> None:
    """创建天气预报表（不存在则创建）。"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS weather_forecast (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            city        TEXT NOT NULL,
            city_code   TEXT NOT NULL,
            date_text   TEXT NOT NULL,
            weather     TEXT,
            temp_high   TEXT,
            temp_low    TEXT,
            wind_dir    TEXT,
            wind_level  TEXT,
            crawl_time  TEXT
        )
        """
    )
    conn.commit()


def save_to_db(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """将一批预报记录写入数据库，先清空该城市旧数据再写入，避免重复。"""
    city = rows[0]["city"]
    crawl_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("DELETE FROM weather_forecast WHERE city = ?", (city,))
    conn.executemany(
        """
        INSERT INTO weather_forecast
            (city, city_code, date_text, weather, temp_high, temp_low,
             wind_dir, wind_level, crawl_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (r["city"], r["city_code"], r["date_text"], r["weather"],
             r["temp_high"], r["temp_low"], r["wind_dir"], r["wind_level"], crawl_time)
            for r in rows
        ],
    )
    conn.commit()


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    total = 0
    for city, code in CITY_CODES.items():
        try:
            html = fetch_html(code)
            rows = parse_forecast(city, code, html)
            if rows:
                save_to_db(conn, rows)
                total += len(rows)
                print(f"[完成] {city}({code}) 入库 {len(rows)} 条 7 日预报")
            time.sleep(1)  # 礼貌延时，避免对站点造成压力
        except requests.RequestException as e:
            print(f"[错误] {city} 请求失败：{e}")

    print(f"\n本次共入库 {total} 条预报，数据库文件：{DB_PATH}")

    # 入库核对：统计总条数、各城市条数与首条记录，便于与网页逐项比对
    count = conn.execute("SELECT COUNT(*) FROM weather_forecast").fetchone()[0]
    per_city = dict(conn.execute("SELECT city, COUNT(*) FROM weather_forecast GROUP BY city").fetchall())
    first = conn.execute(
        "SELECT city, date_text, weather, temp_high, temp_low FROM weather_forecast ORDER BY id LIMIT 1"
    ).fetchone()
    print(f"[核对] 数据库共 {count} 条，各城市条数：{per_city}")
    print(f"[核对] 首条记录：{first}")
    conn.close()


if __name__ == "__main__":
    main()
