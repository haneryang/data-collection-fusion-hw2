# -*- coding: utf-8 -*-
"""
作业3：爬取软科 2021 中国大学主榜全部院校信息并入库
来源站点：https://www.shanghairanking.cn/rankings/bcur/2021
接口说明：浏览器 F12 分析页面发包，可得排名数据 JSON 接口：
    /api/pub/v1/bcur?bcur_type=11&year=2021
    返回 data.rankings 数组，主要字段：
        ranking 排名 / univNameCn 学校名称 / province 省市 /
        univCategory 院校类型 / score 总分
方法：requests 请求 JSON -> json 解析 -> 存入 SQLite 数据库
作者：102402154 韩尔洋
运行环境：Python 3.13 / requests / sqlite3(标准库)
运行方式：python 3.py
"""

import os
import sqlite3
from datetime import datetime

import requests

# ----------------------------------------------------------------------------
# 1. 基础配置
# ----------------------------------------------------------------------------
API_URL = "https://www.shanghairanking.cn/api/pub/v1/bcur"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Referer": "https://www.shanghairanking.cn/rankings/bcur/2021",
}

# 查询参数：bcur_type=11 为中国大学主榜，year=2021 为榜单年份
PARAMS = {"bcur_type": 11, "year": 2021}

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rank_2021.db")

# 预留 MySQL 连接方式（pymysql）：
# import pymysql
# conn = pymysql.connect(host="127.0.0.1", port=3306, user="root",
#                        password="你的密码", database="rank", charset="utf8mb4")


def to_float(value):
    """把接口返回值安全转换为浮点数；空字符串、None 等非法值返回 None。"""
    if value in ("", "-", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_rankings() -> list[dict]:
    """请求排名接口，解析并返回结构化院校列表。"""
    resp = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    payload = resp.json()

    # 接口状态码 code=200 表示成功
    if payload.get("code") != 200:
        raise ValueError(f"接口返回异常：{payload.get('msg')}")

    rankings = (payload.get("data") or {}).get("rankings") or []
    result: list[dict] = []
    for item in rankings:
        result.append({
            "ranking": item.get("ranking"),
            "name": item.get("univNameCn", ""),
            "province": item.get("province", ""),
            "category": item.get("univCategory", ""),
            "score": to_float(item.get("score")),
        })
    return result


def init_db(conn: sqlite3.Connection) -> None:
    """创建大学排名表（不存在则创建）。

    说明：软科主榜存在并列名次（同一排名有多所院校），因此排名不作为唯一主键，
    改用自增 id 作主键，ranking 仅作为普通列，保证全部院校都能入库。
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS university_rank (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ranking    INTEGER,
            name       TEXT NOT NULL,
            province   TEXT,
            category   TEXT,
            score      REAL,
            crawl_time TEXT
        )
        """
    )
    conn.commit()


def save_to_db(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """批量写入排名记录；先清空旧数据再写入，避免重复运行产生叠加。"""
    crawl_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("DELETE FROM university_rank")
    conn.executemany(
        """
        INSERT INTO university_rank
            (ranking, name, province, category, score, crawl_time)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (r["ranking"], r["name"], r["province"], r["category"], r["score"], crawl_time)
            for r in rows
        ],
    )
    conn.commit()


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    rows = fetch_rankings()
    save_to_db(conn, rows)

    print(f"本次共入库 {len(rows)} 所院校信息，数据库文件：{DB_PATH}")

    # 入库核对：总条数、含并列名次的名次个数、首条记录，与网页标注总数比对
    count = conn.execute("SELECT COUNT(*) FROM university_rank").fetchone()[0]
    dup = conn.execute(
        "SELECT COUNT(*) FROM (SELECT ranking FROM university_rank GROUP BY ranking HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    first = conn.execute(
        "SELECT ranking, name, province, category, score FROM university_rank ORDER BY ranking LIMIT 1"
    ).fetchone()
    print(f"[核对] 数据库共 {count} 所院校，其中并列名次 {dup} 个；首条记录：{first}")
    conn.close()


if __name__ == "__main__":
    main()
