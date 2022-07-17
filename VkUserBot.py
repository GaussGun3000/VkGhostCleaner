"""
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
"""
import time

import PySimpleGUI

from rls import RateLimitingSemaphore
from vkbottle import API
from vkbottle import VKAPIError
import asyncio
from ExcelWriter import dump_users


def read_token():
    try:
        with open(file="token.txt", mode='r') as file:
            return file.read()
    except FileNotFoundError:
        return None


class MyAPI(API):
    """Own API class implementation with request method overloaded to limit RPS"""
    def __init__(self, token:  str, limit: int = 3):
        super().__init__(token)
        self.sema = RateLimitingSemaphore(limit)
        self.requests = 0

    async def request(self, method: str, data: dict) -> dict:
        """Makes a single request opening a session (overload)"""
        async with self.sema:
            data = await self.validate_request(data)

            async with self.token_generator as token:
                response = await self.http_client.request_text(
                    self.API_URL + method,
                    method="POST",
                    data=data,  # type: ignore
                    params={"access_token": token, "v": self.API_VERSION},
                    )
            self.requests += 1
            return await self.validate_response(method, data, response)  # type: ignore

    def set_sema(self, limit: int):
        """
        :param limit: new max RPS
        :return: None

        Sets new max RPS
        """
        self.sema = RateLimitingSemaphore(limit)


