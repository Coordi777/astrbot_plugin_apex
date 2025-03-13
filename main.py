from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.message_components import *

from datetime import datetime, time, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import os
import pytz
import requests
import sys
sys.path.append("/remote-home/bxy/AstrBot/data/plugins/astrbot_plugin_apex")

from scheduler import Scheduler, get_time

URL_PLAYER = "https://api.mozambiquehe.re/bridge"
URL_PRO = "https://api.mozambiquehe.re/predator"
URL_MAP = "https://api.mozambiquehe.re/maprotation"
API_KEY = "YOUR_API_KEY"

@register("apex", "Coordi", "Apex功能插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

        logger.info("Apex插件初始化...")
        self.scheduler = Scheduler(context)
        logger.info("Apex定时任务...")
        self.scheduler.start()

        self.scheduler.update_task_queue()
        logger.info("Apex定时任务初始化完成")

    
    @filter.command("apexmap")
    async def apexmap(self, event: AstrMessageEvent):
        '''查询Apex地图轮换信息''' 
        params = {
            "auth": API_KEY,
            "version":2
            }
        try:
            response = requests.get(URL_MAP, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            logger.info("请求成功，响应数据")
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败: {e}")
        except json.JSONDecodeError:
            logger.error("错误：响应内容不是有效的 JSON")

        chain = [Plain("Hi,"),
                 At(qq=event.get_sender_id()),
                 Plain("当前地图信息:\n"),
                 Plain("=== Battle Royale ===\n"),
                 Plain(f"当前地图: {data['battle_royale']['current']['map']}\n"),
                 Image.fromURL(f"{data['battle_royale']['current']['asset']}"),
                 Plain(f"剩余时间: {data['battle_royale']['current']['remainingTimer']}\n下一张地图: {data['battle_royale']['next']['map']}\n"),
                 Plain("=== Ranked 排位赛 ===\n"),
                 Plain(f"当前地图: {data['ranked']['current']['map']}\n"),
                 Image.fromURL(f"{data['ranked']['current']['asset']}"),
                 Plain(f"剩余时间: {data['ranked']['current']['remainingTimer']}\n下一张地图: {data['ranked']['next']['map']}\n"),
                 Plain("=== Ranked LTM（限时模式） ===\n"),
                 Plain(f"当前地图: {data['ltm']['current']['map']}\n"),
                 Image.fromURL(f"{data['ltm']['current']['asset']}"),
                 Plain(f"剩余时间: {data['ltm']['current']['remainingTimer']}\n下一张地图: {data['ltm']['next']['map']}\n"),
                 ]
        yield event.chain_result(chain)
    
    @filter.command("apexpro")
    async def apexpro(self, event: AstrMessageEvent):
        '''查询Apex PC端猎杀者人数''' 
        params = {
            "auth": API_KEY
            }
        beijing_tz = pytz.timezone("Asia/Shanghai")
        try:
            response = requests.get(URL_PRO, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            logger.info("请求成功，响应数据")
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败: {e}")
        except json.JSONDecodeError:
            logger.error("错误：响应内容不是有效的 JSON")
        user_name = event.get_sender_name()
        message = f"""Hi,{user_name}!\n当前PC端已经有{data['RP']["PC"]["foundRank"]}位猎杀了哦。你需要至少达到{data['RP']["PC"]["val"]}分才能成为猎杀。\n顺便一提,PC已经有{data['RP']["PC"]["totalMastersAndPreds"]}大师段位的玩家了，加油上分吧！\n更新时间: {datetime.fromtimestamp(data['RP']["PC"]["updateTimestamp"], tz=beijing_tz).strftime("%Y-%m-%d %H:%M:%S")}"""

        yield event.plain_result(message)

    @filter.command("apexuser")
    async def apexuser(self, event: AstrMessageEvent, player_name:str, platform="PC"):
        '''查询Apex PC端猎杀者人数''' 
        params = {
                "auth": API_KEY,
                "player": player_name,
                "platform": platform
                }
        try:
            response = requests.get(URL_PLAYER, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            logger.info("请求成功，响应数据")
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败: {e}")
        except json.JSONDecodeError:
            logger.error("错误：响应内容不是有效的 JSON")
        chain = [
            Plain("Hi, "),
            At(qq=event.get_sender_id()),
            Plain(f"!\n🎮 EA用户 {player_name} 的 APEX 信息如下（中文ID可能无法显示）:\n"),
            Plain(f"  ID: [{data['global']['tag']}]{data['global']['name']}\n"),
            Plain(f"  UID: {data['global']['uid']}\n\n"),
            Plain("⭐️ 等级与排位:\n"),
            Plain(f"  - 等级: {data['global']['level']}\n"),
            Plain(f"  - 🏆 段位: {data['global']['rank']['rankName']} {data['global']['rank']['rankDiv']}\n"),
            Plain(f"  - 🎯 分数: {data['global']['rank']['rankScore']}\n\n"),
            Plain("🕹️ 当前状态:\n"),
            Plain(f"  - 状态: {data['realtime']['currentStateAsText']}\n"),
            Plain(f"  - 已选传奇: {data['realtime']['selectedLegend']}\n\n"),
            Plain("📊 生涯统计:\n"),
            Plain(f"  - 🔫 总击杀: {data['total']['career_kills']['value']}\n"),
            Plain(f"  - 🆘 总救援: {data['total']['career_revives']['value']}\n"),
            Plain(f"  - 🏅 总胜利: {data['total']['career_wins']['value']}\n"),
            Plain(f"  - 🎯 生涯KD: {data['total']['kd']['value']}")
            ]
        yield event.chain_result(chain)
       


    def normalize_session_id(self, event: AstrMessageEvent) -> str:
        """标准化会话ID,确保格式一致"""
        try:
            target = event.unified_msg_origin
            return target
        except Exception as e:
            logger.error(f"标准化会话ID时出错: {str(e)}")
            return event.unified_msg_origin  # 返回原始ID作为后备

    @filter.command("apexclock")
    async def apexclock(self, event: AstrMessageEvent, cus_time=None):
        target = self.normalize_session_id(event)
        self.scheduler.group_settings[target] = {}
        if cus_time is None:
            cus_time = "20:30"
        try:
            hour,minute = map(int, cus_time.split(':'))
        except ValueError:
            yield event.make_result().message("时间格式错误,请使用HH:MM格式")
            
        self.scheduler.group_settings[target]['cus_time'] = cus_time
        now = get_time()
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target_time <= now:
            target_time += timedelta(days=1)

        if hasattr(self, 'scheduler') and self.scheduler:
            self.scheduler.update_task_queue()
            logger.info("Apex定时任务更新")
            self.scheduler.wakeup_event.set()

    async def terminate(self):
        '''可选择实现 terminate 函数，当插件被卸载/停用时会调用。'''
