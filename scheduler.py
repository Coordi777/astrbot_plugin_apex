import asyncio
from astrbot.api.message_components import *

from datetime import datetime, time, timedelta, timezone
import heapq
from astrbot.api import logger
import traceback
from astrbot.api.event import MessageChain
from typing import List, Tuple, Optional
from functools import wraps

def get_time():
    SHA_TZ = timezone(timedelta(hours=8), name='Asia/Shanghai')
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    current_datetime = utc_now.astimezone(SHA_TZ)

    return current_datetime


def scheduler_error_handler(func):
    """调度器错误处理装饰器"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"{func.__name__} 执行出错: {str(e)}")
            logger.error(traceback.format_exc())
            # 出错后等待一段时间再继续
            await asyncio.sleep(60)
            return None
    return wrapper

class Scheduler:
    def __init__(self, context):
        self.context = context
        self.task_queue: List[Tuple[datetime, str]] = []
        self.wakeup_event = asyncio.Event()
        self.scheduled_task_ref: Optional[asyncio.Task] = None
        self.group_settings = {}
        
    def update_task_queue(self, ) -> None:
        """更新任务队列"""
        self.task_queue = []
        
        now = get_time()
        for target, settings in self.group_settings.items():
            try:
                # 检查是否有自定义时间设置
                if not isinstance(settings, dict) or 'cus_time' not in settings:
                    continue
                    
                # 解析时间设置
                time_str = settings['cus_time']
                try:
                    hour, minute = map(int, time_str.split(':'))
                except ValueError:
                    logger.error(f"无效的时间格式: {time_str}")
                    continue
                
                # 计算今天的执行时间点
                today_exec_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # 如果今天的时间已经过去，调整到明天
                if today_exec_time <= now:
                    today_exec_time = (now + timedelta(days=1)).replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )
                
                # 添加到优先队列
                heapq.heappush(self.task_queue, (today_exec_time, target))
            except ValueError as e:
                logger.error(f"解析群 {target} 的时间设置出错: {str(e)}")
            except Exception as e:
                logger.error(f"处理群 {target} 的任务时出错: {str(e)}")
                logger.error(traceback.format_exc())
    
    def normalize_session_id(self, target: str) -> str:
        """标准化会话ID格式"""
        try:
            # 如果不包含 FriendMessage，添加它
            if ':FriendMessage:' not in target:
                parts = target.split('!')
                if len(parts) == 3:  # webchat!astrbot!uuid 格式
                    target = f"webchat:FriendMessage:{target}"
            return target
        except Exception as e:
            logger.error(f"标准化会话ID时出错: {str(e)}")
            return target  # 返回原始ID作为后备

    @scheduler_error_handler
    async def _execute_task(self, target: str, scheduled_time: datetime) -> None:
        """执行定时任务"""
        now = get_time()
        
        normalized_target = self.normalize_session_id(target)
        if normalized_target not in self.group_settings:
            return
            
        settings = self.group_settings[normalized_target]
        if not isinstance(settings, dict) or 'cus_time' not in settings:
            return
        
        current_datetime = get_time().strftime("%Y-%m-%d %H:%M")

        # 创建消息段列表
        from astrbot.api.message_components import Plain
        message_segments = [

            Plain(f" 现在是北京时间{current_datetime},是时候启动Apex啦!")
        ]
        
        # 使用send_message发送消息
        from astrbot.api.event import MessageChain
        message_chain = MessageChain(message_segments)
        
        try:
            await self.context.send_message(normalized_target, message_chain)
            logger.info(f"向 {normalized_target} 发送Apex提醒成功")
        except Exception as e:
            logger.error(f"向 {normalized_target} 发送消息失败：{str(e)}")
            logger.error(traceback.format_exc())
            return
        
        # 计算下一次执行时间
        try:
            hour, minute = map(int, settings['cus_time'].split(':'))
            next_time = (now + timedelta(days=1)).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            
            # 更新任务队列
            for i, (time, task_target) in enumerate(self.task_queue):
                if self.normalize_session_id(task_target) == normalized_target:
                    self.task_queue[i] = (next_time, task_target)
                    heapq.heapify(self.task_queue)
                    break
            message_segments = [
                At(qq="598103911"),
                Plain(f" 提醒发送成功啦，下一次提醒时间是{next_time}哦!")]
            message_chain = MessageChain(message_segments)
            await self.context.send_message(normalized_target, message_chain)
        except Exception as e:
            logger.error(f"更新下一次执行时间失败: {str(e)}")
            logger.error(traceback.format_exc())


    @scheduler_error_handler
    async def scheduled_task(self) -> None:
        """定时任务主循环"""
        while True:
            try:
                # 如果任务队列为空，等待唤醒
                if not self.task_queue:
                    logger.info("任务队列为空，等待唤醒")
                    self.wakeup_event.clear()
                    await self.wakeup_event.wait()
                    continue
                
                # 获取下一个任务
                next_time, target = self.task_queue[0]
                
                # 计算等待时间
                now = get_time()
                if next_time > now:
                    wait_seconds = (next_time - now).total_seconds()
                    
                    # 设置唤醒事件的超时
                    try:
                        # 等待唤醒事件或超时
                        await asyncio.wait_for(self.wakeup_event.wait(), timeout=wait_seconds)
                        
                        # 如果被唤醒，重新计算任务
                        self.wakeup_event.clear()
                        continue
                    except asyncio.TimeoutError:
                        # 超时，执行任务
                        pass
                
                # 弹出当前任务
                # next_time, target = heapq.heappop(self.task_queue)
                
                # 执行任务
                await self._execute_task(target, next_time)
                
            except asyncio.CancelledError:
                # 任务被取消
                logger.info("定时任务被取消")
                break
            except Exception as e:
                logger.error(f"定时任务循环出错: {str(e)}")
                logger.error(traceback.format_exc())
                # 出错后等待一段时间再继续
                await asyncio.sleep(60)

    def start(self) -> None:
        """启动定时任务"""
        if not self.scheduled_task_ref:
            logger.info("创建定时任务...")
            self.scheduled_task_ref = asyncio.get_event_loop().create_task(self.scheduled_task())
            logger.info("定时任务创建成功")
        else:
            logger.info("定时任务已经在运行中")
            
    async def stop(self) -> None:
        """停止定时任务"""
        if self.scheduled_task_ref:
            self.scheduled_task_ref.cancel()
            self.scheduled_task_ref = None 

    def remove_task(self, target: str) -> bool:
        """从任务队列中删除特定目标的任务
        
        Args:
            target: 目标会话ID
            
        Returns:
            bool: 是否成功删除任务
        """
        try:
            # 标准化目标ID
            normalized_target = self.normalize_session_id(target)
            
            # 创建新的任务队列，排除指定目标的任务
            new_queue = []
            removed = False
            
            # 遍历当前任务队列
            while self.task_queue:
                task = heapq.heappop(self.task_queue)
                time, task_target = task
                
                # 如果不是要删除的目标，则保留
                if self.normalize_session_id(task_target) != normalized_target:
                    new_queue.append(task)
                else:
                    removed = True
            
            # 重建任务队列
            self.task_queue = []
            for task in new_queue:
                heapq.heappush(self.task_queue, task)
                
            return removed
        except Exception as e:
            logger.error(f"删除任务时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return False 