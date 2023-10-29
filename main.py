import cloudscraper
import signal
import asyncio
from loguru import logger
import secrets
import requests
from urllib.parse import quote
from dotenv import load_dotenv
import sys
import os
import json


def notify_discord_role(item):
    role_id = os.getenv("ROLE_ID")
    webhook_url = os.getenv("WEBHOOK_URL")

    message = {
        "content": f"<@&{role_id}> New item listed:",
        "embeds": [
            {
                "title": item["marketName"],
                "description": f'Price: ${item["salePrice"] / 100:.2f} USD\n Wear: {item.get("wear", "N/A")}\n Link: https://skinport.com/item/{item["url"]}/{item["saleId"]}',
                "url": f"https://skinport.com/item/{item['url']}/{item['saleId']}",
                "image": {
                    "url": f"https://cdn.skinport.com/cdn-cgi/image/width=256,height=128,fit=pad,format=webp,quality=85,background=transparent/images/screenshots/{item['assetId']}/playside.png"
                },
                "color": 0x00FF00,
            }
        ],
    }

    response = requests.post(
        webhook_url,
        data=json.dumps(message),
        headers={"Content-Type": "application/json"},
    )
    response.close()


async def monitor_item(item_name, item_type, item_category, delay_seconds: float, proxy_config={}):
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}, debug=False)
    item_catalog = []
    while True:
        try:
            url = f"https://skinport.com/api/browse/730?cat={quote(item_category)}&type={quote(item_type)}&item={quote(item_name)}&sort=date&order=desc"
            headers = {
                "Cookie": f"_csrf={secrets.token_hex(16)}",
                "Referer": "https://skinport.com/",
            }
            response = await asyncio.to_thread(scraper.get, url, headers=headers, proxies=proxy_config)
            if response.status_code == 200:
                data = response.json()
                new_catalog = data["items"]
                if not item_catalog:
                    item_catalog = new_catalog
                    continue

                current_ids = set([item["saleId"] for item in new_catalog])
                old_ids = set([item["saleId"] for item in item_catalog])

                newly_added_ids = current_ids.difference(old_ids)
                if newly_added_ids:
                    for id in newly_added_ids:
                        item = next(
                            item for item in new_catalog if item["saleId"] == id)
                        notify_discord_role(item)
                        item_url = f"https://skinport.com/item/{item['url']}/{item['saleId']}"
                        logger.info(
                            f"Newly listed item found: {item_url}")
                else:
                    logger.info(
                        f"({item_type} | {item_name}) No new items detected")
                item_catalog = new_catalog

            else:
                logger.warning(
                    f"Failed to fetch catalog. Status Code: {response.status_code}")
            response.close()
        except Exception as e:
            logger.exception(e)
        await asyncio.sleep(delay_seconds)


def handle_exit(signum, frame):
    logger.warning("Received exit signal. Stopping monitoring.")
    sys.exit(0)


async def main():
    tasks = []
    proxy_config = {
        "http": f"http://{os.getenv('PROXY')}", "https": f"http://{os.getenv('PROXY')}"}

    tasks.append(asyncio.create_task(monitor_item(
        "Printstream", "M4A1-S", "Rifle", 5.0, proxy_config)))
    tasks.append(asyncio.create_task(monitor_item(
        "Fire Serpent", "AK-47", "Rifle", 5.0, proxy_config)))

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    load_dotenv()
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
