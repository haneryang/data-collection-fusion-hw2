# -*- coding: utf-8 -*-
"""
作业2：使用 requests + json 定向爬取 A 股股票行情信息并入库
来源站点：新浪财经-行情中心 https://finance.sina.com.cn/stock/
接口说明：浏览器 F12 抓包可得行情列表 JSON 接口（Market_Center.getHQNodeData），
    node=hs_a 表示沪深 A 股；返回数组，主要字段：
        symbol 带市场前缀的代码(如 sh600000) / code 纯代码 / name 名称 /
        trade 最新价 / pricechange 涨跌额 / changepercent 涨跌幅(%) /
        volume 成交量(股) / amount 成交额(元)
方法：requests 分页请求 JSON -> json 解析 -> 存入 SQLite 数据库
作者：102402154 韩尔洋
运行环境：Python 3.13 / requests / sqlite3(标准库)
运行方式：python 2.py
"""

import os
import time
import sqlite3
from datetime import datetime

import requests

# ----------------------------------------------------------------------------
# 1. 基础配置
# ----------------------------------------------------------------------------
# 行情列表接口
LIST_URL = ("https://vip.stock.finance.sina.com.cn/quotes_service/api/"
            "json_v2.php/Market_Center.getHQNodeData")
# 股票总数接口
COUNT_URL = ("https://vip.stock.finance.sina.com.cn/quotes_service/api/"
             "json_v2.php/Market_Center.getHQNodeStockCount")

NODE = "hs_a"      # 沪深 A 股节点
PAGE_SIZE = 100    # 每页条数

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Referer": "https://finance.sina.com.cn/stock/",
}

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock.db")

# 预留 MySQL 连接方式（pymysql）：
# import pymysql
# conn = pymysql.connect(host="127.0.0.1", port=3306, user="root",
#                        password="你的密码", database="stock", charset="utf8mb4")


def to_float(value):
    """把接口返回值安全转换为浮点数； '-'、None 等非法值返回 None。"""
    if value in ("-", "", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_total() -> int:
    """请求 A 股股票总数；失败时返回 0（仅用于进度参考，不影响翻页）。"""
    try:
        r = requests.get(COUNT_URL, params={"node": NODE}, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return int(r.text.strip().strip('"'))
    except (requests.RequestException, ValueError):
        return 0


def fetch_page(page: int) -> list[dict]:
    """请求一页行情数据，返回原始字典列表。"""
    params = {
        "page": page,
        "num": PAGE_SIZE,
        "sort": "symbol",
        "asc": 1,
        "node": NODE,
        "symbol": "",
        "_s_r_a": "init",
    }
    resp = requests.get(LIST_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    # 接口直接返回 JSON 数组
    return resp.json() or []


def parse_stocks(items: list[dict]) -> list[dict]:
    """将原始记录映射为结构化字典列表。"""
    stocks: list[dict] = []
    for item in items:
        stocks.append({
            "code": item.get("code", ""),
            "symbol": item.get("symbol", ""),
            "name": item.get("name", ""),
            "price": to_float(item.get("trade")),
            "change_amount": to_float(item.get("pricechange")),
            "change_pct": to_float(item.get("changepercent")),
            "volume": to_float(item.get("volume")),
            "amount": to_float(item.get("amount")),
        })
    return stocks


def init_db(conn: sqlite3.Connection) -> None:
    """创建股票行情表（不存在则创建）。"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS stock (
            code           TEXT PRIMARY KEY,
            symbol         TEXT,
            name           TEXT,
            price          REAL,
            change_amount  REAL,
            change_pct     REAL,
            volume         REAL,
            amount         REAL,
            crawl_time     TEXT
        )
        """
    )
    conn.commit()


def save_to_db(conn: sqlite3.Connection, stocks: list[dict]) -> None:
    """批量写入股票记录；代码为主键，重复时替换为最新行情。"""
    crawl_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.executemany(
        """
        INSERT OR REPLACE INTO stock
            (code, symbol, name, price, change_amount, change_pct, volume, amount, crawl_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (s["code"], s["symbol"], s["name"], s["price"], s["change_amount"],
             s["change_pct"], s["volume"], s["amount"], crawl_time)
            for s in stocks
        ],
    )
    conn.commit()


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    total = fetch_total()
    if total:
        print(f"接口返回 A 股股票总数：{total}")

    all_stocks: list[dict] = []
    page = 1

    while True:
        items = fetch_page(page)
        if not items:
            break
        stocks = parse_stocks(items)
        all_stocks.extend(stocks)

        # 已取满总数或本页不足一页时结束翻页
        if total and len(all_stocks) >= total:
            break
        if len(items) < PAGE_SIZE:
            break
        page += 1
        time.sleep(0.5)  # 分页礼貌延时

    save_to_db(conn, all_stocks)
    print(f"本次共入库 {len(all_stocks)} 只股票行情，数据库文件：{DB_PATH}")

    # 入库核对：统计总条数与首条记录，确认与接口返回总数一致
    count = conn.execute("SELECT COUNT(*) FROM stock").fetchone()[0]
    first = conn.execute(
        "SELECT code, name, price, change_pct FROM stock ORDER BY code LIMIT 1"
    ).fetchone()
    print(f"[核对] 数据库共 {count} 只股票，首条记录：{first}")
    conn.close()


if __name__ == "__main__":
    main()
