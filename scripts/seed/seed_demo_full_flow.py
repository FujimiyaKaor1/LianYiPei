"""
Seed a realistic, complete demo dataset for ChainYiPei.

The dataset is deliberately scoped and idempotent: rerunning this script refreshes
only the named demo enterprises and their related records, while keeping the
existing local database intact.
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import or_

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402
from app.models import (  # noqa: E402
    Alert,
    BusinessCard,
    ChatMessage,
    Enterprise,
    FavoriteSupplier,
    HermesPendingAction,
    Inquiry,
    InquiryChat,
    IntentQuote,
    MatchFeedback,
    MatchRecord,
    Message,
    PriceIndex,
    Product,
    Quote,
    RecruitmentTask,
    Transaction,
)

DEMO_MARK = "full_flow_demo_2026"
DEMO_PASSWORD = "123456"

ENTERPRISES: list[dict[str, Any]] = [
    {
        "key": "admin",
        "name": "链易配运营中心",
        "role": "admin",
        "is_admin": True,
        "province": "四川",
        "city": "成都",
        "address": "成都市高新区天府五街200号",
        "contact": "陈运营",
        "phone": "028-86510001",
        "credit": 100,
        "capacity": 0,
        "max_capacity": 0,
        "capital": 1000,
        "scope": "产业链协同平台运营、供需撮合、信用评价服务",
        "keywords": "平台运营,产业链协同,信用评价",
    },
    {
        "key": "gov",
        "name": "成都市产业链协同专班",
        "role": "government",
        "is_admin": True,
        "province": "四川",
        "city": "成都",
        "address": "成都市锦江区督院街30号",
        "contact": "周处长",
        "phone": "028-86630012",
        "credit": 98,
        "capacity": 0,
        "max_capacity": 0,
        "capital": 500,
        "scope": "重点产业链监测、风险预警、招商补链、企业服务",
        "keywords": "产业治理,风险监测,招商补链",
    },
    {
        "key": "buyer_ev",
        "name": "成都星河新能源汽车有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "成都",
        "address": "成都市龙泉驿区汽车城大道168号",
        "contact": "林采购",
        "phone": "138-0001-1001",
        "credit": 91.5,
        "capacity": 720,
        "max_capacity": 1200,
        "capital": 50000,
        "scope": "新能源乘用车整车研发、生产与供应链管理",
        "keywords": "整车制造,三电系统,车规供应链",
        "lead": True,
    },
    {
        "key": "buyer_robot",
        "name": "德阳川西机器人系统有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "德阳",
        "address": "德阳市旌阳区智能制造产业园88号",
        "contact": "唐工",
        "phone": "138-0001-1002",
        "credit": 87.2,
        "capacity": 410,
        "max_capacity": 680,
        "capital": 18000,
        "scope": "工业机器人本体、系统集成、智能产线改造",
        "keywords": "工业机器人,伺服系统,减速机",
        "lead": True,
    },
    {
        "key": "buyer_storage",
        "name": "宜宾长江储能科技有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "宜宾",
        "address": "宜宾市三江新区动力电池产业园6号",
        "contact": "宋经理",
        "phone": "138-0001-1003",
        "credit": 88.8,
        "capacity": 580,
        "max_capacity": 900,
        "capital": 26000,
        "scope": "储能电池系统、BMS、电池包集成",
        "keywords": "储能系统,BMS,电池包",
        "lead": True,
    },
    {
        "key": "buyer_chip",
        "name": "绵阳天府电子科技有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "绵阳",
        "address": "绵阳市科技城新区创新中心12号",
        "contact": "谢总",
        "phone": "138-0001-1004",
        "credit": 84.6,
        "capacity": 320,
        "max_capacity": 560,
        "capital": 12000,
        "scope": "智能控制板、车规传感器模组、工业网关",
        "keywords": "PCB,传感器,工业网关",
    },
    {
        "key": "buyer_rail",
        "name": "成都轨道交通装备集团有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "成都",
        "address": "成都市新都区轨道交通产业园1号",
        "contact": "许部长",
        "phone": "138-0001-1005",
        "credit": 93.1,
        "capacity": 260,
        "max_capacity": 420,
        "capital": 80000,
        "scope": "轨道车辆牵引系统、制动系统、维保装备",
        "keywords": "轨道交通,牵引系统,制动系统",
        "lead": True,
    },
    {
        "key": "buyer_pack",
        "name": "重庆渝芯智能装备有限公司",
        "role": "enterprise",
        "province": "重庆",
        "city": "重庆",
        "address": "重庆市两江新区水土高新园云汉大道9号",
        "contact": "马经理",
        "phone": "138-0001-1006",
        "credit": 82.4,
        "capacity": 300,
        "max_capacity": 480,
        "capital": 9500,
        "scope": "电子封装设备、自动化检测设备、智能工站",
        "keywords": "封装设备,视觉检测,自动化工站",
    },
    {
        "key": "supplier_harness",
        "name": "成都锦城线束科技有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "成都",
        "address": "成都市龙泉驿区车城西二路66号",
        "contact": "罗总",
        "phone": "138-0002-2001",
        "credit": 89.7,
        "capacity": 840,
        "max_capacity": 1100,
        "capital": 6200,
        "scope": "车规级高低压线束、连接器组件、线束检测",
        "keywords": "高压线束,连接器,车规认证",
    },
    {
        "key": "supplier_battery",
        "name": "遂宁安驰电池系统有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "遂宁",
        "address": "遂宁市经开区锂电大道18号",
        "contact": "何经理",
        "phone": "138-0002-2002",
        "credit": 86.9,
        "capacity": 620,
        "max_capacity": 950,
        "capital": 15000,
        "scope": "动力电池模组、储能电池包、热管理结构件",
        "keywords": "电池模组,储能PACK,热管理",
    },
    {
        "key": "supplier_motor",
        "name": "乐山嘉能电驱有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "乐山",
        "address": "乐山市高新区迎宾大道188号",
        "contact": "郑工",
        "phone": "138-0002-2003",
        "credit": 85.4,
        "capacity": 460,
        "max_capacity": 720,
        "capital": 8800,
        "scope": "永磁同步电机、伺服电机、驱动控制器",
        "keywords": "永磁同步电机,伺服电机,电驱",
    },
    {
        "key": "supplier_sensor",
        "name": "绵阳科测传感器有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "绵阳",
        "address": "绵阳市游仙区科学城路21号",
        "contact": "邓博士",
        "phone": "138-0002-2004",
        "credit": 83.6,
        "capacity": 280,
        "max_capacity": 450,
        "capital": 7600,
        "scope": "压力传感器、温度传感器、车规传感器模组",
        "keywords": "MEMS,压力传感器,车规模组",
    },
    {
        "key": "supplier_pcb",
        "name": "成都蓉芯电路有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "成都",
        "address": "成都市郫都区电子信息产业园9号",
        "contact": "吴经理",
        "phone": "138-0002-2005",
        "credit": 81.8,
        "capacity": 700,
        "max_capacity": 960,
        "capital": 9200,
        "scope": "多层PCB、HDI线路板、工业控制板贴装",
        "keywords": "HDI,PCB,SMT",
    },
    {
        "key": "supplier_bearing",
        "name": "自贡精密轴承有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "自贡",
        "address": "自贡市沿滩区高新工业园16号",
        "contact": "蒲经理",
        "phone": "138-0002-2006",
        "credit": 78.9,
        "capacity": 360,
        "max_capacity": 620,
        "capital": 5300,
        "scope": "精密轴承、交叉滚子轴承、机器人关节轴承",
        "keywords": "精密轴承,机器人关节,低噪声",
    },
    {
        "key": "supplier_reducer",
        "name": "德阳重装减速机有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "德阳",
        "address": "德阳市旌阳区装备制造园6号",
        "contact": "韩总",
        "phone": "138-0002-2007",
        "credit": 87.5,
        "capacity": 240,
        "max_capacity": 390,
        "capital": 11000,
        "scope": "RV减速机、谐波减速器、精密齿轮箱",
        "keywords": "RV减速机,谐波减速器,齿轮箱",
    },
    {
        "key": "supplier_diecast",
        "name": "眉山铝镁压铸有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "眉山",
        "address": "眉山市东坡区铝硅产业园3号",
        "contact": "付厂长",
        "phone": "138-0002-2008",
        "credit": 80.6,
        "capacity": 520,
        "max_capacity": 780,
        "capital": 6800,
        "scope": "铝镁合金压铸件、电机壳体、电池箱体",
        "keywords": "压铸,电机壳体,电池箱体",
    },
    {
        "key": "supplier_mold",
        "name": "成都高新精密模具有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "成都",
        "address": "成都市高新区西区合作路188号",
        "contact": "梁经理",
        "phone": "138-0002-2009",
        "credit": 82.7,
        "capacity": 190,
        "max_capacity": 310,
        "capital": 4200,
        "scope": "精密注塑模具、连接器模具、工装夹具",
        "keywords": "精密模具,连接器模具,工装夹具",
    },
    {
        "key": "supplier_chip",
        "name": "重庆西永功率半导体有限公司",
        "role": "enterprise",
        "province": "重庆",
        "city": "重庆",
        "address": "重庆市沙坪坝区西永微电园88号",
        "contact": "彭总",
        "phone": "138-0002-2010",
        "credit": 79.5,
        "capacity": 180,
        "max_capacity": 300,
        "capital": 22000,
        "scope": "IGBT模块、功率器件封装、车规芯片测试",
        "keywords": "IGBT,功率器件,车规测试",
    },
    {
        "key": "supplier_material",
        "name": "宜宾三江新材料有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "宜宾",
        "address": "宜宾市南溪区新材料产业园10号",
        "contact": "任经理",
        "phone": "138-0002-2011",
        "credit": 84.1,
        "capacity": 760,
        "max_capacity": 980,
        "capital": 13000,
        "scope": "工程塑料粒子、阻燃材料、动力电池结构胶",
        "keywords": "工程塑料,阻燃材料,结构胶",
    },
    {
        "key": "supplier_logistics",
        "name": "成都陆港供应链管理有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "成都",
        "address": "成都市青白江区国际铁路港88号",
        "contact": "袁经理",
        "phone": "138-0002-2012",
        "credit": 86.2,
        "capacity": 900,
        "max_capacity": 1300,
        "capital": 3000,
        "scope": "制造业仓配一体、汽配专线、跨省干线运输",
        "keywords": "仓配一体,汽配物流,干线运输",
    },
    {
        "key": "supplier_quality",
        "name": "成都计量检测认证中心有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "成都",
        "address": "成都市双流区物联大道99号",
        "contact": "贺主任",
        "phone": "138-0002-2013",
        "credit": 90.4,
        "capacity": 160,
        "max_capacity": 220,
        "capital": 5600,
        "scope": "车规件检测、可靠性试验、供应商质量审核",
        "keywords": "车规检测,可靠性试验,质量审核",
    },
    {
        "key": "supplier_software",
        "name": "成都云工工业软件有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "成都",
        "address": "成都市天府软件园E区2栋",
        "contact": "邱产品",
        "phone": "138-0002-2014",
        "credit": 88.3,
        "capacity": 120,
        "max_capacity": 180,
        "capital": 5000,
        "scope": "MES系统、供应链协同系统、质量追溯平台",
        "keywords": "MES,追溯系统,供应链协同",
    },
    {
        "key": "supplier_cable",
        "name": "资阳航电电缆有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "资阳",
        "address": "资阳市雁江区临空制造园26号",
        "contact": "蒋经理",
        "phone": "138-0002-2015",
        "credit": 77.8,
        "capacity": 640,
        "max_capacity": 850,
        "capital": 4700,
        "scope": "特种电缆、屏蔽线缆、高压电缆组件",
        "keywords": "特种电缆,屏蔽线,高压组件",
    },
    {
        "key": "supplier_connector",
        "name": "绵阳九洲连接器有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "绵阳",
        "address": "绵阳市经开区塘汛北街22号",
        "contact": "曹经理",
        "phone": "138-0002-2016",
        "credit": 82.9,
        "capacity": 480,
        "max_capacity": 700,
        "capital": 6600,
        "scope": "高速连接器、防水连接器、车载端子组件",
        "keywords": "连接器,端子,防水组件",
    },
    {
        "key": "supplier_heat",
        "name": "南充热控科技有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "南充",
        "address": "南充市顺庆区潆华工业园13号",
        "contact": "廖总",
        "phone": "138-0002-2017",
        "credit": 80.2,
        "capacity": 350,
        "max_capacity": 540,
        "capital": 3900,
        "scope": "液冷板、热管理管路、电池热控组件",
        "keywords": "液冷板,热管理,电池热控",
    },
    {
        "key": "supplier_sheet",
        "name": "遂宁精工钣金有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "遂宁",
        "address": "遂宁市船山区装备制造基地8号",
        "contact": "范厂长",
        "phone": "138-0002-2018",
        "credit": 76.5,
        "capacity": 510,
        "max_capacity": 760,
        "capital": 3100,
        "scope": "精密钣金、机柜壳体、激光切割焊接",
        "keywords": "精密钣金,机柜壳体,激光切割",
    },
    {
        "key": "supplier_optics",
        "name": "成都睿视觉检测设备有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "成都",
        "address": "成都市新津区智能装备产业园2号",
        "contact": "顾经理",
        "phone": "138-0002-2019",
        "credit": 84.9,
        "capacity": 150,
        "max_capacity": 240,
        "capital": 5800,
        "scope": "机器视觉检测设备、AOI系统、缺陷识别软件",
        "keywords": "机器视觉,AOI,缺陷识别",
    },
    {
        "key": "supplier_robotarm",
        "name": "成都天府协作机器人有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "成都",
        "address": "成都市温江区海峡科技园19号",
        "contact": "秦总",
        "phone": "138-0002-2020",
        "credit": 83.2,
        "capacity": 210,
        "max_capacity": 330,
        "capital": 7600,
        "scope": "协作机器人、末端执行器、柔性工站",
        "keywords": "协作机器人,末端执行器,柔性工站",
    },
    {
        "key": "supplier_fastener",
        "name": "内江高强紧固件有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "内江",
        "address": "内江市市中区城西工业园5号",
        "contact": "刘经理",
        "phone": "138-0002-2021",
        "credit": 75.9,
        "capacity": 880,
        "max_capacity": 1200,
        "capital": 2600,
        "scope": "高强螺栓、铆接件、车规紧固件",
        "keywords": "高强螺栓,铆接件,紧固件",
    },
    {
        "key": "supplier_plating",
        "name": "德阳表面工程科技有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "德阳",
        "address": "德阳市罗江区绿色表面处理园1号",
        "contact": "王主任",
        "phone": "138-0002-2022",
        "credit": 74.8,
        "capacity": 300,
        "max_capacity": 480,
        "capital": 3500,
        "scope": "表面处理、阳极氧化、镀镍镀锌",
        "keywords": "表面处理,阳极氧化,镀镍",
    },
    {
        "key": "supplier_packaging",
        "name": "泸州绿色包装材料有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "泸州",
        "address": "泸州市江阳区轻工园区28号",
        "contact": "叶经理",
        "phone": "138-0002-2023",
        "credit": 78.4,
        "capacity": 720,
        "max_capacity": 1050,
        "capital": 2400,
        "scope": "可循环周转箱、工业包装、缓冲防护材料",
        "keywords": "周转箱,工业包装,缓冲材料",
    },
    {
        "key": "supplier_ems",
        "name": "成都高新电子制造服务有限公司",
        "role": "enterprise",
        "province": "四川",
        "city": "成都",
        "address": "成都市双流区电子科创园7号",
        "contact": "魏经理",
        "phone": "138-0002-2024",
        "credit": 85.8,
        "capacity": 560,
        "max_capacity": 820,
        "capital": 8500,
        "scope": "EMS代工、PCBA测试、整机装配",
        "keywords": "EMS,PCBA测试,整机装配",
    },
]

DEMO_ENTERPRISE_NAMES = [row["name"] for row in ENTERPRISES]

PRODUCTS_BY_ENTERPRISE: dict[str, list[dict[str, Any]]] = {
    "buyer_ev": [
        {"name": "整车控制器采购需求", "category": "采购需求", "industry": "C36"},
        {"name": "车规级高压线束需求", "category": "采购需求", "industry": "C36"},
    ],
    "buyer_robot": [
        {"name": "六轴机器人本体", "category": "终端装备", "industry": "C34"},
        {"name": "机器人关节模组需求", "category": "采购需求", "industry": "C34"},
    ],
    "buyer_storage": [
        {"name": "工商业储能柜", "category": "终端装备", "industry": "C37"},
        {"name": "储能电池包需求", "category": "采购需求", "industry": "C37"},
    ],
    "buyer_chip": [
        {"name": "工业控制板需求", "category": "采购需求", "industry": "C38"},
        {"name": "传感器模组需求", "category": "采购需求", "industry": "C38"},
    ],
    "buyer_rail": [
        {"name": "轨交牵引控制单元", "category": "终端装备", "industry": "C37"},
        {"name": "轨交制动传感器需求", "category": "采购需求", "industry": "C37"},
    ],
    "buyer_pack": [
        {"name": "半导体封装自动化线", "category": "终端装备", "industry": "C35"},
        {"name": "AOI视觉检测需求", "category": "采购需求", "industry": "C35"},
    ],
    "supplier_harness": [
        {"name": "车规级高压线束", "category": "汽车零部件", "industry": "C36"},
        {"name": "防水连接线束总成", "category": "汽车零部件", "industry": "C36"},
        {"name": "线束导通检测服务", "category": "质量检测", "industry": "M74"},
    ],
    "supplier_battery": [
        {"name": "磷酸铁锂电池模组", "category": "动力电池", "industry": "C37"},
        {"name": "液冷储能电池包", "category": "储能系统", "industry": "C37"},
        {"name": "电池箱体总成", "category": "结构件", "industry": "C36"},
    ],
    "supplier_motor": [
        {"name": "永磁同步驱动电机", "category": "电驱系统", "industry": "C37"},
        {"name": "低压伺服电机", "category": "机器人部件", "industry": "C37"},
        {"name": "电机控制器", "category": "电控系统", "industry": "C38"},
    ],
    "supplier_sensor": [
        {"name": "车规压力传感器", "category": "传感器", "industry": "C39"},
        {"name": "温度采集模组", "category": "传感器", "industry": "C39"},
        {"name": "轨交制动传感器", "category": "轨交部件", "industry": "C37"},
    ],
    "supplier_pcb": [
        {"name": "六层HDI控制板", "category": "电子元件", "industry": "C38"},
        {"name": "工业网关PCBA", "category": "电子制造", "industry": "C38"},
        {"name": "BMS采集板", "category": "电池管理", "industry": "C38"},
    ],
    "supplier_bearing": [
        {"name": "机器人关节轴承", "category": "精密零部件", "industry": "C34"},
        {"name": "低噪声精密轴承", "category": "精密零部件", "industry": "C34"},
    ],
    "supplier_reducer": [
        {"name": "RV减速机", "category": "机器人部件", "industry": "C34"},
        {"name": "谐波减速器", "category": "机器人部件", "industry": "C34"},
    ],
    "supplier_diecast": [
        {"name": "一体化压铸电机壳体", "category": "金属结构件", "industry": "C33"},
        {"name": "铝合金电池箱体", "category": "金属结构件", "industry": "C33"},
    ],
    "supplier_mold": [
        {"name": "连接器精密注塑模具", "category": "模具", "industry": "C35"},
        {"name": "电池包工装夹具", "category": "工装夹具", "industry": "C35"},
    ],
    "supplier_chip": [
        {"name": "车规IGBT功率模块", "category": "半导体", "industry": "C38", "import_ratio": 0.68},
        {"name": "功率器件封装测试", "category": "半导体服务", "industry": "C38"},
    ],
    "supplier_material": [
        {"name": "阻燃PA66粒子", "category": "工程材料", "industry": "C29", "import_ratio": 0.34},
        {"name": "动力电池结构胶", "category": "化工材料", "industry": "C26"},
    ],
    "supplier_logistics": [
        {"name": "汽配仓配一体服务", "category": "供应链服务", "industry": "G54"},
        {"name": "跨省干线运输", "category": "物流服务", "industry": "G54"},
        {"name": "冷链电池包周转服务", "category": "物流服务", "industry": "G54"},
    ],
    "supplier_quality": [
        {"name": "车规件可靠性试验", "category": "质量检测", "industry": "M74"},
        {"name": "供应商过程审核", "category": "质量服务", "industry": "M74"},
        {"name": "批次追溯审计服务", "category": "质量服务", "industry": "M74"},
    ],
    "supplier_software": [
        {"name": "MES生产执行系统", "category": "工业软件", "industry": "I65"},
        {"name": "供应链质量追溯平台", "category": "工业软件", "industry": "I65"},
        {"name": "产能协同排程系统", "category": "工业软件", "industry": "I65"},
    ],
    "supplier_cable": [
        {"name": "高压屏蔽电缆", "category": "电缆组件", "industry": "C37"},
        {"name": "柔性拖链电缆", "category": "机器人部件", "industry": "C37"},
    ],
    "supplier_connector": [
        {"name": "高速防水连接器", "category": "连接器", "industry": "C38"},
        {"name": "车载端子组件", "category": "连接器", "industry": "C38"},
        {"name": "储能大电流连接器", "category": "连接器", "industry": "C38"},
    ],
    "supplier_heat": [
        {"name": "电池液冷板", "category": "热管理", "industry": "C36"},
        {"name": "热管理管路总成", "category": "热管理", "industry": "C36"},
        {"name": "水冷板气密检测服务", "category": "质量检测", "industry": "M74"},
    ],
    "supplier_sheet": [
        {"name": "精密钣金机柜", "category": "金属结构件", "industry": "C33"},
        {"name": "激光切割焊接服务", "category": "加工服务", "industry": "C33"},
    ],
    "supplier_optics": [
        {"name": "AOI视觉检测设备", "category": "检测设备", "industry": "C35"},
        {"name": "机器视觉缺陷识别系统", "category": "工业软件", "industry": "I65"},
        {"name": "视觉检测算法调试服务", "category": "工业软件", "industry": "I65"},
    ],
    "supplier_robotarm": [
        {"name": "协作机器人本体", "category": "机器人装备", "industry": "C34"},
        {"name": "柔性夹爪末端执行器", "category": "机器人部件", "industry": "C34"},
    ],
    "supplier_fastener": [
        {"name": "车规高强紧固件", "category": "标准件", "industry": "C33"},
        {"name": "铆接螺母组件", "category": "标准件", "industry": "C33"},
    ],
    "supplier_plating": [
        {"name": "连接器镀镍服务", "category": "表面处理", "industry": "C33"},
        {"name": "铝件阳极氧化服务", "category": "表面处理", "industry": "C33"},
    ],
    "supplier_packaging": [
        {"name": "可循环汽配周转箱", "category": "工业包装", "industry": "C29"},
        {"name": "防静电缓冲包装", "category": "工业包装", "industry": "C29"},
    ],
    "supplier_ems": [
        {"name": "PCBA测试代工", "category": "电子制造", "industry": "C38"},
        {"name": "工业控制器整机装配", "category": "电子制造", "industry": "C38"},
        {"name": "三防漆涂覆加工", "category": "电子制造", "industry": "C38"},
    ],
}

DEMO_PRODUCT_NAMES = [
    product["name"]
    for items in PRODUCTS_BY_ENTERPRISE.values()
    for product in items
]


def _dt(days_ago: int = 0, hours_ago: int = 0) -> datetime:
    return datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_ago, hours=hours_ago)


def _delete_if_any(query) -> int:
    return query.delete(synchronize_session=False)


def reset_demo_data() -> None:
    demo_ids = [
        row[0]
        for row in db.session.query(Enterprise.id)
        .filter(Enterprise.name.in_(DEMO_ENTERPRISE_NAMES))
        .all()
    ]

    alert_ids = [
        row[0]
        for row in db.session.query(Alert.id)
        .filter(Alert.product_name.in_(DEMO_PRODUCT_NAMES))
        .all()
    ]
    if alert_ids:
        _delete_if_any(HermesPendingAction.query.filter(HermesPendingAction.alert_id.in_(alert_ids)))

    if demo_ids:
        chat_ids = [
            row[0]
            for row in db.session.query(InquiryChat.id)
            .filter(or_(InquiryChat.buyer_id.in_(demo_ids), InquiryChat.seller_id.in_(demo_ids)))
            .all()
        ]
        if chat_ids:
            _delete_if_any(ChatMessage.query.filter(ChatMessage.chat_id.in_(chat_ids)))
        _delete_if_any(
            RecruitmentTask.query.filter(
                or_(
                    RecruitmentTask.assigned_to.in_(demo_ids),
                    RecruitmentTask.assigned_by.in_(demo_ids),
                    RecruitmentTask.target_product.in_(DEMO_PRODUCT_NAMES),
                )
            )
        )
        _delete_if_any(BusinessCard.query.filter(or_(BusinessCard.initiator_id.in_(demo_ids), BusinessCard.recipient_id.in_(demo_ids))))
        _delete_if_any(IntentQuote.query.filter(or_(IntentQuote.buyer_id.in_(demo_ids), IntentQuote.seller_id.in_(demo_ids))))
        _delete_if_any(InquiryChat.query.filter(or_(InquiryChat.buyer_id.in_(demo_ids), InquiryChat.seller_id.in_(demo_ids))))
        _delete_if_any(FavoriteSupplier.query.filter(or_(FavoriteSupplier.collector_id.in_(demo_ids), FavoriteSupplier.supplier_id.in_(demo_ids))))
        _delete_if_any(MatchRecord.query.filter(or_(MatchRecord.buyer_id.in_(demo_ids), MatchRecord.seller_id.in_(demo_ids))))
        _delete_if_any(MatchFeedback.query.filter(or_(MatchFeedback.buyer_id.in_(demo_ids), MatchFeedback.supplier_id.in_(demo_ids))))
        _delete_if_any(Quote.query.filter(Quote.supplier_id.in_(demo_ids)))
        _delete_if_any(Transaction.query.filter(or_(Transaction.buyer_id.in_(demo_ids), Transaction.seller_id.in_(demo_ids))))
        _delete_if_any(Inquiry.query.filter(or_(Inquiry.poster_id.in_(demo_ids), Inquiry.buyer_id.in_(demo_ids), Inquiry.seller_id.in_(demo_ids))))
        _delete_if_any(Message.query.filter(or_(Message.sender_id.in_(demo_ids), Message.recipient_id.in_(demo_ids))))
        _delete_if_any(Product.query.filter(Product.enterprise_id.in_(demo_ids)))
        _delete_if_any(Enterprise.query.filter(Enterprise.id.in_(demo_ids)))

    _delete_if_any(Alert.query.filter(Alert.product_name.in_(DEMO_PRODUCT_NAMES)))
    _delete_if_any(RecruitmentTask.query.filter(RecruitmentTask.target_product.in_(DEMO_PRODUCT_NAMES)))
    _delete_if_any(PriceIndex.query.filter(PriceIndex.product_name.in_(DEMO_PRODUCT_NAMES)))
    db.session.commit()


def _make_enterprises() -> dict[str, Enterprise]:
    by_key: dict[str, Enterprise] = {}
    city_lng_lat = {
        "成都": (104.0668, 30.5728),
        "德阳": (104.3987, 31.1271),
        "宜宾": (104.6432, 28.7513),
        "绵阳": (104.6796, 31.4675),
        "重庆": (106.5516, 29.5630),
        "遂宁": (105.5929, 30.5329),
        "乐山": (103.7654, 29.5521),
        "自贡": (104.7784, 29.3392),
        "眉山": (103.8485, 30.0754),
        "资阳": (104.6276, 30.1289),
        "南充": (106.1107, 30.8378),
        "内江": (105.0584, 29.5802),
        "泸州": (105.4433, 28.8891),
    }
    for idx, row in enumerate(ENTERPRISES, start=1):
        lng, lat = city_lng_lat.get(row["city"], (104.0668, 30.5728))
        ent = Enterprise(
            name=row["name"],
            address=row["address"],
            longitude=lng + (idx % 5) * 0.012,
            latitude=lat + (idx % 4) * 0.01,
            contact=row["contact"],
            phone=row["phone"],
            credit_score=row["credit"],
            capacity=row["capacity"],
            current_orders=int(row["capacity"] * (0.45 + (idx % 4) * 0.08)) if row["capacity"] else 0,
            max_capacity=row["max_capacity"],
            password_hash=None,
            is_admin=row.get("is_admin", False),
            role=row["role"],
            registered_capital=row["capital"],
            business_scope=row["scope"],
            province=row["province"],
            city=row["city"],
            patent_category="发明专利,实用新型" if row["role"] == "enterprise" else None,
            patent_count=8 + idx % 18 if row["role"] == "enterprise" else 0,
            tech_keywords=row["keywords"],
            rd_investment=round(row["capital"] * 0.018, 2) if row["role"] == "enterprise" else 0,
            industry_code="C36" if "汽车" in row["scope"] else "C34",
            is_green_factory=idx % 3 == 0,
            green_certification={
                "level": "省级绿色工厂" if idx % 3 == 0 else "待申报",
                "valid_until": "2028-12-31",
            },
            clean_energy_usage=round(0.18 + (idx % 6) * 0.07, 2),
            carbon_emission_level=["A", "B", "B", "C"][idx % 4],
            environment_protection_patents=idx % 7,
            green_supplier_rank=["A", "B", "B", "C"][idx % 4],
            verification_status="approved",
            is_verified=True,
            verified_at=_dt(36 - idx),
            registered_at=_dt(180 + idx),
            business_status="存续",
            biz_data_updated_at=_dt(idx % 7),
            daily_quote_count=idx % 3,
            daily_quote_limit=5,
            last_quote_reset_date=date.today(),
            is_lead_enterprise=row.get("lead", False),
            data_freshness_score=round(95 - (idx % 8) * 2.1, 1),
            last_data_update=_dt(idx % 10),
            is_dormant=False,
            current_mode="buyer" if row["key"].startswith("buyer") else "seller",
            wechat_bound=True,
            wechat_work_userid=f"demo_{row['key']}",
            wechat_service_openid=f"openid_demo_{row['key']}",
            wechat_bound_at=_dt(idx % 20),
            wechat_push_preference="all",
            qualifications=[
                {
                    "label_type": "cert",
                    "label_name": "IATF16949" if "车" in row["scope"] else "ISO9001",
                    "issuer_id": 1,
                    "certificate_no": f"DEMO-Q-{idx:04d}",
                    "valid_from": "2025-01-01",
                    "valid_until": "2028-12-31",
                    "status": "valid",
                }
            ],
            data_auth={
                "business": {"authorized": True, "sync_status": "success", "last_sync_at": _dt(1).isoformat()},
                "invoice": {"authorized": row["role"] == "enterprise", "sync_status": "success"},
                "power": {"authorized": row["role"] == "enterprise", "sync_status": "success"},
            },
            cooperation_cases=[
                {
                    "buyer_name_masked": "西南整车龙头" if row["key"].startswith("supplier") else "产业链协同客户",
                    "product_category": row["keywords"].split(",")[0],
                    "cooperation_time": "2025Q4",
                    "amount_range": "100万-500万",
                    "is_public": True,
                }
            ],
            patents=[
                {
                    "patent_no": f"CN2026DEMO{idx:04d}",
                    "title": f"{row['keywords'].split(',')[0]}关键工艺优化方法",
                    "patent_type": "发明专利",
                    "ipc_code": "B23P",
                    "apply_date": "2025-09-18",
                }
            ],
            extras={"demo_dataset": DEMO_MARK, "enterprise_key": row["key"]},
            credit_score_events=[
                {
                    "id": f"demo-credit-{idx}-1",
                    "old_score": max(row["credit"] - 4.5, 60),
                    "new_score": row["credit"],
                    "change_value": 4.5,
                    "change_type": "data_auth",
                    "reason": "完成工商、发票、电力数据授权",
                    "created_at": _dt(12).isoformat(),
                }
            ],
        )
        ent.set_password(DEMO_PASSWORD)
        db.session.add(ent)
        by_key[row["key"]] = ent
    db.session.commit()
    return by_key


def _make_products(enterprises: dict[str, Enterprise]) -> dict[str, Product]:
    products: dict[str, Product] = {}
    for key, rows in PRODUCTS_BY_ENTERPRISE.items():
        ent = enterprises[key]
        for idx, row in enumerate(rows, start=1):
            import_ratio = row.get("import_ratio", 0.08 + (idx % 4) * 0.11)
            product = Product(
                name=row["name"],
                description=f"{ent.name}提供的{row['name']}，适用于{row['category']}场景，支持批量交付和质量追溯。",
                category=row["category"],
                industry_code=row["industry"],
                enterprise_id=ent.id,
                image_path=f"/static/demo/products/{row['name']}.jpg",
                embedding=[round((idx + n) / 100, 4) for n in range(8)],
                created_at=_dt(idx),
                import_risk={
                    "import_ratio": import_ratio,
                    "source_countries": "德国,日本,韩国" if import_ratio >= 0.45 else "国内供应为主",
                    "hs_code": f"DEMO{idx:04d}",
                    "data_source": "演示数据-海关口径模拟",
                    "updated_at": _dt(1).isoformat(),
                },
            )
            db.session.add(product)
            products[row["name"]] = product
    db.session.commit()
    return products


def _make_price_indices() -> list[PriceIndex]:
    names = [
        "车规级高压线束",
        "磷酸铁锂电池模组",
        "永磁同步驱动电机",
        "车规压力传感器",
        "六层HDI控制板",
        "机器人关节轴承",
        "RV减速机",
        "车规IGBT功率模块",
        "电池液冷板",
        "AOI视觉检测设备",
    ]
    rows = []
    for idx, name in enumerate(names, start=1):
        base = [320, 860, 1280, 96, 42, 180, 4200, 560, 240, 118000][idx - 1]
        row = PriceIndex(
            product_name=name,
            median_price=base,
            mean_price=round(base * 1.03, 2),
            std_dev=round(base * 0.08, 2),
            min_price=round(base * 0.84, 2),
            max_price=round(base * 1.22, 2),
            sample_count=36 + idx * 7,
            data_source="demo-realtime",
            last_updated=_dt(idx % 3),
        )
        db.session.add(row)
        rows.append(row)
    db.session.commit()
    return rows


INQUIRY_SPECS = [
    ("buyer_ev", "supplier_harness", "车规级高压线束", 12000, "套", "quoted", 0.92),
    ("buyer_ev", "supplier_battery", "磷酸铁锂电池模组", 1800, "套", "contracted", 0.89),
    ("buyer_ev", "supplier_chip", "车规IGBT功率模块", 900, "件", "contracted", 0.76),
    ("buyer_robot", "supplier_reducer", "RV减速机", 320, "台", "quoted", 0.94),
    ("buyer_robot", "supplier_bearing", "机器人关节轴承", 2200, "套", "contracted", 0.91),
    ("buyer_robot", "supplier_robotarm", "柔性夹爪末端执行器", 180, "套", "fulfilled", 0.84),
    ("buyer_storage", "supplier_battery", "液冷储能电池包", 650, "套", "quoted", 0.88),
    ("buyer_storage", "supplier_heat", "电池液冷板", 4200, "件", "fulfilled", 0.87),
    ("buyer_storage", "supplier_material", "动力电池结构胶", 38, "吨", "open", 0.82),
    ("buyer_chip", "supplier_pcb", "六层HDI控制板", 26000, "片", "quoted", 0.9),
    ("buyer_chip", "supplier_sensor", "温度采集模组", 6000, "套", "fulfilled", 0.86),
    ("buyer_chip", "supplier_ems", "PCBA测试代工", 18000, "片", "contracted", 0.88),
    ("buyer_rail", "supplier_sensor", "轨交制动传感器", 2800, "套", "open", 0.83),
    ("buyer_rail", "supplier_cable", "高压屏蔽电缆", 55, "千米", "quoted", 0.81),
    ("buyer_pack", "supplier_optics", "AOI视觉检测设备", 6, "台", "contracted", 0.93),
    ("buyer_pack", "supplier_sheet", "精密钣金机柜", 420, "套", "open", 0.79),
]


def _make_inquiries_quotes_matches(
    enterprises: dict[str, Enterprise],
    products: dict[str, Product],
) -> tuple[list[Inquiry], list[Quote], list[MatchFeedback], list[MatchRecord]]:
    inquiries: list[Inquiry] = []
    quotes: list[Quote] = []
    feedbacks: list[MatchFeedback] = []
    records: list[MatchRecord] = []
    alternate_suppliers = [
        "supplier_connector",
        "supplier_quality",
        "supplier_logistics",
        "supplier_software",
        "supplier_fastener",
        "supplier_plating",
    ]

    for idx, (buyer_key, supplier_key, product_name, qty, unit, status, score) in enumerate(INQUIRY_SPECS, start=1):
        buyer = enterprises[buyer_key]
        supplier = enterprises[supplier_key]
        product = products[product_name]
        feedback = MatchFeedback(
            buyer_id=buyer.id,
            supplier_id=supplier.id,
            product_name=product_name,
            clicked=True,
            contacted=idx % 4 != 0,
            status="converted" if status in {"contracted", "fulfilled"} else "contacted",
            blockchain_evidence_hash=f"demo-hash-{idx:04d}",
            rl_reward_applied=status in {"contracted", "fulfilled"},
            dim_scores={
                "product": round(score + 0.02, 2),
                "distance": round(0.72 + (idx % 4) * 0.04, 2),
                "capacity": round(0.76 + (idx % 5) * 0.03, 2),
                "credit": round(supplier.credit_score / 100, 2),
                "green": round(0.65 + (idx % 3) * 0.08, 2),
            },
            match_score=score,
            session_id=f"demo-session-{idx:02d}",
            ip_address="127.0.0.1",
            user_agent="ChainYiPeiDemoSeeder",
            created_at=_dt(idx),
        )
        db.session.add(feedback)
        db.session.flush()

        inquiry = Inquiry(
            poster_id=buyer.id,
            direction="demand",
            buyer_id=buyer.id,
            seller_id=supplier.id,
            product_id=product.id,
            product_name=product_name,
            quantity=qty,
            unit=unit,
            description=f"{buyer.name}采购{product_name}，要求供应商具备稳定交付、质量追溯和数据授权能力。",
            content=f"交付窗口：{14 + idx}天；验收要求：IATF16949/批次追溯；付款方式：验收后30天。",
            status=status,
            match_feedback_id=feedback.id,
            match_context={
                "demo_dataset": DEMO_MARK,
                "match_score": score,
                "recommended_supplier": supplier.name,
                "dim_scores": feedback.dim_scores,
            },
            is_group_buy=idx in {3, 9, 13},
            group_members=[
                {"enterprise_id": buyer.id, "quantity": qty, "joined_at": _dt(idx).isoformat()}
            ] if idx in {3, 9, 13} else [],
            created_at=_dt(idx + 1),
            updated_at=_dt(idx),
        )
        db.session.add(inquiry)
        db.session.flush()
        inquiries.append(inquiry)
        feedbacks.append(feedback)

        record = MatchRecord(
            buyer_id=buyer.id,
            seller_id=supplier.id,
            product_name=product_name,
            match_score=score,
            dim_scores=feedback.dim_scores,
            match_feedback_id=feedback.id,
            status="contracted" if status in {"contracted", "fulfilled"} else ("quoted" if status == "quoted" else "matched"),
            session_id=feedback.session_id,
            created_at=_dt(idx + 1),
            updated_at=_dt(idx),
        )
        db.session.add(record)
        db.session.flush()
        records.append(record)

        supplier_quote = Quote(
            inquiry_id=inquiry.id,
            supplier_id=supplier.id,
            product_name=product_name,
            price=round((100 + idx * 19) * (1 if unit not in {"吨", "千米"} else 100), 2),
            quantity=qty,
            unit=unit,
            delivery_days=12 + idx % 8,
            remarks=f"主推方案：{supplier.name}可按周排产，支持批次追溯和发票验真。",
            status="accepted" if status in {"contracted", "fulfilled"} else "active",
            created_at=_dt(idx),
        )
        db.session.add(supplier_quote)
        quotes.append(supplier_quote)

        alt_key = alternate_suppliers[idx % len(alternate_suppliers)]
        alt = enterprises[alt_key]
        alt_quote = Quote(
            inquiry_id=inquiry.id,
            supplier_id=alt.id,
            product_name=product_name,
            price=round(supplier_quote.price * (1.04 + (idx % 3) * 0.03), 2),
            quantity=max(int(qty * 0.7), 1),
            unit=unit,
            delivery_days=18 + idx % 10,
            remarks=f"备选方案：{alt.name}可部分供货，适合作为风险兜底供应商。",
            status="active",
            created_at=_dt(idx, 4),
        )
        db.session.add(alt_quote)
        quotes.append(alt_quote)

    db.session.commit()
    return inquiries, quotes, feedbacks, records


def _make_transactions(
    enterprises: dict[str, Enterprise],
    inquiries: list[Inquiry],
) -> list[Transaction]:
    completed = [inq for inq in inquiries if inq.status in {"contracted", "fulfilled"}][:8]
    transactions: list[Transaction] = []
    for idx, inq in enumerate(completed, start=1):
        seller_id = inq.seller_id or enterprises["supplier_logistics"].id
        amount = round((inq.quantity or 1) * (128 + idx * 23.5), 2)
        tx = Transaction(
            buyer_id=inq.buyer_id or inq.poster_id,
            seller_id=seller_id,
            product_name=inq.product_name,
            quantity=inq.quantity,
            price=amount,
            status="completed",
            match_code=Transaction.generate_match_code(inq.buyer_id or inq.poster_id, seller_id, f"DEMO-C-{idx:03d}"),
            invoice_info={
                "invoice_no": f"DEMO2026{idx:06d}",
                "invoice_amount": amount,
                "invoice_date": (_dt(idx + 4).date()).isoformat(),
                "delivery_date": (_dt(idx).date()).isoformat(),
                "on_time": idx != 5,
                "quality_rating": [5, 5, 4, 5, 3, 4, 5, 4][idx - 1],
                "verified": True,
                "contract_id": f"DEMO-CONTRACT-{idx:03d}",
                "amount_range": "50万-300万" if amount > 500000 else "10万-50万",
                "valid_until": (_dt(-90).date()).isoformat(),
                "order_no": f"LYP-DEMO-ORDER-{idx:04d}",
                "customer_name": db.session.get(Enterprise, inq.buyer_id or inq.poster_id).name,
                "qc_status": "passed" if idx != 5 else "conditional_pass",
                "payment_progress": [100, 100, 80, 100, 65, 90, 100, 85][idx - 1],
                "demo_dataset": DEMO_MARK,
            },
            fulfillment_status="verified" if idx not in {5, 8} else "delivered",
            inquiry_id=inq.id,
            created_at=_dt(idx * 3),
        )
        db.session.add(tx)
        transactions.append(tx)
    db.session.commit()
    return transactions


def _make_chats_intents_cards(
    records: list[MatchRecord],
) -> tuple[list[InquiryChat], list[ChatMessage], list[IntentQuote], list[BusinessCard]]:
    chats: list[InquiryChat] = []
    messages: list[ChatMessage] = []
    quotes: list[IntentQuote] = []
    cards: list[BusinessCard] = []
    for idx, record in enumerate(records[:8], start=1):
        chat = InquiryChat(
            match_record_id=record.id,
            buyer_id=record.buyer_id,
            seller_id=record.seller_id,
            mode="procurement" if idx % 2 else "sales",
            is_anonymous=idx in {3, 7},
            status="quoted" if idx <= 6 else "active",
            created_at=_dt(idx + 2),
            updated_at=_dt(idx),
        )
        db.session.add(chat)
        db.session.flush()
        chats.append(chat)

        content_rows = [
            (record.buyer_id, f"我们需要确认{record.product_name}的月度交付能力和质检报告。", "text", {}),
            (record.seller_id, "可提供近三个月良率、产能负荷和发票验真记录，支持分批交付。", "text", {}),
            (None, f"链小易建议：该供应商匹配度 {record.match_score:.0%}，可进入意向报价。", "ai_suggestion", {"match_score": record.match_score}),
            (record.seller_id, "报价方案已提交：含税价、交期、付款条件见结构化报价。", "quote_proposal", {"price": 128 + idx * 23, "quantity": 1000 + idx * 100, "unit": "件", "delivery_days": 14 + idx}),
        ]
        for offset, (sender_id, content, msg_type, metadata) in enumerate(content_rows):
            msg = ChatMessage(
                chat_id=chat.id,
                sender_id=sender_id,
                content=content,
                message_type=msg_type,
                msg_metadata={**metadata, "demo_dataset": DEMO_MARK},
                created_at=_dt(idx, offset),
            )
            db.session.add(msg)
            messages.append(msg)

        if idx <= 6:
            intent = IntentQuote(
                chat_id=chat.id,
                buyer_id=record.buyer_id,
                seller_id=record.seller_id,
                match_record_id=record.id,
                product_name=record.product_name,
                quantity=800 + idx * 220,
                unit="件",
                target_price=round(110 + idx * 17.5, 2),
                budget_range=f"{100 + idx * 10}-{150 + idx * 12}",
                ai_suggested_price=round(118 + idx * 16.8, 2),
                ai_price_basis="结合近30天平台报价、供应商信用分、交期和历史履约表现估算。",
                ai_delivery_estimate=f"{12 + idx}-{18 + idx}天",
                status="accepted" if idx <= 4 else ("pending" if idx == 5 else "rejected"),
                buyer_confirmed=idx <= 5,
                seller_confirmed=idx <= 4,
                seller_reply_price=round(116 + idx * 16.2, 2) if idx <= 5 else None,
                seller_reply_notes="接受意向报价，可锁定两周产能。" if idx <= 4 else "需重新确认原材料排期。",
                created_at=_dt(idx + 1),
                updated_at=_dt(idx),
                expires_at=_dt(-7),
            )
            db.session.add(intent)
            db.session.flush()
            quotes.append(intent)
            if idx <= 4:
                card = BusinessCard(
                    initiator_id=record.buyer_id,
                    recipient_id=record.seller_id,
                    intent_quote_id=intent.id,
                    status="completed",
                    created_at=_dt(idx),
                )
                db.session.add(card)
                cards.append(card)
    db.session.commit()
    return chats, messages, quotes, cards


def _make_favorites(enterprises: dict[str, Enterprise]) -> list[FavoriteSupplier]:
    pairs = [
        ("buyer_ev", "supplier_harness", "车规级高压线束", 0.95),
        ("buyer_ev", "supplier_battery", "磷酸铁锂电池模组", 0.91),
        ("buyer_ev", "supplier_connector", "高速防水连接器", 0.86),
        ("buyer_robot", "supplier_reducer", "RV减速机", 0.94),
        ("buyer_robot", "supplier_bearing", "机器人关节轴承", 0.9),
        ("buyer_storage", "supplier_heat", "电池液冷板", 0.88),
        ("buyer_storage", "supplier_material", "动力电池结构胶", 0.82),
        ("buyer_chip", "supplier_pcb", "六层HDI控制板", 0.9),
        ("buyer_rail", "supplier_sensor", "轨交制动传感器", 0.83),
        ("buyer_pack", "supplier_optics", "AOI视觉检测设备", 0.93),
    ]
    rows: list[FavoriteSupplier] = []
    for buyer_key, supplier_key, product_name, score in pairs:
        fav = FavoriteSupplier(
            collector_id=enterprises[buyer_key].id,
            supplier_id=enterprises[supplier_key].id,
            product_name=product_name,
            match_score=score,
            notes=f"演示收藏：{product_name}首选供应商，适合快速询价和风险兜底。",
            created_at=_dt(len(rows)),
        )
        db.session.add(fav)
        rows.append(fav)
    db.session.commit()
    return rows


def _workflow(assigned_to: int, assigned_by: int, status: str, note: str = "") -> list[dict[str, Any]]:
    now = _dt(1).isoformat()
    return [
        {
            "assigned_to": assigned_to,
            "assigned_by": assigned_by,
            "assigned_at": now,
            "status": status,
            "handling_notes": note if status == "completed" else None,
            "evidence_urls": ["/demo/evidence/supplier-risk-review.pdf"] if status == "completed" else [],
            "completed_at": _dt(0).isoformat() if status == "completed" else None,
            "reviewed_by": assigned_by if status == "completed" else None,
            "review_result": "approved" if status == "completed" else None,
            "review_notes": "演示数据：处置结果已通过审核" if status == "completed" else None,
        }
    ]


ALERT_SPECS = [
    ("车规IGBT功率模块", "red", "import_risk", "进口依赖度升高，重庆功率模块供应出现排产拥堵", 0.91, "建议立即启动双供应商替代和省外协同采购。"),
    ("车规级高压线束", "red", "supplier_count", "高压线束本地可用供应商低于3家，整车交付存在延期风险", 0.88, "建议派发给产业链专班核实锦城线束产能，并准备资阳航电兜底。"),
    ("RV减速机", "red", "capacity", "机器人减速机产能利用率超过92%，未来两周交付排队", 0.86, "建议引入第二供应商并跟进德阳重装扩产计划。"),
    ("电池液冷板", "yellow", "capacity", "热管理件订单集中释放，南充热控产能利用率偏高", 0.66, "建议提前锁定排产窗口。"),
    ("六层HDI控制板", "yellow", "quality", "近期两批PCBA返修率高于平台均值", 0.58, "建议要求供应商提交AOI检测报告。"),
    ("轨交制动传感器", "yellow", "supplier_count", "轨交制动传感器本地供应商偏少", 0.61, "建议进行招商补链。"),
    ("磷酸铁锂电池模组", "blue", "price", "近30天报价小幅波动", 0.32, "建议继续观察。"),
    ("车规压力传感器", "blue", "data_freshness", "供应商电力数据两天未同步", 0.28, "建议提醒企业重新授权。"),
    ("AOI视觉检测设备", "yellow", "delivery", "检测设备交期延长至45天", 0.62, "建议采购方提前确认安装窗口。"),
    ("高压屏蔽电缆", "yellow", "interprovincial", "跨省运输受天气影响，电缆交付有延迟风险", 0.57, "建议启用成都陆港备用线路。"),
    ("动力电池结构胶", "blue", "price", "化工材料价格小幅上行", 0.35, "建议批量采购锁价。"),
    ("机器人关节轴承", "red", "quality", "关节轴承良率波动，影响机器人本体装配节拍", 0.84, "建议质量检测中心介入复核。"),
    ("高速防水连接器", "yellow", "capacity", "连接器端子排产趋紧", 0.55, "建议安排安全库存。"),
    ("供应链质量追溯平台", "blue", "data_auth", "部分供应商追溯数据授权未完成", 0.25, "建议管理员发起数据授权提醒。"),
]


def _make_alerts_tasks_messages(
    enterprises: dict[str, Enterprise],
) -> tuple[list[Alert], list[RecruitmentTask], list[Message]]:
    gov = enterprises["gov"]
    admin = enterprises["admin"]
    alerts: list[Alert] = []
    for idx, (product_name, level, dimension, message, severity, suggestion) in enumerate(ALERT_SPECS, start=1):
        status = "pending" if idx in {1, 2, 3, 12} else ("completed" if idx in {4, 5, 10} else "processing")
        alert = Alert(
            product_name=product_name,
            message=message,
            level=level,
            dimension=dimension,
            is_active=level in {"red", "yellow"},
            suggestion=suggestion,
            alert_type="supply_chain_risk",
            severity_score=severity,
            auto_pushed=level == "red",
            workflow_history=_workflow(gov.id, admin.id, status, "已联系企业补充产能与质检材料。"),
            analysis_data={
                "risk_reason": message,
                "impact_scope": "新能源汽车、机器人、储能装备重点产业链" if level == "red" else "局部订单履约与供应稳定性",
                "ai_suggestions": [
                    suggestion,
                    "通过 Hermes 微信查询详情后，可先预览派发动作，再回复确认执行。",
                    "同步关注供应商信用分、产能利用率和近30天报价波动。",
                ],
                "data_source_info": {
                    "name": "链易配演示监测模型",
                    "node_id": f"demo-alert-{idx:03d}",
                    "last_sync": _dt(idx % 3).isoformat(),
                },
                "historical_trend": [round(severity * 100 - n * 2 + (idx % 3), 1) for n in range(7)],
                "demo_dataset": DEMO_MARK,
            },
            created_at=_dt(idx),
        )
        db.session.add(alert)
        alerts.append(alert)
    db.session.commit()

    tasks_specs = [
        ("车规IGBT功率模块补链任务", "车规IGBT功率模块", "重庆西永功率半导体有限公司", "重庆", "high", "pending"),
        ("高压线束第二供应商培育", "车规级高压线束", "资阳航电电缆有限公司", "资阳", "high", "processing"),
        ("机器人减速机扩产跟进", "RV减速机", "德阳重装减速机有限公司", "德阳", "normal", "processing"),
        ("轨交制动传感器招商", "轨交制动传感器", "绵阳科测传感器有限公司", "绵阳", "normal", "pending"),
        ("液冷板产能保障", "电池液冷板", "南充热控科技有限公司", "南充", "normal", "signed"),
        ("质量检测公共服务对接", "机器人关节轴承", "成都计量检测认证中心有限公司", "成都", "high", "pending"),
    ]
    tasks: list[RecruitmentTask] = []
    for idx, (task_name, product, target_name, location, priority, status) in enumerate(tasks_specs, start=1):
        task = RecruitmentTask(
            task_name=task_name,
            target_product=product,
            target_enterprise_name=target_name,
            target_enterprise_location=location,
            assigned_to=gov.id,
            assigned_by=admin.id,
            priority=priority,
            status=status,
            progress_notes=f"演示任务：已完成第{idx}轮企业画像核验，待跟进产能和政策诉求。",
            deadline=date.today() + timedelta(days=7 + idx * 3),
            created_at=_dt(idx + 2),
            updated_at=_dt(idx),
        )
        db.session.add(task)
        tasks.append(task)
    db.session.commit()

    recipients = [
        enterprises["buyer_ev"],
        enterprises["buyer_robot"],
        enterprises["buyer_storage"],
        enterprises["buyer_chip"],
        enterprises["supplier_harness"],
        enterprises["supplier_battery"],
        enterprises["supplier_pcb"],
        gov,
    ]
    messages: list[Message] = []
    for idx in range(32):
        recipient = recipients[idx % len(recipients)]
        sender = admin if idx % 5 == 0 else None
        msg_type = ["alert", "quote", "fulfillment", "system"][idx % 4]
        msg = Message(
            sender_id=sender.id if sender else None,
            recipient_id=recipient.id,
            message_type=msg_type,
            title=f"【演示】{['风险预警', '报价更新', '履约回流', '系统提醒'][idx % 4]} #{idx + 1}",
            content=(
                "这是一条链易配完整演示数据，用于展示站内消息、微信提醒、"
                "报价、履约、风险处置等页面状态。"
            ),
            link_url="/dashboard/alert-center" if msg_type == "alert" else "/sales",
            is_read=idx % 3 == 0,
            priority="high" if msg_type == "alert" and idx % 2 == 0 else "normal",
            mode="procurement" if idx % 2 == 0 else "sales",
            created_at=_dt(idx % 9, idx % 5),
            read_at=_dt(idx % 4) if idx % 3 == 0 else None,
        )
        db.session.add(msg)
        messages.append(msg)
    db.session.commit()
    return alerts, tasks, messages


def _summary() -> dict[str, int]:
    demo_ids = [
        row[0]
        for row in db.session.query(Enterprise.id)
        .filter(Enterprise.name.in_(DEMO_ENTERPRISE_NAMES))
        .all()
    ]
    product_ids = [
        row[0]
        for row in db.session.query(Product.id)
        .filter(Product.enterprise_id.in_(demo_ids))
        .all()
    ] if demo_ids else []
    inquiry_ids = [
        row[0]
        for row in db.session.query(Inquiry.id)
        .filter(or_(Inquiry.poster_id.in_(demo_ids), Inquiry.buyer_id.in_(demo_ids), Inquiry.seller_id.in_(demo_ids)))
        .all()
    ] if demo_ids else []
    chat_ids = [
        row[0]
        for row in db.session.query(InquiryChat.id)
        .filter(or_(InquiryChat.buyer_id.in_(demo_ids), InquiryChat.seller_id.in_(demo_ids)))
        .all()
    ] if demo_ids else []
    alert_ids = [
        row[0]
        for row in db.session.query(Alert.id)
        .filter(Alert.product_name.in_(DEMO_PRODUCT_NAMES))
        .all()
    ]
    return {
        "enterprises": Enterprise.query.filter(Enterprise.name.in_(DEMO_ENTERPRISE_NAMES)).count(),
        "products": Product.query.filter(Product.enterprise_id.in_(demo_ids)).count() if demo_ids else 0,
        "inquiries": Inquiry.query.filter(Inquiry.id.in_(inquiry_ids)).count() if inquiry_ids else 0,
        "quotes": Quote.query.filter(Quote.inquiry_id.in_(inquiry_ids)).count() if inquiry_ids else 0,
        "transactions": Transaction.query.filter(or_(Transaction.buyer_id.in_(demo_ids), Transaction.seller_id.in_(demo_ids))).count() if demo_ids else 0,
        "match_feedbacks": MatchFeedback.query.filter(or_(MatchFeedback.buyer_id.in_(demo_ids), MatchFeedback.supplier_id.in_(demo_ids))).count() if demo_ids else 0,
        "match_records": MatchRecord.query.filter(or_(MatchRecord.buyer_id.in_(demo_ids), MatchRecord.seller_id.in_(demo_ids))).count() if demo_ids else 0,
        "inquiry_chats": InquiryChat.query.filter(InquiryChat.id.in_(chat_ids)).count() if chat_ids else 0,
        "chat_messages": ChatMessage.query.filter(ChatMessage.chat_id.in_(chat_ids)).count() if chat_ids else 0,
        "intent_quotes": IntentQuote.query.filter(or_(IntentQuote.buyer_id.in_(demo_ids), IntentQuote.seller_id.in_(demo_ids))).count() if demo_ids else 0,
        "business_cards": BusinessCard.query.filter(or_(BusinessCard.initiator_id.in_(demo_ids), BusinessCard.recipient_id.in_(demo_ids))).count() if demo_ids else 0,
        "favorite_suppliers": FavoriteSupplier.query.filter(or_(FavoriteSupplier.collector_id.in_(demo_ids), FavoriteSupplier.supplier_id.in_(demo_ids))).count() if demo_ids else 0,
        "recruitment_tasks": RecruitmentTask.query.filter(RecruitmentTask.target_product.in_(DEMO_PRODUCT_NAMES)).count(),
        "alerts": Alert.query.filter(Alert.id.in_(alert_ids)).count() if alert_ids else 0,
        "messages": Message.query.filter(or_(Message.sender_id.in_(demo_ids), Message.recipient_id.in_(demo_ids))).count() if demo_ids else 0,
        "price_indices": PriceIndex.query.filter(PriceIndex.product_name.in_(DEMO_PRODUCT_NAMES)).count(),
    }


def seed_demo_data(app=None) -> dict[str, int]:
    if app is None:
        from app import create_app

        app = create_app()

    with app.app_context():
        db.create_all()
        reset_demo_data()
        enterprises = _make_enterprises()
        products = _make_products(enterprises)
        _make_price_indices()
        inquiries, _quotes, _feedbacks, records = _make_inquiries_quotes_matches(enterprises, products)
        _make_transactions(enterprises, inquiries)
        _make_chats_intents_cards(records)
        _make_favorites(enterprises)
        _make_alerts_tasks_messages(enterprises)
        return _summary()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed complete ChainYiPei demo data.")
    parser.add_argument("--json", action="store_true", help="Print summary as JSON.")
    args = parser.parse_args()

    from app import create_app

    app = create_app()
    summary = seed_demo_data(app)
    if args.json:
        import json

        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    print("=" * 56)
    print("链易配完整功能演示数据已刷新")
    print("=" * 56)
    for key, value in summary.items():
        print(f"{key:18s} {value}")
    print("-" * 56)
    print(f"演示账号统一密码：{DEMO_PASSWORD}")
    print("采购方示例：成都星河新能源汽车有限公司 / 123456")
    print("政府端示例：成都市产业链协同专班 / 123456")
    print("管理端示例：链易配运营中心 / 123456")


if __name__ == "__main__":
    main()
