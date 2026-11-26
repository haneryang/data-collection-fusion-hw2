# 数据采集与融合技术 · 第二次作业

- 姓名：韩尔洋
- 学号：102402154
- 专业：数据科学与大数据技术
- 运行环境：Python 3.13 / requests / beautifulsoup4 / sqlite3（标准库，零配置可直接运行）

## 目录结构

```
data-collection-fusion-hw2/
├── 第二次作业博客.md          # 作业博客（含实现过程、代码、分析截图与心得）
├── 作业1/                    # ① 中国天气网 7 日天气预报
│   ├── 1.py
│   ├── weather.db
│   └── images/               # 页面分析与结果截图
├── 作业2/                    # ② 新浪财经沪深 A 股行情
│   ├── 2.py
│   ├── stock.db
│   └── images/
└── 作业3/                    # ③ 软科 2021 中国大学主榜
    ├── 3.py
    ├── rank_2021.db
    └── images/               # 接口分析截图与 F12 抓包过程 GIF
```

## 运行方式

各作业脚本依赖同目录下的 SQLite 数据库文件，进入对应目录后直接运行：

```bash
cd 作业1 && python 1.py
cd 作业2 && python 2.py
cd 作业3 && python 3.py
```

## 入库结果

| 作业 | 采集内容 | 入库结果 | 数据库表 |
| --- | --- | --- | --- |
| ① 天气预报 | 北京、上海、福州、广州、成都 5 城 7 日天气 | 35 条（5 城 × 7 天） | `weather_forecast` |
| ② 股票信息 | 沪深 A 股行情：代码、名称、最新价、涨跌幅、成交量、成交额 | 5580 只 | `stock` |
| ③ 大学排名 | 软科 2021 中国大学主榜：排名、学校、省市、类型、总分 | 582 所（含并列名次） | `university_rank` |

## 接口说明

- 天气：`http://www.weather.com.cn/weather/{城市编码}.shtml`，HTML 由 BeautifulSoup 解析。
- 股票：新浪行情中心 `Market_Center.getHQNodeData`（`node=hs_a`，`page/num/sort/asc` 分页），返回 JSON 数组。
- 排名：`https://www.shanghairanking.cn/api/pub/v1/bcur?bcur_type=11&year=2021`，需携带 Referer，返回 JSON。

> 代码中预留了切换 MySQL（pymysql）的连接注释，如需改用 MySQL 取消注释并填写连接信息即可。
