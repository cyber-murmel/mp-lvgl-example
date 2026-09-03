from machine import bootloader, reset
from upysh import *
import aiorepl
import asyncio
import lv_utils
import lvgl as lv
import ZDD
from gui.file_browser import file_browser
from gui.menu import Menu, scroll_flex_label
from gui.utils import init_indevs

class SoftwareInformationPage:
    def __init__(self, menu_page):
        page_section = lv.menu_section(menu_page)
        page_cont = lv.menu_cont(page_section)
        scroll_flex_label(page_cont, "Version 1.0")

class FilesPage:
    def __init__(self, menu_page):
        page_cont = lv.menu_cont(menu_page)
        file_browser(page_cont)

menu_tree = [
    {
        "name": "Settings",
        "pages": [
            {
                "name":"Files",
                "icon": lv.SYMBOL.DIRECTORY,
                "class": FilesPage,
            },
        ],
    },
    {
        "name": "Others",
        "pages": [
            {
                "name":"About",
                "icon": None,
                "pages" :[
                    {
                        "name": "Software information",
                        "class": SoftwareInformationPage,
                    },
                ],
            },
        ],
    },
]

aiorepl_task = asyncio.create_task(aiorepl.task())
lvgl_event_loop = lv_utils.event_loop(asynchronous=True)
task_list = [
    aiorepl_task,
    lvgl_event_loop.refresh_task,
    lvgl_event_loop.timer_task,
]

def main():
    global menu
    ZDD.init()
    init_indevs()
    menu = Menu(menu_tree)
    asyncio.run(asyncio.gather(*task_list))

if __name__ == "__main__":
    main()
