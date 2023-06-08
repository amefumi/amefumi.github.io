import os
import requests
from bs4 import BeautifulSoup
import re


def download_image(image_url, save_path):
    response = requests.get(image_url)
    with open(save_path, 'wb') as file:
        file.write(response.content)


def process_markdown_file(md_file):
    # 获取文件名和目录
    file_name = os.path.basename(md_file)
    file_dir = os.path.dirname(md_file)
    images_dir = os.path.join(file_dir, f"images-{file_name[:-3]}")

    # 创建图片目录
    if not os.path.exists(images_dir):
        os.makedirs(images_dir)

    # 读取Markdown文件内容
    with open(md_file, 'r', encoding='utf-8') as file:
        content = file.read()

    # 使用BeautifulSoup解析Markdown内容
    soup = BeautifulSoup(content, 'html.parser')

    # 查找所有的图片链接
    image_tags = soup.find_all('img')
    for image_tag in image_tags:
        image_url = image_tag['src']

        # 从图片链接中提取文件名
        image_filename = os.path.basename(image_url)

        # 下载图片并保存到本地
        save_path = os.path.join(images_dir, image_filename)
        download_image(image_url, save_path)

        # 修改Markdown中图片链接为本地路径
        new_image_url = f"image-filename/{image_filename}"
        image_tag['src'] = new_image_url

    # 将修改后的内容写回Markdown文件
    with open(md_file, 'w') as file:
        file.write(str(soup))


# 指定Markdown文件路径
markdown_file = "2023-06-05-rdma-notes.md"

# 处理Markdown文件
process_markdown_file(markdown_file)