class VkUserBot:
    def __init__(self, logger):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.logger = logger
        self.group = None
        self.inactive = None
        token = read_token()
        self.api = MyAPI(token=token)
        if token:
            self.logger.log("vk_api initialized")
        else:
            self.logger.log("no token for vk_api")

    def login(self):
        pass

    def set_group(self, group: str):
        self.group = group
        pass

    def find_inactive(self, amount: int, window: PySimpleGUI.Window, rps: int = 3) -> set:
        """
        :param window:
        :param amount: amount of posts to search through
        :param rps: RPS limit
        :return: list of IDs of inactive people
        Create a list of people inactive on last *amount* posts"""
        self.logger.log(f'Searching for inactive users with rps={rps}')
        self.api.requests = 0
        self.api.set_sema(limit=rps)
        loop = asyncio.get_event_loop()
        inactive = loop.run_until_complete(self.gather_inactive(window, amount))
        self.inactive = inactive
        dump_users(self)
        return inactive

    def find_group_sync(self, group_id):
        """Synchronous variant of find_group() to call from main.Window"""
        loop = asyncio.get_event_loop()
        coroutine = self.find_group(group_id)
        res = loop.run_until_complete(coroutine)
        return res

    def delete(self, window: PySimpleGUI.Window, rps: int = 3) -> str:
        """
        :param rps: RPS limit
        :param window:  reference to GUIController to tart timer
        :returns: string with statistic about amount of deleted users
        Calls async delete_subs(). To use from main.Window"""
        self.logger.log(f'Deleting inactive users with rps={rps}')
        self.api.set_sema(rps)
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.delete_subs(self.inactive, window))

    def collect_users_info(self):
        """Collect info about deleted users. To be called from synchronous func"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.collect_info_call())

    async def collect_info_call(self):
        """Makes actual API calls to gather data"""
        response = await self.api.users.get(list(self.inactive), fields=['screen_name'])
        return response

    async def delete_subs(self, uid_set: set[int], window: PySimpleGUI.Window):
        """Makes actual API calls to delete subscribers"""
        self.api.requests = 0
        tasks = [self.timer(window, event='delete')]
        for uid in uid_set:
            task = asyncio.create_task(self.api.groups.remove_user(group_id=self.group.get('id'), user_id=uid))
            tasks.append(task)
        result = await asyncio.gather(*tasks)
        counter = 0
        for val in result[1:]:
            if val == 1:
                counter += 1
            else:
                self.logger.log('Could not delete a user')
        return f"{counter} / {len(uid_set)} "

    async def find_group(self, group_id: str):
        """finds group and returns it's name on success and memorises it in parameter self.group"""
        try:
            result = await self.api.request(method='groups.getById', data={'group_id': group_id})
            self.group = result.get('response')[0]
            self.logger.log( result.get('response')[0].get('id'))
            return result.get('response')[0].get('name')
        except (IndexError, VKAPIError):
            self.logger.log(f"Group {group_id} not found")
            return None

    async def gather_inactive(self, window: PySimpleGUI.Window, post_amount: int) -> set:
        """Creates a set of sunscribers inactive within *post_amount* posts"""
        posts = await self.get_posts(post_amount)
        post_count = len(posts)
        tasks = [self.timer(window)]
        for i in range(post_count):  # likes
            task = asyncio.create_task(self.get_liked(posts[i]))
            tasks.append(task)
        res_likes = await asyncio.gather(*tasks)

        time.sleep(1)
        tasks = [self.timer(window)]
        for i in range(post_count):  # comments
            task = asyncio.create_task(self.get_commented(posts[i]))
            tasks.append(task)
        res_comment = await asyncio.gather(*tasks)

        active_uid_set = set()
        for id_set in res_comment[1:]:
            active_uid_set.update(id_set)
        for id_list in res_likes[1:]:
            active_uid_set.update(id_list)
        self.logger.log(f'found {len(active_uid_set)} active users')
        subs_set = await self.get_subscribers()
        subs_set -= active_uid_set
        return subs_set

    async def get_subscribers(self) -> set:
        """
        :returns: set of subscribers of self.group
        """
        response = await self.api.groups.get_members(group_id=self.group.get('id'))
        id_set = set(response.items)
        return id_set

    async def get_liked(self, post):
        """Get IDs of users who liked the post
        """
        response = await self.api.likes.get_list(type='post', owner_id=-self.group.get('id'), item_id=post.id)
        return response.items

    async def get_commented(self, post) -> set:
        """Get set of IDs of users who commented the post"""
        comments_count = post.comments.count
        users = set()
        for i in range(comments_count // 100 + 1):
            response = await self.api.wall.get_comments(owner_id=-self.group.get('id'), post_id=post.id, count=100,
                                                        offset=100 * i, sort='asc', preview_length=1)
            for comment in response.items:
                if comment.thread.count > 0:  # if comment has thread with other comments under it
                    thread_comments = comment.thread.count
                    for j in range(thread_comments // 100 + 1):
                        response1 = await self.api.wall.get_comments(owner_id=-self.group.get('id'), post_id=post.id,
                                                                     count=100, offset=100 * j, sort='asc', preview_length=1,
                                                                     comment_id=comment.id)
                        users.update([comm.from_id for comm in response1.items])
                users.add(comment.from_id)
        return users

    async def get_wall(self, index: int, count: int):
        gid = self.group.get('id')
        response = await self.api.wall.get(owner_id=-gid, offset=100 * index, count=count - 100 * index)
        return response.items

    async def get_posts(self, amount: int):
        """Get required amount of posts in a list"""
        if self.group:
            gid = self.group.get('id')
            response = await self.api.wall.get(owner_id=-gid, count=1)  # amount of all the posts from group
            max_count = response.count
            count = min([amount, max_count])
            tasks = list()
            for i in range(count // 100 + 1):
                tasks.append(asyncio.create_task(self.get_wall(i, count)))
            result = await(asyncio.gather(*tasks))
            return [r for res in result for r in res]

    async def timer(self, window: PySimpleGUI.Window, event: str = 'search'):
        if event == 'search':
            while self.api.sema.queued_calls:
                event, value = window.read(1)  # wait for event, return in 1 ms anyway to update window
                if event == PySimpleGUI.WIN_CLOSED:
                    self.close_connection()
                    self.logger.close()
                    exit(-1)
                message = f"Производится поиск... Выполнено запросов: {self.api.requests} "
                window.find_element(key='group_name').update(message)
                await asyncio.sleep(1.1)
        elif event == 'delete':
            while self.api.sema.queued_calls:
                event, value = window.read(1)  # wait for event, return in 1 ms anyway to update window
                if event == PySimpleGUI.WIN_CLOSED:
                    self.close_connection()
                    self.logger.close()
                    exit(-1)
                message = f"Чистка в процессе... Прогресс: {self.api.requests} / {len(self.inactive)}"
                window.find_element(key='delete progress').update(message)
                await asyncio.sleep(1.1)
        else:
            raise ValueError(f'VkUserBot.timer(): illegal argument: {event}')

    def close_connection(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.api.http_client.close())
        self.api = None

    def reconnect(self):
        self.api = MyAPI(token=read_token())


def file_dump(inactive: set):
    with open(file='inactive.txt', mode='w') as file:
        file.write(f'Всего неактивных: {len(inactive)}\nСписок пользователей (по их ID):')
        for uid in inactive:
            file.write(f'\n{uid}')
