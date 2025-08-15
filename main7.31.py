import os
import time
import requests
import random
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from loguru import logger
from main import Data_Spider
from xhs_utils.common_util import init

def take_webpage_screenshot(url, save_path):
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1280,720')

        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        driver.save_screenshot(save_path)
        driver.quit()
        logger.info(f"📸 网页截图保存成功：{save_path}")
    except Exception as e:
        logger.warning(f"网页截图失败：{url}，错误：{e}")
        # fallback: 生成空白图
        Image.new('RGB', (1280, 720), color='white').save(save_path)

if __name__ == '__main__':
    # 初始化
    cookies_str, base_path = init()
    data_spider = Data_Spider()

    # 设置参数
    query = "INTP"
    query_num = 20
    sort_type_choice = 1
    note_type = 0
    note_time = 0
    note_range = 0
    pos_distance = 0
    save_choice = 'none'

    # 搜索笔记
    note_list, success, msg = data_spider.spider_some_search_note(
        query,
        query_num,
        cookies_str,
        base_path,
        save_choice,
        sort_type_choice,
        note_type,
        note_time,
        note_range,
        pos_distance,
        geo=None
    )

    media_root = '/Users/satoh/Desktop/Spider_XHS-master3/datas/media_datas'
    date_folder = 'date1'
    date_path = os.path.join(media_root, date_folder)
    os.makedirs(date_path, exist_ok=True)


    if success:
        for i, note_url in enumerate(note_list):
            current_note_success, current_note_msg, current_note_info = data_spider.spider_note(note_url, cookies_str)
            if not current_note_success or not current_note_info:
                logger.warning(f'跳过失败的笔记：{note_url}')
                continue

            current_user_name = current_note_info.get('nickname', '未知')
            current_note_title = current_note_info.get('title', '未知')
            current_note_desc = current_note_info.get('desc', '')
            image_list = current_note_info.get('image_list', [])

            # 路径
            duc_name = f'duc{i + 1}'
            duc_path = os.path.join(date_path, duc_name)
            scaner_path = os.path.join(duc_path, 'scaner')
            foto_path = os.path.join(duc_path, 'foto')
            test_path = os.path.join(duc_path, 'test')
            os.makedirs(scaner_path, exist_ok=True)
            os.makedirs(foto_path, exist_ok=True)
            os.makedirs(test_path, exist_ok=True)

            # 保存文字到 test/0.txt
            with open(os.path.join(test_path, '0.txt'), 'w', encoding='utf-8') as f:
                f.write(f"标题：{current_note_title}\n作者：{current_user_name}\n链接：{note_url}\n内容：{current_note_desc}")

            # 下载图片到 foto/
            for idx, img_url in enumerate(image_list):
                try:
                    img_data = requests.get(img_url).content
                    with open(os.path.join(foto_path, f'{idx}.jpg'), 'wb') as handler:
                        handler.write(img_data)
                except Exception as e:
                    logger.warning(f'图片下载失败: {img_url}, 错误: {e}')

            # 使用 selenium 截图
            screenshot_path = os.path.join(scaner_path, '0.jpg')
            take_webpage_screenshot(note_url, screenshot_path)

            logger.info(f"✅ 已保存笔记 {i + 1}: {current_note_title}")
            sleep_time = random.uniform(100, 500)
            logger.info(f"⏱️ 随机等待 {sleep_time:.2f} 秒以防止封号")
            time.sleep(sleep_time)

    else:
        logger.error("❌ 搜索失败，请检查 cookies 或关键词设置")